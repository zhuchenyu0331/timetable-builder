from __future__ import annotations

from datetime import date

from PIL import Image

from timetable.exporter import export_project_png
from timetable.logic import ScheduleService
from timetable.models import Course, TimetableProject, WeekRule, default_periods
from timetable.storage import ProjectStore


def test_unicode_path_save_reload_and_export(tmp_path) -> None:
    project = TimetableProject(periods=default_periods())
    service = ScheduleService(project)
    item = Course("数据结构", "逸夫楼 302", WeekRule("odd", 1, 12), 2, "#61DDAA")
    service.add_course(item)
    service.place_course(item.id, 2, 2)

    json_path = tmp_path / "中文目录" / "我的课表.json"
    store = ProjectStore(json_path)
    store.save(project)
    restored = store.load()
    assert restored.courses[0].name == "数据结构"
    assert restored.courses[0].week_rule.label() == "1-12周单周"
    assert restored.placements[0].day == 2

    png_path = tmp_path / "中文桌面" / f"课表_{date.today():%Y-%m-%d}.png"
    export_project_png(restored, png_path)
    assert png_path.exists() and png_path.stat().st_size > 20_000
    with Image.open(png_path) as image:
        assert image.format == "PNG"
        assert image.width >= 3000
        assert image.info.get("dpi", (0, 0))[0] >= 190
