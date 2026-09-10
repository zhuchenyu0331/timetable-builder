from __future__ import annotations

import argparse
from pathlib import Path

from timetable.ui import MainWindow


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = PROJECT_ROOT / "data" / "timetable.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="课表制作器 / Timetable Builder")
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE, help="项目 JSON 文件路径")
    parser.add_argument("--auto-close-ms", type=int, default=0, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = MainWindow(args.data_file.resolve())
    if args.auto_close_ms > 0:
        app.after(args.auto_close_ms, app.destroy)
    app.mainloop()


if __name__ == "__main__":
    main()
