import sys
import time
import re
import subprocess
import psutil
import wmi
import pynvml

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QAction, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QStyle
)

REFRESH_MS = 400
SMART_REFRESH_SECONDS = 8


# -------------------------
# Utilities
# -------------------------

def run_command(cmd):
    try:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        return subprocess.check_output(
            cmd,
            text=True,
            stderr=subprocess.DEVNULL,
            startupinfo=startup,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
    except:
        return ""


def c_to_f(c):
    try:
        return int((int(c) * 9 / 5) + 32)
    except:
        return "?"


def format_speed(v):
    if v >= 1024:
        return f"{v/1024:.2f} GB/s"
    if v >= 1:
        return f"{v:.1f} MB/s"
    kb = v * 1024
    if kb >= 1:
        return f"{kb:.0f} KB/s"
    return "0 MB/s"


# -------------------------
# SMART parsing
# -------------------------

def run_smartctl(device, dtype=None):

    attempts = []
    attempts.append(["smartctl", "-a", device])

    if dtype:
        attempts.append(["smartctl", "-a", "-d", dtype, device])

    attempts.append(["smartctl", "-a", "-d", "ata", device])
    attempts.append(["smartctl", "-a", "-d", "sat", device])

    for cmd in attempts:

        data = run_command(cmd)

        if data and ("SMART" in data or "Temperature:" in data):
            return data

    return ""


def parse_temperature_from_ata(data):

    for line in data.splitlines():

        if "Temperature_Celsius" in line or "Airflow_Temperature_Cel" in line:

            nums = re.findall(r"\d+", line)

            if nums:
                return nums[-1]

    return "?"


def parse_lba_written(data):

    for line in data.splitlines():

        if "Total_LBAs_Written" in line:

            nums = re.findall(r"\d+", line)

            if nums:
                return int(nums[-1])

    return None


def parse_smart(device, dtype=None):

    data = run_smartctl(device, dtype)

    temp = "?"
    health = "?"
    written = "?"

    if not data:
        return temp, health, written

    m = re.search(r"Temperature:\s+(\d+)", data)

    if m:
        temp = m.group(1)

    if temp == "?":
        temp = parse_temperature_from_ata(data)

    m = re.search(r"Percentage Used:\s+(\d+)%", data)

    if m:
        used = int(m.group(1))
        health = f"{100-used}%"

    if health == "?" and "PASSED" in data:
        health = "100%"

    # Primary: Data Units Written (common on NVMe / many modern SSDs)
    m = re.search(r"Data Units Written:\s+([\d,]+)", data)
    if m:
        units = int(m.group(1).replace(",", ""))
        tb = (units * 512000) / (1024**4)  # 1000-based units × 512 bytes
        written = f"{tb:.2f} TB"

    # Fallback 1: Total_LBAs_Written (common on many SATA SSDs)
    if written == "?":
        lbas = parse_lba_written(data)
        if lbas:
            tb = (lbas * 512) / (1024**4)
            written = f"{tb:.2f} TB"

    # Fallback 2: Host Writes / Cumulative Host Sectors Written variants
    if written == "?":
        m = re.search(r"(Host[_ -]?Writes|Cumulative Host Sectors Written)\s*[:=]\s*([\d,]+)", data, re.IGNORECASE)
        if m:
            sectors = int(m.group(2).replace(",", ""))
            tb = (sectors * 512) / (1024**4)
            written = f"{tb:.2f} TB"

    # Fallback 3: Lifetime / NAND / Physical Writes in GB (some drives report GB directly)
    if written == "?":
        m = re.search(r"(Lifetime|Total|NAND|Physical)[_ -]?Writes(_GB)?\s*[:=]\s*([\d,.]+)", data, re.IGNORECASE)
        if m:
            gb_str = m.group(3).replace(",", "")
            try:
                gb = float(gb_str)
                tb = gb / 1024
                written = f"{tb:.2f} TB"
            except:
                pass

    # Fallback 4: Scan attribute table for large raw values on common write IDs (241, 246, etc.)
    if written == "?":
        for line in data.splitlines():
            if re.search(r"^\s*(241|242|246|249)\s+", line):  # common IDs for writes
                parts = re.split(r"\s+", line.strip())
                if len(parts) >= 10:  # typical: ID FLAG VALUE WORST THRESH TYPE UPDATED WHEN_FAILED RAW
                    raw_str = parts[-1].replace("-", "").replace(",", "")
                    try:
                        raw_val = int(raw_str)
                        if raw_val > 1000000:  # avoid tiny / temp values
                            tb = (raw_val * 512) / (1024**4)  # assume sectors
                            written = f"{tb:.2f} TB"
                            break
                    except ValueError:
                        pass

    return temp, health, written


# -------------------------
# Drive labels
# -------------------------

def get_drive_labels():

    c = wmi.WMI()

    labels = []

    for disk in c.Win32_DiskDrive():

        model = disk.Model or "Drive"
        letters = []

        for part in disk.associators("Win32_DiskDriveToDiskPartition"):
            for logical in part.associators("Win32_LogicalDiskToPartition"):
                letters.append(logical.DeviceID)

        label = ", ".join(letters) if letters else "No Letter"

        labels.append(f"{label}  {model}")

    return labels


# -------------------------
# Gauge widget
# -------------------------

class Gauge(QWidget):

    def __init__(self, title):

        super().__init__()

        self.title = title
        self.target = 0
        self.value = 0

        self.main = ""
        self.sub1 = ""
        self.sub2 = ""
        self.sub3 = ""

        self.setMinimumSize(220,220)

    def set_data(self, percent, main="", s1="", s2="", s3=""):

        self.target = percent
        self.main = main
        self.sub1 = s1
        self.sub2 = s2
        self.sub3 = s3

    def tick(self):

        self.value += (self.target - self.value) * 0.2
        self.update()

    def color(self):

        v = self.value

        if v < 60:
            return QColor(0,200,120)
        elif v < 85:
            return QColor(255,180,0)
        return QColor(255,70,70)

    def paintEvent(self, e):

        rect = self.rect()
        size = min(rect.width(), rect.height())

        square = rect.adjusted(
            (rect.width()-size)//2,
            (rect.height()-size)//2,
            -(rect.width()-size)//2,
            -(rect.height()-size)//2
        )

        arc = square.adjusted(24,24,-24,-24)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        base = self.color()

        # soft center glow
        center = QPointF(square.center())
        radius = size * 0.42
        radial = QRadialGradient(center, radius)
        radial.setColorAt(0.00, QColor(base.red(), base.green(), base.blue(), 85))
        radial.setColorAt(0.28, QColor(base.red(), base.green(), base.blue(), 42))
        radial.setColorAt(0.58, QColor(base.red(), base.green(), base.blue(), 14))
        radial.setColorAt(1.00, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(radial)
        p.drawEllipse(QRectF(square.adjusted(34, 34, -34, -34)))

        # subtle outer halo behind ring
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 26), 34, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 0, 360 * 16)

        # base ring
        p.setPen(QPen(QColor(60,60,60),16, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 0, 360 * 16)

        # animated glow arc
        span = int(360 * self.value / 100)

        p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 70), 30, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 90 * 16, -span * 16)

        p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 135), 22, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 90 * 16, -span * 16)

        p.setPen(QPen(base, 16, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 90 * 16, -span * 16)

        p.setPen(Qt.GlobalColor.white)

        p.setFont(QFont("Segoe UI",10))
        p.drawText(square.adjusted(0,-75,0,0),
                   Qt.AlignmentFlag.AlignHCenter,
                   self.title)

        p.setFont(QFont("Segoe UI",20,QFont.Weight.Bold))
        p.drawText(square, Qt.AlignmentFlag.AlignCenter, self.main)

        p.setFont(QFont("Segoe UI",9))

        if self.sub1:
            p.drawText(square.adjusted(0,45,0,0),
                       Qt.AlignmentFlag.AlignHCenter,
                       self.sub1)

        if self.sub2:
            p.drawText(square.adjusted(0,63,0,0),
                       Qt.AlignmentFlag.AlignHCenter,
                       self.sub2)

        if self.sub3:
            p.drawText(square.adjusted(0,81,0,0),
                       Qt.AlignmentFlag.AlignHCenter,
                       self.sub3)


# -------------------------
# Main monitor
# -------------------------

class Monitor(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("System Gauges")

        pynvml.nvmlInit()
        self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        # GPU-only fix:
        # keep a short rolling window so bursty FLUX kernels don't read falsely low
        self.gpu_samples = []
        self.gpu_window_seconds = 1.6

        self.last = psutil.disk_io_counters(perdisk=True)
        self.last_time = time.time()

        # ---- Disk detection + sorting ----

        disk_names = list(psutil.disk_io_counters(perdisk=True).keys())
        labels = get_drive_labels()

        pairs = list(zip(disk_names, labels))

        pairs.sort(key=lambda x: x[1])  # SORT BY DRIVE LETTER

        self.disks = [p[0] for p in pairs]
        self.labels = [p[1] for p in pairs]

        # ----------------------------------

        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        grid = QGridLayout(container)

        self.gpu = Gauge("GPU")
        self.ram = Gauge("RAM")

        grid.addWidget(self.gpu,0,0)
        grid.addWidget(self.ram,0,1)

        self.disk_gauges = {}

        for i,d in enumerate(self.disks):

            g = Gauge(self.labels[i])
            self.disk_gauges[d] = g

            row = 1 + (i//2)
            col = i%2

            grid.addWidget(g,row,col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # SMART

        self.smart_devices = self.detect_smart()
        self.smart_cache = {}
        self.last_smart = 0

        # Tray

        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray = QSystemTrayIcon(icon,self)

        menu = QMenu()

        show = QAction("Show",self)
        hide = QAction("Hide",self)
        exit = QAction("Exit",self)

        show.triggered.connect(self.show)
        hide.triggered.connect(self.hide)
        exit.triggered.connect(QApplication.quit)

        menu.addAction(show)
        menu.addAction(hide)
        menu.addSeparator()
        menu.addAction(exit)

        self.tray.setContextMenu(menu)
        self.tray.show()

        # timers

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(REFRESH_MS)

        self.anim = QTimer()
        self.anim.timeout.connect(self.animate)
        self.anim.start(33)

    def detect_smart(self):

        out = run_command(["smartctl","--scan-open"])

        devices = []

        for line in out.splitlines():

            parts = line.split()

            if not parts:
                continue

            device = parts[0]
            dtype = None

            if "-d" in parts:
                dtype = parts[parts.index("-d")+1]

            devices.append((device,dtype))

        return devices

    def refresh_smart(self):

        for i,d in enumerate(self.disks):

            if not self.smart_devices:
                self.smart_cache[d] = ("?","?","?")
                continue

            device,dtype = self.smart_devices[min(i,len(self.smart_devices)-1)]

            self.smart_cache[d] = parse_smart(device,dtype)

        self.last_smart = time.time()

    def animate(self):

        self.gpu.tick()
        self.ram.tick()

        for g in self.disk_gauges.values():
            g.tick()

    def update_stats(self):

        # GPU
        util = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
        temp = pynvml.nvmlDeviceGetTemperature(
            self.gpu_handle,
            pynvml.NVML_TEMPERATURE_GPU
        )

        gpu_now = time.time()
        gpu_pct = max(int(util.gpu), int(util.memory))

        self.gpu_samples.append((gpu_now, gpu_pct))
        cutoff = gpu_now - self.gpu_window_seconds
        self.gpu_samples = [(t, v) for t, v in self.gpu_samples if t >= cutoff]

        if self.gpu_samples:
            gpu_display = max(v for t, v in self.gpu_samples)
        else:
            gpu_display = gpu_pct

        try:
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
            vram_used_gb = mem_info.used / (1024 ** 3)
            vram_total_gb = mem_info.total / (1024 ** 3)
            vram_text = f"VRAM {vram_used_gb:.1f}/{vram_total_gb:.1f} GB"
        except:
            vram_text = ""

        try:
            power_w = pynvml.nvmlDeviceGetPowerUsage(self.gpu_handle) / 1000.0
            power_text = f"{power_w:.0f} W"
        except:
            power_text = ""

        self.gpu.set_data(
            gpu_display,
            f"{gpu_display:.0f}%",
            f"{c_to_f(temp)}°F",
            vram_text,
            power_text
        )

        # RAM
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024 ** 3)
        avail_gb = mem.available / (1024 ** 3)

        self.ram.set_data(
            mem.percent,
            f"{used_gb:.1f} GB",           # main number = In Use (like Task Manager)
            f"{mem.percent:.1f}%",
            f"Avail {avail_gb:.1f} GB"
        )

        # DISKS

        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        cur = psutil.disk_io_counters(perdisk=True)

        if now - self.last_smart > SMART_REFRESH_SECONDS:
            self.refresh_smart()

        for d in self.disks:

            try:
                r = ((cur[d].read_bytes-self.last[d].read_bytes)/1024/1024)/dt
                w = ((cur[d].write_bytes-self.last[d].write_bytes)/1024/1024)/dt
            except:
                r=w=0

            total = max(0,r+w)

            pct = min(total/500*100,100)

            temp,health,writes = self.smart_cache.get(d,("?", "?", "?"))

            self.disk_gauges[d].set_data(
                pct,
                format_speed(total),
                f"Temp {c_to_f(temp)}°F",
                f"Health {health}",
                f"Writes {writes}"
            )

        self.last = cur


app = QApplication(sys.argv)

window = Monitor()
window.resize(600,800)
window.show()

sys.exit(app.exec())