# System Gauges

System Gauges is a polished Windows desktop telemetry panel for CPU, GPU, RAM, and SMART-enabled storage. It uses animated circular gauges, adaptive sizing, and a compact `3 up top / 4 below` dashboard layout.

## Features

- CPU load, frequency, core/thread count, and usage gauge.
- NVIDIA GPU usage, temperature, VRAM, and power draw through NVML.
- RAM usage, available memory, and color-coded warning states.
- Drive activity, SMART temperature, and SMART health for SATA/SSD/NVMe drives.
- Smooth animated gauge rings with tracer effects.
- Resizable PyQt6 interface with system tray show/hide/exit actions.
- Background SMART polling so slow disk queries do not freeze the UI.

## Requirements

- Windows 10 or newer.
- Python 3.11+.
- NVIDIA GPU and current NVIDIA drivers for GPU telemetry.
- [smartmontools](https://www.smartmontools.org/) installed at `C:\Program Files\smartmontools\bin\smartctl.exe`.

Install Python dependencies:

```powershell
pip install PyQt6 psutil WMI pywin32 nvidia-ml-py openrgb-python
```

`openrgb-python` is optional. If OpenRGB is not installed/running, the monitor still works; RGB sync is skipped.

## Usage

From the repository folder:

```powershell
python -m monitor
```

Run as Administrator if SMART temperature or health is missing for some drives. Some Windows storage devices expose partial SMART data without admin rights, but full logs may require elevation.

Keyboard:

- `F1`: cycle Classic, Telemetry, and Hybrid display modes.

## Notes

- GPU telemetry is NVIDIA-only.
- SMART data is refreshed less often than CPU/GPU/RAM to avoid excessive disk queries.
- Drive tiles intentionally show activity speed, temperature, and health only.
- The `nvidia-ml-py` package is imported as `pynvml`; this is expected.

## Build EXE

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --name SystemGauges --icon app.ico --add-data "app.ico;." monitor.py
```

The finished executable will be created at `dist\SystemGauges.exe`.
