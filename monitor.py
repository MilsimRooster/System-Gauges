import sys
import time
import re
import subprocess
import math
import warnings
import json
import os
import traceback
from pathlib import Path
import psutil
import wmi

warnings.filterwarnings(
    "ignore",
    message=r"The pynvml package is deprecated.*",
    category=FutureWarning,
)
import pynvml

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QSize, QThread, pyqtSignal, QUrl
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QAction, QActionGroup, QRadialGradient, QBrush, QIcon, QPixmap, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QSystemTrayIcon,
    QMenu,
    QStyle,
    QLabel,
    QSizePolicy,
    QFileDialog
)
QAudioOutput = None
QMediaPlayer = None
QVideoSink = None
VIDEO_BACKGROUND_AVAILABLE = False

REFRESH_MS = 150
SMART_REFRESH_SECONDS = 4
SMARTCTL_PATH = r"C:\Program Files\smartmontools\bin\smartctl.exe"
UNKNOWN_SMART = ("?", "N/A")
SMART_DEBUG = False
DEFAULT_SKIN = "graphite"
CUSTOM_SKIN_KEY = "custom_image"
VIDEO_SKIN_KEY = "custom_video"
CUSTOM_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
CUSTOM_VIDEO_FILTER = "Videos (*.mp4 *.mov *.m4v *.avi *.mkv *.webm *.wmv)"
CUSTOM_IMAGE_OVERLAY_ALPHA = 132
VIDEO_OVERLAY_ALPHA = 138

SKINS = {
    "graphite": {"name": "Graphite", "background": "#17191c", "panel": "#111a2a", "text": "#f3fbff", "hint": "#a9d8ff"},
    "carbon": {"name": "Carbon Fiber", "background": "#101315", "panel": "#151d20", "text": "#f0fbf7", "hint": "#9fd6c7"},
    "deep_navy": {"name": "Deep Navy", "background": "#111722", "panel": "#0d1d33", "text": "#f3f8ff", "hint": "#9ec9ff"},
    "brushed_steel": {"name": "Brushed Steel", "background": "#202326", "panel": "#2b3035", "text": "#f6fbff", "hint": "#c5d6e3"},
    "glass_green": {"name": "Glass Green", "background": "#101a17", "panel": "#0d241d", "text": "#f2fff9", "hint": "#91f0c2"},
    "amber": {"name": "Amber Warning", "background": "#1b1711", "panel": "#2a1d0d", "text": "#fff7e8", "hint": "#ffd58b"},
}


def smart_log(message):
    if SMART_DEBUG:
        print(message)


def resource_path(filename):
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path / filename


def config_path():
    appdata = os.getenv("APPDATA")
    base_path = Path(appdata) if appdata else Path.home()
    return base_path / "SystemGauges" / "config.json"


def log_path():
    return config_path().with_name("system_gauges.log")


def log_event(message, exc=None):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
            if exc is not None:
                handle.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass
    print(message)


def handle_uncaught_exception(exc_type, exc, tb):
    log_event("Uncaught exception", exc)
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = handle_uncaught_exception


def load_config():
    path = config_path()
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log_event(f"Config load failed: {e}", e)
    return {}


def save_config(config):
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except Exception as e:
        log_event(f"Config save failed: {e}", e)


def skin_by_key(key):
    return SKINS.get(key, SKINS[DEFAULT_SKIN])


def custom_image_path(config):
    path = config.get("custom_image_path", "")
    return Path(path) if path else None


def custom_video_path(config):
    path = config.get("custom_video_path", "")
    return Path(path) if path else None


def window_style(skin):
    return f"""
QWidget#MonitorRoot {{
    background: {skin["background"]};
    color: {skin["text"]};
    font-family: "Segoe UI";
}}
QWidget {{
    color: {skin["text"]};
    font-family: "Segoe UI";
    background: transparent;
}}
QScrollArea {{
    border: 0;
    background: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    width: 0px;
    height: 0px;
}}
"""


def hint_style(skin):
    return f"""
        color: {skin["hint"]};
        font-size: 12px;
        background: {skin["panel"]};
        padding: 6px 10px;
        border-radius: 3px;
    """


def run_command(cmd):
    try:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startup,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=8
        )
        return (result.stdout or "") + (result.stderr or "")
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        log_event(f"Command failed: {' '.join(cmd)} | Error: {e}", e)
        return ""


def c_to_f(c):
    try:
        return int((float(c) * 9 / 5) + 32)
    except (TypeError, ValueError):
        return "?" 


def format_temp(c):
    f = c_to_f(c)
    return f"Temp {f}°F" if f != "?" else "Temp N/A"


def format_speed(v):
    if v >= 1024:
        return f"{v/1024:.2f} GB/s"
    if v >= 1:
        return f"{v:.1f} MB/s"
    kb = v * 1024
    if kb >= 1:
        return f"{kb:.0f} KB/s"
    return "0 B/s"


# ====================== SMART ======================
def smartctl_exists():
    try:
        result = subprocess.run(
            [SMARTCTL_PATH, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=4
        )
        return result.returncode == 0
    except Exception:
        return False


def parse_smart(device, dtype="nvme"):
    smart_log(f"Attempting SMART on {device} with type {dtype}")
    attempts = []
    if dtype:
        attempts.append([SMARTCTL_PATH, "-a", "-d", dtype, device])
    attempts.append([SMARTCTL_PATH, "-a", device])
    if dtype != "nvme":
        attempts.append([SMARTCTL_PATH, "-a", "-d", "nvme", device])

    for cmd in attempts:
        data = run_command(cmd)
        smart_log(f"  -> Got {len(data)} characters")
        if data and "SMART support is: Unavailable" not in data:
            # Temperature
            temp = "?"
            m = re.search(r"(?:Temperature|Current Drive Temperature):\s+(\d+)", data, re.IGNORECASE)
            if not m:
                m = re.search(r"Temperature_Celsius.*?-\s+(\d+)", data, re.IGNORECASE)
            if not m:
                m = re.search(r"Airflow_Temperature_Cel.*?-\s+(\d+)", data, re.IGNORECASE)
            if m:
                temp = m.group(1)

            # Health
            health = "?"
            if re.search(r"(PASSED|OK)", data, re.IGNORECASE):
                health = "100%"
            m = re.search(r"Percentage Used:\s+(\d+)%", data, re.IGNORECASE)
            if m:
                health = f"{100 - int(m.group(1))}%"
            m = re.search(r"Remaining_Lifetime_Perc.*?\s(\d+)(?:\s|$)", data, re.IGNORECASE)
            if m:
                health = f"{int(m.group(1))}%"
            m = re.search(r"Media_Wearout_Indicator.*?\s(\d+)(?:\s|$)", data, re.IGNORECASE)
            if m:
                health = f"{int(m.group(1))}%"

            smart_log(f"  SMART Success on {device} | Temp: {temp}")
            return temp, health

    smart_log(f"  All attempts failed for {device}")
    return UNKNOWN_SMART


def detect_smart():
    print("=== Scanning for Drives ===")
    devices = []
    if not smartctl_exists():
        print(f"smartctl not found or not runnable: {SMARTCTL_PATH}")
        return devices

    scan = run_command([SMARTCTL_PATH, "--scan-open"])
    for line in scan.splitlines():
        m = re.match(r"(\S+)\s+-d\s+(\S+)", line)
        if m and ("PHYSICALDRIVE" in m.group(1).upper() or re.match(r"/dev/sd[a-z]+", m.group(1), re.IGNORECASE)):
            device = m.group(1)
            dtype = m.group(2).split(",")[0]
            devices.append((device, dtype))
            print(f"Detected: {device} ({dtype})")

    if devices:
        return sorted(devices, key=lambda item: physicaldrive_index(item[0]))

    for i in range(8):
        dev = f"\\\\.\\PHYSICALDRIVE{i}"
        for dtype in ("nvme", "sat", None):
            cmd = [SMARTCTL_PATH, "-i", dev] if dtype is None else [SMARTCTL_PATH, "-i", "-d", dtype, dev]
            data = run_command(cmd)
            if data and re.search(r"(Device Model|Model Number|SMART support)", data, re.IGNORECASE):
                devices.append((dev, dtype))
                print(f"Detected: {dev} ({dtype or 'auto'})")
                break
    return devices


def physicaldrive_index(device_id):
    m = re.search(r"PHYSICALDRIVE(\d+)", device_id or "", re.IGNORECASE)
    if m:
        return int(m.group(1))

    m = re.search(r"/dev/sd([a-z]+)", device_id or "", re.IGNORECASE)
    if m:
        value = 0
        for char in m.group(1).lower():
            value = (value * 26) + (ord(char) - ord("a") + 1)
        return value - 1

    return 9999


def get_drive_labels():
    try:
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
    except:
        return ["Drive 1", "Drive 2", "Drive 3", "Drive 4"]


def get_drive_info():
    try:
        c = wmi.WMI()
        drives = []
        for disk in c.Win32_DiskDrive():
            model = disk.Model or "Drive"
            letters = []
            for part in disk.associators("Win32_DiskDriveToDiskPartition"):
                for logical in part.associators("Win32_LogicalDiskToPartition"):
                    letters.append(logical.DeviceID)
            label = ", ".join(letters) if letters else "No Letter"
            index = int(disk.Index)
            drives.append({
                "psutil": f"PhysicalDrive{index}",
                "smart": f"\\\\.\\PHYSICALDRIVE{index}",
                "label": f"{label}  {model}",
                "index": index,
            })
        return sorted(drives, key=lambda drive: drive["index"])
    except Exception as e:
        log_event(f"WMI drive lookup failed: {e}", e)
        return []


class SmartWorker(QThread):
    result_ready = pyqtSignal(dict)

    def __init__(self, disk_devices, previous_cache):
        super().__init__()
        self.disk_devices = disk_devices
        self.previous_cache = previous_cache.copy()

    def run(self):
        results = {}
        try:
            for disk_name, device, dtype in self.disk_devices:
                reading = parse_smart(device, dtype)
                if reading == UNKNOWN_SMART and disk_name in self.previous_cache:
                    reading = self.previous_cache[disk_name]
                results[disk_name] = reading
        except Exception as e:
            log_event(f"SMART worker failed: {e}", e)
        self.result_ready.emit(results)


# RGB, Gauge, Monitor classes (full)
class RGBController:
    def __init__(self):
        self.client = None
        self.RGBColor = None
        try:
            from openrgb import OpenRGBClient
            from openrgb.utils import RGBColor
            self.RGBColor = RGBColor
            self.client = OpenRGBClient()
        except:
            self.client = None

    def update(self, cpu, gpu, ram):
        if self.client is None or self.RGBColor is None:
            return
        try:
            load = max(cpu, gpu, ram)
            if load <= 50:
                r = int(255 * (load / 50))
                g = 255
                b = 0
            else:
                r = 255
                g = int(255 * (100 - load) / 50)
                b = 0
            color = self.RGBColor(r, g, b)
            self.client.set_color(color)
        except:
            pass


class Gauge(QWidget):
    def __init__(self, title, preferred_size=230, minimum_size=70):
        super().__init__()
        self.title = title
        self.preferred_size = preferred_size
        self.minimum_size = minimum_size
        self.target = 0
        self.value = 0
        self.main = ""
        self.sub1 = ""
        self.sub2 = ""
        self.sub3 = ""
        self.setMinimumSize(minimum_size, minimum_size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.history = []
        self.MAX_HISTORY = 100
        self.last_smoothed = 0.0
        self.background_is_image = False
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def uses_image_background(self):
        parent = self.window()
        if hasattr(parent, "using_rich_background"):
            return parent.using_rich_background()
        if hasattr(parent, "using_custom_image_background"):
            return parent.using_custom_image_background()
        return self.background_is_image

    def sizeHint(self):
        return QSize(self.preferred_size, self.preferred_size)

    def minimumSizeHint(self):
        return QSize(self.minimum_size, self.minimum_size)

    def set_data(self, percent, main="", s1="", s2="", s3=""):
        self.target = percent
        self.main = main
        self.sub1 = s1 if s1 not in ["?", ""] else "N/A"
        self.sub2 = s2 if s2 not in ["?", ""] else "N/A"
        self.sub3 = s3 if s3 not in ["?", ""] else "N/A"

        smoothed = (self.last_smoothed * 0.8) + (percent * 0.2)
        self.last_smoothed = smoothed
        self.history.append(smoothed)
        if len(self.history) > self.MAX_HISTORY:
            self.history.pop(0)

    def tick(self):
        self.value += (self.target - self.value) * 0.2
        self.update()

    def color(self):
        v = self.value
        if v < 60:
            return QColor(0, 200, 120)
        elif v < 85:
            return QColor(255, 180, 0)
        return QColor(255, 70, 70)

    def draw_waveform(self, painter: QPainter, rect: QRectF, alpha=140, glow=True):
        if len(self.history) == 0:
            return
        w = rect.width()
        h = rect.height()
        if w < 5 or h < 5:
            return
        x = int(rect.left())
        y = int(rect.top())
        w = int(w)
        h = int(h)
        n = len(self.history)
        bar_width = max(1.5, w / n)

        for i, val in enumerate(self.history):
            bar_h = (val / 100.0) * h
            if bar_h < 0.5:
                continue
            x_pos = int(x + i * bar_width)
            y_pos = int(y + h - bar_h)
            bar_w_int = int(bar_width)
            bar_h_int = int(bar_h)

            color = QColor(0, 255, 120) if val < 50 else QColor(255, 200, 0) if val < 80 else QColor(255, 60, 0)
            if self.uses_image_background():
                color.setAlpha(220)

            if glow:
                glow_col = QColor(color.red(), color.green(), color.blue(), 76 if self.uses_image_background() else 100)
                painter.setBrush(glow_col)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(x_pos, y_pos, bar_w_int, bar_h_int)

            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            core_w = int(bar_width * 0.65)
            core_x = int(x_pos + (bar_width - core_w) / 2)
            painter.drawRect(core_x, y_pos, core_w, bar_h_int)

    def draw_arc_waveform(self, painter: QPainter, arc: QRectF, size):
        if len(self.history) == 0 or arc.width() < 20 or arc.height() < 20:
            return

        values = self.history[-52:]
        if not values:
            return

        center = arc.center()
        ring_radius = arc.width() / 2.0
        base_radius = ring_radius - max(12.0, size * 0.080)
        max_bar = max(7.0, size * 0.105)
        start_angle = 205.0
        end_angle = 335.0
        step = (end_angle - start_angle) / max(1, len(values) - 1)
        pen_width = max(2.0, size * 0.010)

        for i, val in enumerate(values):
            bar_len = max(1.5, (val / 100.0) * max_bar)
            angle_deg = start_angle + (i * step)
            angle = math.radians(angle_deg)
            inner = QPointF(
                center.x() + base_radius * math.cos(angle),
                center.y() - base_radius * math.sin(angle)
            )
            outer = QPointF(
                center.x() + (base_radius + bar_len) * math.cos(angle),
                center.y() - (base_radius + bar_len) * math.sin(angle)
            )
            color = QColor(0, 255, 120) if val < 50 else QColor(255, 200, 0) if val < 80 else QColor(255, 60, 0)
            color.setAlpha(145 if self.uses_image_background() else 175)
            painter.setPen(QPen(color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(inner, outer)

    def paintEvent(self, e):
        rect = self.rect()
        if rect.width() < 10 or rect.height() < 10:
            return

        size = min(rect.width(), rect.height())
        square = rect.adjusted((rect.width() - size) // 2, (rect.height() - size) // 2,
                               -(rect.width() - size) // 2, -(rect.height() - size) // 2)
        compact = size < 205
        inset = max(14, int(size * (0.088 if compact else 0.078)))
        arc = square.adjusted(inset, inset, -inset, -inset)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        mode = getattr(self, 'display_mode', 0)

        if mode == 1:
            waveform_rect = rect.adjusted(8, 8, -8, -8)
            bg_alpha = 72 if self.uses_image_background() else 255
            p.fillRect(waveform_rect, QColor(10, 14, 22, bg_alpha))
            self.draw_waveform(p, waveform_rect, alpha=200, glow=True)
            p.setPen(QColor(160, 220, 255, 220))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(waveform_rect.adjusted(14, 10, -14, -14),
                       Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, self.title.upper())
            return

        base = self.color()
        center = QPointF(square.center())
        radius = size * 0.42
        radial = QRadialGradient(center, radius)
        radial.setColorAt(0.00, QColor(base.red(), base.green(), base.blue(), 62 if compact else 76))
        radial.setColorAt(0.30, QColor(base.red(), base.green(), base.blue(), 30 if compact else 38))
        radial.setColorAt(0.62, QColor(base.red(), base.green(), base.blue(), 8 if compact else 12))
        radial.setColorAt(1.00, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(radial)
        glow_inset = max(24, int(size * 0.13))
        p.drawEllipse(QRectF(square.adjusted(glow_inset, glow_inset, -glow_inset, -glow_inset)))

        track_width = max(7, int(size * (0.045 if compact else 0.050)))
        glow_width = max(10, int(size * (0.066 if compact else 0.074)))
        tracer_width = max(5, int(size * (0.037 if compact else 0.041)))

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 18), glow_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 0, 360 * 16)

        p.setPen(QPen(QColor(48, 54, 52), track_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(arc, 0, 360 * 16)

        span = max(0.0, min(360.0, 360.0 * self.value / 100.0))
        if span > 0.2:
            span16 = int(span * 16)
            p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 46), glow_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(arc, 90 * 16, -span16)

            tail = min(span, 48.0 if compact else 58.0)
            segments = 8
            for i in range(segments):
                seg_start = max(0.0, span - tail + (tail * i / segments))
                seg_end = max(0.0, span - tail + (tail * (i + 1) / segments))
                alpha = int((22 if compact else 30) + (i / max(1, segments - 1)) * (88 if compact else 112))
                pen = QPen(QColor(base.red(), base.green(), base.blue(), alpha), tracer_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawArc(arc, int((90 - seg_start) * 16), -int((seg_end - seg_start) * 16))

            p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 230), max(4, int(size * (0.026 if compact else 0.030))), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(arc, 90 * 16, -span16)

            ring_radius = arc.width() / 2.0
            end_angle = math.radians(90.0 - span)
            head = QPointF(
                arc.center().x() + ring_radius * math.cos(end_angle),
                arc.center().y() - ring_radius * math.sin(end_angle)
            )
            head_radius = max(3.8, tracer_width * (0.54 if compact else 0.58))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(base.red(), base.green(), base.blue(), 46 if compact else 58))
            p.drawEllipse(head, head_radius * 1.85, head_radius * 1.85)
            p.setBrush(QColor(base.red(), base.green(), base.blue(), 215))
            p.drawEllipse(head, head_radius, head_radius)

        p.setPen(Qt.GlobalColor.white)

        micro = size < 130
        title_offset_y = int(size * (0.73 if compact else 0.72))
        sub_offset_1 = int(size * (0.19 if compact else 0.20))
        sub_offset_2 = int(size * (0.275 if compact else 0.28))
        sub_offset_3 = int(size * (0.355 if compact else 0.36))

        if size >= 105:
            p.setFont(QFont("Segoe UI", max(6, int(size * (0.036 if compact else 0.038)))))
            title_rect = square.adjusted(2, title_offset_y - 20, -2, -sub_offset_1 - 10)
            p.drawText(title_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextSingleLine, self.title)

        p.setFont(QFont("Segoe UI", max(9, int(size * (0.064 if compact else 0.068))), QFont.Weight.DemiBold))
        p.drawText(square, Qt.AlignmentFlag.AlignCenter, self.main)

        p.setFont(QFont("Segoe UI", max(6, int(size * (0.038 if compact else 0.040)))))
        if self.sub1 and self.sub1 != "N/A" and size >= 105:
            p.drawText(square.adjusted(0, sub_offset_1, 0, 0), Qt.AlignmentFlag.AlignHCenter, self.sub1)
        if self.sub2 and self.sub2 != "N/A" and size >= 118:
            p.drawText(square.adjusted(0, sub_offset_2, 0, 0), Qt.AlignmentFlag.AlignHCenter, self.sub2)
        if self.sub3 and self.sub3 != "N/A" and not micro:
            p.drawText(square.adjusted(0, sub_offset_3, 0, 0), Qt.AlignmentFlag.AlignHCenter, self.sub3)

        if mode == 2 and len(self.history) > 0:
            self.draw_arc_waveform(p, arc, size)


class Monitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("MonitorRoot")
        self.setWindowTitle("System Gauges")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.config = load_config()
        self.current_skin_key = self.config.get("skin", DEFAULT_SKIN)
        if self.config.get("background_type") == "video" and custom_video_path(self.config):
            self.config["background_type"] = "image"
            self.current_skin_key = CUSTOM_SKIN_KEY if custom_image_path(self.config) else DEFAULT_SKIN
            save_config(self.config)
        if self.current_skin_key not in SKINS and self.current_skin_key not in (CUSTOM_SKIN_KEY, VIDEO_SKIN_KEY):
            self.current_skin_key = DEFAULT_SKIN
        self.skin_actions = {}
        self.custom_image_action = None
        self.clear_custom_image_action = None
        self.custom_video_action = None
        self.clear_custom_video_action = None
        self.background_pixmap = QPixmap()
        self.load_background_image()
        self.apply_skin(save=False)
        self.app_icon = QIcon(str(resource_path("app.ico")))
        if not self.app_icon.isNull():
            self.setWindowIcon(self.app_icon)
        self.video_player = None
        self.video_audio = None
        self.video_sink = None
        self.video_frame_image = QImage()
        self.last_video_frame_update = 0
        self.video_error = ""
        self.init_video_background()

        self.gpu_handle = None
        try:
            pynvml.nvmlInit()
            self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            log_event("NVML GPU initialized")
        except Exception as e:
            log_event(f"NVML init failed: {e}", e)

        self.gpu_samples = []
        self.gpu_window_seconds = 1.6

        self.last = psutil.disk_io_counters(perdisk=True)
        self.last_time = time.time()

        disk_counters = psutil.disk_io_counters(perdisk=True)
        drive_info = [drive for drive in get_drive_info() if drive["psutil"] in disk_counters]
        if not drive_info:
            drive_info = [
                {"psutil": name, "smart": f"\\\\.\\PHYSICALDRIVE{i}", "label": name, "index": i}
                for i, name in enumerate(disk_counters.keys())
            ]

        self.disks = [drive["psutil"] for drive in drive_info]
        self.labels = [drive["label"] for drive in drive_info]
        self.smart_paths = {drive["psutil"]: drive["smart"] for drive in drive_info}

        layout = QVBoxLayout(self)

        self.hint_label = QLabel("Press F1 to cycle display modes", self)
        self.hint_label.setStyleSheet(hint_style(skin_by_key(self.current_skin_key)))
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint_label)

        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.main_scroll.setAutoFillBackground(False)
        self.main_scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.main_scroll.viewport().setAutoFillBackground(False)
        self.main_scroll.setStyleSheet("""
            QScrollArea { border: 0; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
        """)

        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        container.setAutoFillBackground(False)
        container_layout = QVBoxLayout(container)
        top_grid = QGridLayout()
        drive_grid = QGridLayout()

        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(10)
        top_grid.setHorizontalSpacing(10)
        top_grid.setVerticalSpacing(10)
        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)
        top_grid.setColumnStretch(2, 1)
        drive_grid.setHorizontalSpacing(8)
        drive_grid.setVerticalSpacing(8)

        self.gpu = Gauge("GPU", preferred_size=250, minimum_size=80)
        self.ram = Gauge("RAM", preferred_size=250, minimum_size=80)
        self.cpu = Gauge("CPU", preferred_size=250, minimum_size=80)

        top_grid.addWidget(self.gpu, 0, 0)
        top_grid.addWidget(self.cpu, 0, 1)
        top_grid.addWidget(self.ram, 0, 2)

        container_layout.addLayout(top_grid, 3)

        self.disk_gauges = {}

        for i, d in enumerate(self.disks):
            g = Gauge(self.labels[i], preferred_size=178, minimum_size=64)
            g.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.disk_gauges[d] = g
            row = i // 4
            col = i % 4
            drive_grid.addWidget(g, row, col)

        for col in range(4):
            drive_grid.setColumnStretch(col, 1)

        container_layout.addLayout(drive_grid, 2)

        self.main_scroll.setWidget(container)
        layout.addWidget(self.main_scroll)
        self.sync_background_layers()

        detected_smart = detect_smart()
        self.smart_devices = {
            physicaldrive_index(device): (device, dtype)
            for device, dtype in detected_smart
        }
        self.smart_cache = {}
        self.last_smart = 0
        self.smart_worker = None

        self.rgb = RGBController()

        icon = self.app_icon if not self.app_icon.isNull() else self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray = QSystemTrayIcon(icon, self)

        menu = QMenu()
        show = QAction("Show", self)
        hide = QAction("Hide", self)
        exit = QAction("Exit", self)

        show.triggered.connect(self.show)
        hide.triggered.connect(self.hide)
        exit.triggered.connect(self.exit_app)

        menu.addAction(show)
        menu.addAction(hide)
        menu.addSeparator()

        skin_menu = menu.addMenu("Background Skin")
        self.skin_group = QActionGroup(self)
        self.skin_group.setExclusive(True)
        for key, skin in SKINS.items():
            action = QAction(skin["name"], self)
            action.setCheckable(True)
            action.setChecked(key == self.current_skin_key)
            action.triggered.connect(lambda checked=False, skin_key=key: self.set_skin(skin_key))
            self.skin_group.addAction(action)
            skin_menu.addAction(action)
            self.skin_actions[key] = action

        skin_menu.addSeparator()
        self.custom_image_action = QAction("Custom Image...", self)
        self.custom_image_action.setCheckable(True)
        self.custom_image_action.setChecked(self.current_skin_key == CUSTOM_SKIN_KEY)
        self.custom_image_action.triggered.connect(self.choose_custom_image)
        self.skin_group.addAction(self.custom_image_action)
        skin_menu.addAction(self.custom_image_action)

        self.clear_custom_image_action = QAction("Clear Custom Image", self)
        self.clear_custom_image_action.triggered.connect(self.clear_custom_image)
        skin_menu.addAction(self.clear_custom_image_action)

        skin_menu.addSeparator()
        self.custom_video_action = QAction("Custom Video unavailable", self)
        self.custom_video_action.setCheckable(True)
        self.custom_video_action.setChecked(self.current_skin_key == VIDEO_SKIN_KEY)
        self.custom_video_action.triggered.connect(self.choose_custom_video)
        self.skin_group.addAction(self.custom_video_action)
        skin_menu.addAction(self.custom_video_action)

        self.clear_custom_video_action = QAction("Clear Custom Video", self)
        self.clear_custom_video_action.triggered.connect(self.clear_custom_video)
        skin_menu.addAction(self.clear_custom_video_action)

        menu.addSeparator()
        menu.addAction(exit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.handle_tray_activated)
        self.tray.show()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.safe_update_stats)
        self.timer.start(REFRESH_MS)

        self.anim = QTimer(self)
        self.anim.timeout.connect(self.safe_animate)
        self.anim.start(10)

        self.display_mode = 0
        self._sync_modes()
        self.apply_skin(save=False)

        QTimer.singleShot(800, self._force_focus)
        log_event("System Gauges started")

    def apply_skin(self, save=True):
        skin = skin_by_key(self.current_skin_key)
        self.setStyleSheet(window_style(skin))
        is_image = self.using_rich_background()
        if hasattr(self, "gpu"):
            self.gpu.background_is_image = is_image
            self.ram.background_is_image = is_image
            self.cpu.background_is_image = is_image
            for gauge in self.disk_gauges.values():
                gauge.background_is_image = is_image
        if hasattr(self, "hint_label"):
            self.hint_label.setStyleSheet(hint_style(skin))
        if hasattr(self, "skin_actions"):
            for key, action in self.skin_actions.items():
                action.setChecked(key == self.current_skin_key)
        if hasattr(self, "custom_image_action") and self.custom_image_action:
            self.custom_image_action.setChecked(self.current_skin_key == CUSTOM_SKIN_KEY)
        if hasattr(self, "clear_custom_image_action") and self.clear_custom_image_action:
            has_custom = bool(custom_image_path(self.config))
            self.clear_custom_image_action.setEnabled(has_custom)
        if hasattr(self, "custom_video_action") and self.custom_video_action:
            self.custom_video_action.setChecked(self.current_skin_key == VIDEO_SKIN_KEY)
            self.custom_video_action.setEnabled(VIDEO_BACKGROUND_AVAILABLE)
        if hasattr(self, "clear_custom_video_action") and self.clear_custom_video_action:
            has_video = bool(custom_video_path(self.config))
            self.clear_custom_video_action.setEnabled(has_video)
        self.update_video_background()
        if save:
            self.config["skin"] = self.current_skin_key
            self.config["background_type"] = "video" if self.current_skin_key == VIDEO_SKIN_KEY else "image"
            save_config(self.config)
        self.sync_background_layers()
        self.update()

    def using_custom_image_background(self):
        return self.current_skin_key == CUSTOM_SKIN_KEY and not self.background_pixmap.isNull()

    def using_custom_video_background(self):
        return (
            self.current_skin_key == VIDEO_SKIN_KEY
            and VIDEO_BACKGROUND_AVAILABLE
            and bool(custom_video_path(self.config))
            and not getattr(self, "video_error", "")
        )

    def using_rich_background(self):
        return self.using_custom_image_background() or self.using_custom_video_background()

    def set_skin(self, skin_key):
        if skin_key not in SKINS:
            return
        self.current_skin_key = skin_key
        self.apply_skin(save=True)

    def load_background_image(self):
        path = custom_image_path(self.config)
        if path and path.exists():
            self.background_pixmap = QPixmap(str(path))
        else:
            self.background_pixmap = QPixmap()

    def init_video_background(self):
        if not VIDEO_BACKGROUND_AVAILABLE:
            log_event("Video background disabled because QtMultimedia was unstable in the packaged EXE")
            return
        self.video_audio = QAudioOutput(self)
        self.video_audio.setVolume(0)
        self.video_sink = QVideoSink(self)
        self.video_sink.videoFrameChanged.connect(self.handle_video_frame)
        self.video_player = QMediaPlayer(self)
        self.video_player.setAudioOutput(self.video_audio)
        self.video_player.setVideoSink(self.video_sink)
        self.video_player.mediaStatusChanged.connect(self.handle_video_status)
        self.video_player.errorOccurred.connect(self.handle_video_error)

    def update_video_background(self):
        if not VIDEO_BACKGROUND_AVAILABLE or not getattr(self, "video_player", None):
            return
        path = custom_video_path(self.config)
        should_play = self.current_skin_key == VIDEO_SKIN_KEY and path and path.exists()
        if not should_play:
            self.video_player.stop()
            self.video_frame_image = QImage()
            self.video_error = ""
            self.update()
            return
        self.video_error = ""
        self.video_player.setSource(QUrl.fromLocalFile(str(path)))
        self.video_audio.setMuted(True)
        self.video_audio.setVolume(0)
        self.video_player.play()

    def handle_video_frame(self, frame):
        if not frame.isValid():
            return
        now = time.monotonic()
        if now - self.last_video_frame_update < 1 / 30:
            return
        image = frame.toImage()
        if image.isNull():
            return
        self.video_frame_image = image.convertToFormat(QImage.Format.Format_RGB32).copy()
        self.last_video_frame_update = now
        self.update()

    def handle_video_status(self, status):
        if not VIDEO_BACKGROUND_AVAILABLE:
            return
        if (
            getattr(self, "video_player", None)
            and status == QMediaPlayer.MediaStatus.EndOfMedia
            and self.current_skin_key == VIDEO_SKIN_KEY
        ):
            self.video_player.setPosition(0)
            self.video_player.play()

    def handle_video_error(self, error, message):
        if not VIDEO_BACKGROUND_AVAILABLE:
            return
        if error == QMediaPlayer.Error.NoError:
            return
        self.video_error = message or str(error)
        log_event(f"Video background failed: {self.video_error}")
        if getattr(self, "video_player", None):
            self.video_player.stop()
        self.video_frame_image = QImage()
        self.current_skin_key = CUSTOM_SKIN_KEY if self.background_pixmap and not self.background_pixmap.isNull() else DEFAULT_SKIN
        self.apply_skin(save=True)

    def sync_background_layers(self):
        if hasattr(self, "hint_label"):
            self.hint_label.raise_()
        if hasattr(self, "main_scroll"):
            self.main_scroll.raise_()

    def choose_custom_image(self):
        start_dir = str(custom_image_path(self.config).parent) if custom_image_path(self.config) else str(Path.home())
        filename, _ = QFileDialog.getOpenFileName(self, "Choose Background Image", start_dir, CUSTOM_IMAGE_FILTER)
        if not filename:
            self.apply_skin(save=False)
            return
        self.config["custom_image_path"] = filename
        self.current_skin_key = CUSTOM_SKIN_KEY
        self.load_background_image()
        self.apply_skin(save=True)

    def choose_custom_video(self):
        if not VIDEO_BACKGROUND_AVAILABLE:
            self.current_skin_key = CUSTOM_SKIN_KEY if self.using_custom_image_background() else DEFAULT_SKIN
            self.config["background_type"] = "image"
            self.apply_skin(save=True)
            log_event("Custom video requested, but QtMultimedia video backgrounds are disabled")
            return
        start_dir = str(custom_video_path(self.config).parent) if custom_video_path(self.config) else str(Path.home())
        filename, _ = QFileDialog.getOpenFileName(self, "Choose Background Video", start_dir, CUSTOM_VIDEO_FILTER)
        if not filename:
            self.apply_skin(save=False)
            return
        self.config["custom_video_path"] = filename
        self.config["background_type"] = "video"
        self.current_skin_key = VIDEO_SKIN_KEY
        self.apply_skin(save=True)

    def clear_custom_image(self):
        self.config.pop("custom_image_path", None)
        self.background_pixmap = QPixmap()
        if self.current_skin_key == CUSTOM_SKIN_KEY:
            self.current_skin_key = DEFAULT_SKIN
        self.apply_skin(save=True)

    def clear_custom_video(self):
        self.config.pop("custom_video_path", None)
        if getattr(self, "video_player", None):
            self.video_player.stop()
        self.video_frame_image = QImage()
        if self.current_skin_key == VIDEO_SKIN_KEY:
            self.current_skin_key = CUSTOM_SKIN_KEY if self.using_custom_image_background() else DEFAULT_SKIN
        self.apply_skin(save=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_background_layers()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.current_skin_key == VIDEO_SKIN_KEY and not self.video_frame_image.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scaled = self.video_frame_image.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)
            painter.fillRect(self.rect(), QColor(10, 12, 14, VIDEO_OVERLAY_ALPHA))
        elif self.current_skin_key == CUSTOM_SKIN_KEY and not self.background_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scaled = self.background_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.fillRect(self.rect(), QColor(10, 12, 14, CUSTOM_IMAGE_OVERLAY_ALPHA))

    def _force_focus(self):
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        log_event("Window close requested; hiding to tray instead")

    def exit_app(self):
        log_event("Exit selected from tray menu")
        QApplication.quit()

    def handle_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.activateWindow()
            self.raise_()

    def _sync_modes(self):
        self.gpu.display_mode = self.display_mode
        self.ram.display_mode = self.display_mode
        self.cpu.display_mode = self.display_mode
        for g in self.disk_gauges.values():
            g.display_mode = self.display_mode
        self._update_hint_label()

    def _sync_page(self):
        self.main_scroll.show()
        self._update_hint_label()

    def _update_hint_label(self):
        modes = ["Classic", "Telemetry (pulse bars)", "Hybrid"]
        self.hint_label.setText(
            f"Current mode: {modes[self.display_mode]}   —   F1 cycles display modes"
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F1:
            self.display_mode = (self.display_mode + 1) % 3
            self._sync_modes()
            self.update()
            event.accept()
            return

        super().keyPressEvent(event)

    def refresh_smart(self):
        if self.smart_worker and self.smart_worker.isRunning():
            return

        disk_devices = []
        for d in self.disks:
            smart_path = self.smart_paths.get(d, "")
            index = physicaldrive_index(smart_path)
            device, dtype = self.smart_devices.get(index, (smart_path, None))
            if device:
                disk_devices.append((d, device, dtype))

        if not disk_devices:
            return

        self.smart_worker = SmartWorker(disk_devices, self.smart_cache)
        self.smart_worker.result_ready.connect(self._smart_finished)
        self.smart_worker.start()

    def _smart_finished(self, results):
        self.smart_cache.update(results)
        self.smart_worker = None

    def safe_animate(self):
        try:
            self.animate()
        except Exception as e:
            log_event(f"Animation update failed: {e}", e)

    def animate(self):
        self.gpu.tick()
        self.ram.tick()
        self.cpu.tick()
        for g in self.disk_gauges.values():
            g.tick()

    def safe_update_stats(self):
        try:
            self.update_stats()
        except Exception as e:
            log_event(f"Telemetry update failed: {e}", e)

    def update_stats(self):
        # GPU
        try:
            if self.gpu_handle:
                util = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
                temp = pynvml.nvmlDeviceGetTemperature(self.gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
                gpu_now = time.time()
                gpu_pct = max(int(util.gpu), int(util.memory))
                self.gpu_samples.append((gpu_now, gpu_pct))
                cutoff = gpu_now - self.gpu_window_seconds
                self.gpu_samples = [(t, v) for t, v in self.gpu_samples if t >= cutoff]
                gpu_display = max(v for t, v in self.gpu_samples) if self.gpu_samples else gpu_pct

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                vram_used_gb = mem_info.used / (1024 ** 3)
                vram_total_gb = mem_info.total / (1024 ** 3)
                power_w = pynvml.nvmlDeviceGetPowerUsage(self.gpu_handle) / 1000.0

                self.gpu.set_data(gpu_display, f"{gpu_display:.0f}%", f"{c_to_f(temp)}°F",
                                  f"VRAM {vram_used_gb:.1f}/{vram_total_gb:.1f} GB", f"{power_w:.0f} W")
            else:
                self.gpu.set_data(0, "0%", "N/A", "", "")
        except Exception as e:
            log_event(f"GPU update failed: {e}", e)
            self.gpu.set_data(0, "GPU Error", "", "", "")

        # CPU
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            freq = psutil.cpu_freq()
            freq_text = f"{freq.current / 1000:.2f} GHz" if freq else "Freq N/A"
            cores = psutil.cpu_count(logical=False) or 0
            threads = psutil.cpu_count(logical=True) or 0
            self.cpu.set_data(cpu_pct, f"{cpu_pct:.0f}%", freq_text, f"{cores}C / {threads}T", "CPU Load")
        except Exception as e:
            log_event(f"CPU update failed: {e}", e)
            cpu_pct = 0
            self.cpu.set_data(0, "CPU Error", "", "", "")

        # RAM
        try:
            mem = psutil.virtual_memory()
            used_gb = mem.used / (1024 ** 3)
            avail_gb = mem.available / (1024 ** 3)
            self.ram.set_data(mem.percent, f"{used_gb:.1f} GB", f"{mem.percent:.1f}%", f"Avail {avail_gb:.1f} GB")
        except:
            pass

        # Disks
        try:
            now = time.time()
            dt = now - self.last_time
            self.last_time = now
            cur = psutil.disk_io_counters(perdisk=True)

            if now - self.last_smart > SMART_REFRESH_SECONDS:
                self.refresh_smart()
                self.last_smart = now

            for d in self.disks:
                r = w = 0
                try:
                    r = ((cur[d].read_bytes - self.last[d].read_bytes) / 1024 / 1024) / dt
                    w = ((cur[d].write_bytes - self.last[d].write_bytes) / 1024 / 1024) / dt
                except:
                    pass

                total = max(0, r + w)
                pct = min(total / 500 * 100, 100)

                temp, health = self.smart_cache.get(d, UNKNOWN_SMART)

                self.disk_gauges[d].set_data(
                    pct,
                    format_speed(total),
                    format_temp(temp),
                    f"Health {health}",
                    ""
                )

            self.last = cur
        except Exception as e:
            log_event(f"Disk update failed: {e}", e)

        # RGB
        try:
            cpu = cpu_pct if 'cpu_pct' in locals() else psutil.cpu_percent(interval=None)
            gpu = gpu_display if 'gpu_display' in locals() else 0
            ram_pct = mem.percent if 'mem' in locals() else 0
            self.rgb.update(cpu, gpu, ram_pct)
        except:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = Monitor()
    window.resize(840, 540)
    window.show()
    window.activateWindow()
    window.raise_()
    window.setFocus()
    exit_code = app.exec()
    log_event(f"System Gauges exited with code {exit_code}")
    sys.exit(exit_code)
