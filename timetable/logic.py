from __future__ import annotations

import colorsys
from dataclasses import replace

from .models import Course, Placement, TimetableProject


COLOR_PALETTE = (
    "#5B8FF9", "#61DDAA", "#F6BD16", "#E8684A", "#6DC8EC",
    "#9270CA", "#FF9D4D", "#269A99", "#FF99C3", "#5D7092",
    "#B6D957", "#6F5EF9",
)


class ScheduleError(ValueError):
    """可直接显示给用户的排课错误。"""


class ScheduleService:
    def __init__(self, project: TimetableProject):
        self.project = project

    def next_color(self) -> str:
        used = [course.color.upper() for course in self.project.courses]
        for color in COLOR_PALETTE:
            if color.upper() not in used:
                return color
        # 色板用尽后，用黄金角生成彼此分散的颜色。
        hue = ((len(used) * 137.508) % 360) / 360
        red, green, blue = colorsys.hsv_to_rgb(hue, 0.52, 0.86)
        return f"#{round(red * 255):02X}{round(green * 255):02X}{round(blue * 255):02X}"

    def validate_course(self, course: Course) -> None:
        if not course.name.strip():
            raise ScheduleError("请输入课程名称。")
        if course.duration < 1:
            raise ScheduleError("持续节数必须大于 0。")
        if not course.week_rule.active_weeks(self.project.semester_weeks):
            raise ScheduleError("上课周次不能为空或超出学期范围。")

    def add_course(self, course: Course) -> None:
        self.validate_course(course)
        self.project.courses.append(course)

    def update_course(self, course: Course) -> None:
        self.validate_course(course)
        index = next((i for i, item in enumerate(self.project.courses) if item.id == course.id), -1)
        if index < 0:
            raise ScheduleError("找不到要编辑的课程。")
        old = self.project.courses[index]
        self.project.courses[index] = course
        try:
            for placement in self.project.placements:
                if placement.course_id == course.id:
                    self._validate_slot(course, placement.day, placement.period, placement.id)
        except ScheduleError:
            self.project.courses[index] = old
            raise

    def delete_course(self, course_id: str) -> None:
        self.project.courses = [c for c in self.project.courses if c.id != course_id]
        self.project.placements = [p for p in self.project.placements if p.course_id != course_id]

    def place_course(self, course_id: str, day: int, period: int) -> Placement:
        course = self.project.course_by_id(course_id)
        if course is None:
            raise ScheduleError("课程不存在。")
        self._validate_slot(course, day, period)
        placement = Placement(course_id=course_id, day=day, period=period)
        self.project.placements.append(placement)
        return placement

    def move_placement(self, placement_id: str, day: int, period: int) -> None:
        placement = next((p for p in self.project.placements if p.id == placement_id), None)
        if placement is None:
            raise ScheduleError("找不到要移动的课程。")
        course = self.project.course_by_id(placement.course_id)
        if course is None:
            raise ScheduleError("课程数据已损坏。")
        self._validate_slot(course, day, period, placement.id)
        placement.day = day
        placement.period = period

    def delete_placement(self, placement_id: str) -> None:
        self.project.placements = [p for p in self.project.placements if p.id != placement_id]

    def _validate_slot(
        self, course: Course, day: int, period: int, ignore_placement_id: str | None = None
    ) -> None:
        if not 0 <= day < 7:
            raise ScheduleError("星期位置无效。")
        if period < 0 or period + course.duration > len(self.project.periods):
            raise ScheduleError("课程持续节数超出当前课表范围。")
        incoming_periods = set(range(period, period + course.duration))
        incoming_weeks = course.week_rule.active_weeks(self.project.semester_weeks)
        for existing in self.project.placements:
            if existing.id == ignore_placement_id or existing.day != day:
                continue
            other = self.project.course_by_id(existing.course_id)
            if other is None:
                continue
            occupied = set(range(existing.period, existing.period + other.duration))
            overlapping_weeks = incoming_weeks & other.week_rule.active_weeks(self.project.semester_weeks)
            if incoming_periods & occupied and overlapping_weeks:
                weeks = "、".join(map(str, sorted(overlapping_weeks)[:6]))
                suffix = "…" if len(overlapping_weeks) > 6 else ""
                raise ScheduleError(f"与“{other.name}”时间冲突（第 {weeks}{suffix} 周）。")

    def clone_course(self, course_id: str) -> Course:
        course = self.project.course_by_id(course_id)
        if course is None:
            raise ScheduleError("课程不存在。")
        return replace(course)
