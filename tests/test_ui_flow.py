from __future__ import annotations

from pathlib import Path

import pytest

from timetable.logic import ScheduleError
from timetable.models import Course, Period, WeekRule
from timetable.storage import ProjectStore
from timetable.ui import MainWindow


@pytest.mark.ui
def test_complete_editing_flow(tmp_path, monkeypatch) -> None:
    """不阻塞窗口的 UI 集成流程：增删、排课、编辑、保存、恢复、导出、冲突。"""
    monkeypatch.setattr("timetable.ui.messagebox.showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr("timetable.ui.messagebox.showinfo", lambda *args, **kwargs: None)
    data_file = tmp_path / "项目数据" / "timetable.json"
    app = MainWindow(data_file)
    app.withdraw()
    app.project.periods.append(Period("晚间加课", "21:00", "21:45"))  # 创建节次

    math = Course("高等数学", "教学楼 A101", WeekRule("odd", 1, 12), 2, "#5B8FF9")
    art = Course("艺术鉴赏", "艺术楼 2F", WeekRule("custom", weeks=[1, 3, 5, 8, 10]), 1, "#61DDAA")
    app.service.add_course(math)
    app.service.add_course(art)
    assert app.place_course(math.id, 2, 2)  # 周三第3节，两节连堂
    assert app.place_course(art.id, 6, 0)  # 周末课程

    edited = Course(math.name, "综合楼 305", math.week_rule, 2, "#E8684A", math.id)
    app.service.update_course(edited)  # 编辑地点与颜色
    with pytest.raises(ScheduleError, match="时间冲突"):
        app.service.place_course(math.id, 2, 3)

    assert app.save_project(quiet=True)
    png = app.export_png(tmp_path / "桌面" / "课表_测试.png", quiet=True)
    assert png and png.exists()
    app.destroy()

    restored = ProjectStore(data_file).load()  # 模拟关闭并重新打开
    assert restored.course_by_id(math.id).location == "综合楼 305"
    assert restored.course_by_id(math.id).color == "#E8684A"
    assert len(restored.placements) == 2
    restored.placements.pop()  # 删除单次安排
    Schedule = type(app.service)
    service = Schedule(restored)
    service.delete_course(math.id)  # 删除课程
    assert restored.course_by_id(math.id) is None
    assert all(p.course_id != math.id for p in restored.placements)
