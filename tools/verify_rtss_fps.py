import argparse
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor import find_rtss_executable, is_rtss_running, read_rtss_fps, start_rtss_if_available


def launch_wire_test(fps):
    exe = ROOT / "dist" / "FpsWireTest.exe"
    if exe.exists():
        return subprocess.Popen([str(exe), "--fps", str(fps)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.Popen(
        [sys.executable, str(ROOT / "tools" / "fps_wire_test.py"), "--fps", str(fps)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main():
    parser = argparse.ArgumentParser(description="Verify RTSS shared-memory FPS capture with the local wire test app.")
    parser.add_argument("--seconds", type=int, default=15, help="How long to wait for RTSS to publish FPS.")
    parser.add_argument("--fps", type=int, default=120, help="FPS target for the render test.")
    args = parser.parse_args()

    rtss_path = find_rtss_executable()
    if not rtss_path:
        print("FAIL: RTSS is not installed. Install with: winget install --id Guru3D.RTSS --exact")
        return 1

    if not is_rtss_running():
        if not start_rtss_if_available(rtss_path):
            print(f"FAIL: RTSS is installed but not running: {rtss_path}")
            print("Start RTSS as administrator, then rerun this verifier.")
            return 1
        time.sleep(3)

    if not is_rtss_running():
        print("FAIL: RTSS did not stay running. Start it as administrator, then rerun this verifier.")
        return 1

    proc = launch_wire_test(args.fps)
    try:
        deadline = time.time() + args.seconds
        while time.time() < deadline:
            time.sleep(1)
            reading = read_rtss_fps()
            if reading:
                print(f"PASS: {reading['application']} {reading['fps']:.1f} FPS via RTSS")
                return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("FAIL: RTSS is running, but no FPS rows were published for the wire test.")
    print("Open RTSS and make sure application detection is enabled, then rerun this verifier.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
