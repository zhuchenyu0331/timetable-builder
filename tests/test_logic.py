from __future__ import annotations

import pytest

from timetable.logic import COLOR_PALETTE, ScheduleError, ScheduleService
from timetable.models import Course, TimetableProject, WeekRule, default_periods


def course(name: str, rule: WeekRule | None = None, duration: int = 2) -> Course:
    return Course(name, "教学楼 A101", rule or WeekRule(), duration, "#5B8FF9")


def test_week_rule_labels_and_sets() -> None:
    assert WeekRule("all").active_weeks(4) == {1, 2, 3, 4}
    assert WeekRule("range", 2, 4).active_weeks(20) == {2, 3, 4}
    assert WeekRule("odd", 1, 12).active_weeks(20) == {1, 3, 5, 7, 9, 11}
    assert WeekRule("even", 2, 16).active_weeks(20) == {2, 4, 6, 8, 10, 12, 14, 16}
    assert WeekRule("custom", weeks=[1, 3, 5, 8, 10]).label() == "1、3、5、8、10周"


def test_duration_and_conflict_detection() -> None:
    project = TimetableProject(periods=default_periods())
    service = ScheduleService(project)
    calculus = course("高等数学", WeekRule("odd", 1, 12), 2)
    physics = course("大学物理", WeekRule("even", 2, 16), 2)
    service.add_course(calculus)
    service.add_course(physics)
    service.place_course(calculus.id, 2, 2)
    # 相同时间、不同单双周不冲突。
    service.place_course(physics.id, 2, 2)
    conflict = course("线性代数", WeekRule("odd", 1, 12), 1)
    service.add_course(conflict)
    with pytest.raises(ScheduleError, match="时间冲突"):
        service.place_course(conflict.id, 2, 3)
    with pytest.raises(ScheduleError, match="超出"):
        service.place_course(calculus.id, 0, len(project.periods) - 1)


def test_edit_rolls_back_when_duration_creates_conflict() -> None:
    project = TimetableProject(periods=default_periods())
    service = ScheduleService(project)
    first, second = course("课程一", duration=1), course("课程二", duration=1)
    service.add_course(first)
    service.add_course(second)
    service.place_course(first.id, 0, 0)
    service.place_course(second.id, 0, 1)
    changed = Course(first.name, first.location, first.week_rule, 2, "#FF0000", first.id)
    with pytest.raises(ScheduleError, match="时间冲突"):
        service.update_course(changed)
    assert project.course_by_id(first.id).duration == 1
    assert project.course_by_id(first.id).color == "#5B8FF9"


def test_course_delete_removes_placements() -> None:
    project = TimetableProject(periods=default_periods())
    service = ScheduleService(project)
    item = course("待删除")
    service.add_course(item)
    service.place_course(item.id, 6, 0)
    service.delete_course(item.id)
    assert project.courses == []
    assert project.placements == []


def test_colors_are_varied_before_reuse() -> None:
    project = TimetableProject(periods=default_periods())
    service = ScheduleService(project)
    colors = []
    for index in range(len(COLOR_PALETTE)):
        color_value = service.next_color()
        colors.append(color_value)
        service.add_course(Course(f"课程 {index}", "", WeekRule(), 1, color_value))
    assert colors == list(COLOR_PALETTE)
