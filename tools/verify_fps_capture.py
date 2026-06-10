import argparse
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from monitor import find_presentmon_executable, parse_presentmon_fps, presentmon_failure_message


def main():
    parser = argparse.ArgumentParser(description="Verify PresentMon can capture the local FPS wire test app.")
    parser.add_argument("--seconds", type=float, default=8, help="Capture duration.")
    parser.add_argument("--fps", type=int, default=120, help="FPS target for the render test.")
    args = parser.parse_args()

    presentmon = find_presentmon_executable()
    if not presentmon:
        print("FAIL: PresentMon console executable was not found.")
        return 2

    output_file = REPO_ROOT / "dist" / f"systemgauges-fps-verify-{int(time.time() * 1000)}.csv"
    packaged_app = REPO_ROOT / "dist" / "FpsWireTest.exe"
    if packaged_app.exists():
        app_command = [str(packaged_app), "--seconds", str(args.seconds + 4), "--fps", str(args.fps)]
    else:
        app_command = [
            sys.executable,
            str(REPO_ROOT / "tools" / "fps_wire_test.py"),
            "--seconds",
            str(args.seconds + 4),
            "--fps",
            str(args.fps),
        ]

    app = subprocess.Popen(app_command, cwd=str(REPO_ROOT))

    try:
        time.sleep(2)
        result = subprocess.run(
            [
                presentmon,
                "--output_file",
                str(output_file),
                "--session_name",
                "SystemGaugesVerify",
                "--set_circular_buffer_size",
                "65536",
                "--timed",
                str(args.seconds),
                "--terminate_after_timed",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.seconds + 8,
        )

        output = (result.stdout or "") + (result.stderr or "")
        reading = None
        if output_file.exists():
            reading = parse_presentmon_fps(output_file.read_text(encoding="utf-8", errors="ignore"))
        if not reading:
            print(f"FAIL: {presentmon_failure_message(output)}")
            if output.strip():
                print(output.strip())
            return 1

        print(f"PASS: {reading['application']} {reading['fps']:.1f} FPS over {reading['frames']} frames")
        return 0
    finally:
        if app.poll() is None:
            app.terminate()
            try:
                app.wait(timeout=3)
            except subprocess.TimeoutExpired:
                app.kill()
        try:
            output_file.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
