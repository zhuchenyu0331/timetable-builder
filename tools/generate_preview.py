"""生成 README 使用的真实应用界面截图。"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import ImageGrab

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from timetable.models import Course, WeekRule  # noqa: E402
from timetable.ui import MainWindow  # noqa: E402


def main() -> None:
    data_file = PROJECT_ROOT / "work" / "preview.json"
    app = MainWindow(data_file)
    app.geometry("1280x760+20+20")
    app.project.courses.clear()
    app.project.placements.clear()
    examples = [
        Course("高等数学", "教学楼 A101", WeekRule("odd", 1, 12), 2, "#5B8FF9"),
        Course("数据结构", "逸夫楼 302", WeekRule("range", 1, 16), 2, "#61DDAA"),
        Course("大学英语", "博学楼 B205", WeekRule("even", 2, 16), 2, "#F6BD16"),
        Course("艺术鉴赏", "艺术楼 2F", WeekRule("custom", weeks=[1, 3, 5, 8, 10]), 1, "#9270CA"),
    ]
    for item in examples:
        app.service.add_course(item)
    for course, day, period in ((examples[0], 0, 0), (examples[1], 2, 2), (examples[2], 4, 4), (examples[3], 6, 1)):
        app.service.place_course(course.id, day, period)
    app.refresh_all()
    app.update_idletasks()
    app.update()
    output = PROJECT_ROOT / "screenshots" / "app-preview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(window=app.winfo_id()).save(output)
    print(output)
    app.destroy()


if __name__ == "__main__":
    main()
