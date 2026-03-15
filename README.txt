# System Gauges

System Gauges is a lightweight Windows desktop application that provides real-time monitoring of your system's GPU, RAM, and disk drives through intuitive circular gauge visualizations. It displays utilization percentages, temperatures, health metrics, and other key stats in a clean, scrollable interface. The app runs in the system tray for easy access and minimization.

## Features

- **GPU Monitoring**: Shows GPU utilization (compute + memory), temperature (in °F), VRAM usage, and power draw. Supports NVIDIA GPUs only.
- **RAM Monitoring**: Displays used RAM (in GB), utilization percentage, and available RAM.
- **Disk Monitoring**: For each detected drive, shows combined read/write speed, temperature (in °F), SMART health percentage, and total lifetime writes (in TB). Drives are sorted by letter and labeled with their model.
- **System Tray Integration**: Minimize to tray with options to show/hide/exit.
- **SMART Support**: Parses disk health and temperature using SMART data (requires smartctl tool).
- **Smooth Animations**: Gauges animate smoothly with color-coded warnings (green <60%, yellow <85%, red >=85%).
- **Refresh Rate**: Updates every 400ms for real-time feel, with SMART data refreshed every 8 seconds to avoid excessive disk queries.

## Requirements

This tool is designed for **Windows** systems only (due to dependencies like WMI for drive labeling). It has been packaged as a standalone executable using PyInstaller for easy distribution without needing Python installed.

### Hardware/Software Prerequisites
- **Operating System**: Windows 10 or later (tested on Windows 11).
- **GPU**: NVIDIA GPU required for GPU monitoring (uses NVML library). AMD/Intel GPUs are not supported and may cause errors or blank GPU gauge.
- **Disks**: Supports SATA/SSD/NVMe drives with SMART capabilities. Non-SMART drives will show "?" for temperature, health, and writes.
- **External Tool**: [Smartmontools](https://www.smartmontools.org/) must be installed for SMART data (temperature, health, writes). Download the Windows installer from the official site and ensure `smartctl.exe` is in your system's PATH (e.g., installed to `C:\Program Files\smartmontools\bin`).
- **NVIDIA Drivers**: Latest NVIDIA drivers installed (required for pynvml to access GPU info).
- **Admin Privileges**: May require running as administrator for full SMART access on some systems (e.g., for NVMe drives).
- **No Internet Required**: Runs offline; all monitoring is local.

### For Developers (Running from Source)
If you're running the original `monitor.py` script instead of the EXE:
- Python 3.12+ (script uses Python 3.12 features implicitly).
- Install dependencies via pip:

(Note: `pywin32` includes WMI support; `pynvml` is NVIDIA's NVML Python bindings.)

## Installation

1. **Download the EXE**: Obtain the packaged executable (e.g., `Monitor.exe`) from the release or build it yourself (see below).
2. **Install Smartmontools**:
 - Download the Windows installer from [smartmontools.org](https://www.smartmontools.org/download.html).
 - Run the installer and add the `bin` folder to your system's PATH environment variable (restart your system or explorer if needed).
 - Verify installation: Open Command Prompt and run `smartctl --version`. It should output the version info.
3. **Run the EXE**: Double-click `SystemGauges.exe`. If SMART data shows "?", ensure smartctl is installed and accessible.
4. **Optional: Run as Admin**: Right-click the EXE and select "Run as administrator" if SMART queries fail.

### Building the EXE Yourself (with PyInstaller)
If you have the source code (`monitor.py`):
1. Install PyInstaller: `pip install pyinstaller`.
2. Run: `pyinstaller --onefile --windowed --name SystemGauges monitor.py`.
 - This creates a single EXE in the `dist` folder.
 - `--windowed` hides the console window.
 - Note: PyInstaller bundles Python and libraries, but **does not bundle external tools like smartctl**. Users still need to install it separately.
3. Test the EXE and distribute.

## Usage

1. Launch the application as Admin (no admin=no data) (EXE or script).
2. The main window opens with gauges for GPU, RAM, and each detected disk drive.
 - GPU gauge: Top-left.
 - RAM gauge: Top-right.
 - Disk gauges: Below, two per row, labeled with drive letters and models.
3. Minimize to system tray: Click the minimize button or right-click tray icon > Hide.
4. Restore: Right-click tray icon > Show.
5. Exit: Right-click tray icon > Exit.
6. Monitoring Notes:
 - Speeds are in MB/s (or GB/s/KB/s as appropriate).
 - Temperatures converted to °F (from °C).
 - Disk health is estimated from SMART "Percentage Used" or "PASSED" status.
 - Lifetime writes parsed from various SMART attributes (LBAs, sectors, etc.).

## Troubleshooting

- **GPU Gauge Blank or Errors**: Ensure you have an NVIDIA GPU and drivers installed. If using AMD/Intel, the GPU gauge will not function (consider commenting out GPU code in source).
- **SMART Data Shows "?"**: 
- Install smartctl and add to PATH.
- Run as admin.
- Verify with `smartctl -a /dev/sdX` in Command Prompt (replace `/dev/sdX` with your drive, e.g., `\\.\PhysicalDrive0`).
- **No Disk Labels**: WMI access issue; ensure running on Windows.
- **High CPU Usage**: Rare, but reduce refresh rate by increasing `REFRESH_MS` in source.
- **Crashes on Launch**: Missing dependencies in EXE build? Rebuild with PyInstaller and check console output (remove `--windowed` for debugging).
- **NVMe Support**: May require `-d nvme` in smartctl, but the script attempts multiple modes.

## Limitations

- Windows-only (WMI, smartctl Windows build).
- NVIDIA GPUs only.
- No configuration options (hardcoded refresh rates, °F units).
- SMART parsing is heuristic-based; may not work perfectly on all drives (fallbacks for various attribute formats).
- Does not monitor CPU or other components.

## Contributing

If you have improvements (e.g., AMD GPU support via other libs, configurable units), fork the repo and submit a PR. Source is in `monitor.py`.

## License

MIT License. Feel free to use, modify, and distribute.

## Credits

Built with PyQt6, psutil, pynvml, and smartmontools. Created by League of Creations.