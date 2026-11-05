"""
Start KaisenOS:  python run.py            (your data)
                 python run.py --demo     (made-up data in a temporary folder)

Always listens on 127.0.0.1 only (this computer). Refuses to run as
root/administrator, which it never needs.
"""

import argparse
import os
import shutil
import socket
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(os.environ.get("KAISEN_PORT", "8000"))
ROOT = Path(__file__).resolve().parent


def _port_free() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, PORT)) != 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Start KaisenOS on this computer.")
    parser.add_argument("--demo", action="store_true", help="use made-up demo data (your data is not touched)")
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = parser.parse_args()

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        print("Please don't run KaisenOS as root/administrator. It doesn't need it.")
        return 1

    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        print("The dashboard isn't built yet. Run ./setup.sh first.")
        return 1

    if not _port_free():
        print(f"Port {PORT} is already in use. Is KaisenOS already running? Open http://{HOST}:{PORT}")
        return 1

    demo_dir = None
    if args.demo:
        # Must be set before any app module is imported (they read it at import).
        # Clear leftovers from a demo that was force-quit, then make a fresh one.
        for old in Path(tempfile.gettempdir()).glob("KaisenOS-demo-*"):
            shutil.rmtree(old, ignore_errors=True)
        demo_dir = tempfile.mkdtemp(prefix="KaisenOS-demo-")
        os.environ["KAISEN_DATA_DIR"] = demo_dir

    sys.path.insert(0, str(ROOT))
    from src.paths import DATA_DIR, make_private  # noqa: E402

    make_private()
    if args.demo:
        from src import demo_data  # noqa: E402

        demo_data.seed()
        print("DEMO MODE: made-up data in a temporary folder (deleted when you stop). Your own data is not used.")
    else:
        print(f"Your data folder: {DATA_DIR}")

    url = f"http://{HOST}:{PORT}"
    print(f"KaisenOS is running at {url}  (press Ctrl+C to stop)")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn  # noqa: E402

    try:
        uvicorn.run("backend.main:app", host=HOST, port=PORT, log_level="warning")
    finally:
        if demo_dir:
            shutil.rmtree(demo_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
