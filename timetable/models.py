from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


DAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


@dataclass(slots=True)
class Period:
    name: str
    start_time: str
    end_time: str
    id: str = field(default_factory=lambda: uuid4().hex)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Period":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name", "未命名节次")),
            start_time=str(data.get("start_time", "08:00")),
            end_time=str(data.get("end_time", "08:45")),
        )


@dataclass(slots=True)
class WeekRule:
    kind: str = "all"  # all | range | odd | even | custom
    start: int = 1
    end: int = 20
    weeks: list[int] = field(default_factory=list)

    def active_weeks(self, semester_weeks: int = 30) -> set[int]:
        maximum = max(1, semester_weeks)
        if self.kind == "all":
            return set(range(1, maximum + 1))
        if self.kind == "custom":
            return {w for w in self.weeks if 1 <= w <= maximum}
        begin = min(maximum, max(1, self.start))
        finish = min(maximum, max(1, self.end))
        begin, finish = sorted((begin, finish))
        values = range(begin, finish + 1)
        if self.kind == "odd":
            return {w for w in values if w % 2 == 1}
        if self.kind == "even":
            return {w for w in values if w % 2 == 0}
        return set(values)

    def label(self) -> str:
        if self.kind == "all":
            return "全部周次"
        if self.kind == "custom":
            return "、".join(str(w) for w in sorted(set(self.weeks))) + "周"
        base = f"{self.start}-{self.end}周"
        return base + ({"odd": "单周", "even": "双周"}.get(self.kind, ""))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeekRule":
        return cls(
            kind=str(data.get("kind", "all")),
            start=int(data.get("start", 1)),
            end=int(data.get("end", 20)),
            weeks=[int(w) for w in data.get("weeks", [])],
        )


@dataclass(slots=True)
class Course:
    name: str
    location: str
    week_rule: WeekRule
    duration: int
    color: str
    id: str = field(default_factory=lambda: uuid4().hex)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Course":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            name=str(data.get("name", "未命名课程")),
            location=str(data.get("location", "")),
            week_rule=WeekRule.from_dict(data.get("week_rule", {})),
            duration=max(1, int(data.get("duration", 1))),
            color=str(data.get("color", "#5B8FF9")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Placement:
    course_id: str
    day: int
    period: int
    id: str = field(default_factory=lambda: uuid4().hex)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Placement":
        return cls(
            id=str(data.get("id") or uuid4().hex),
            course_id=str(data.get("course_id", "")),
            day=int(data.get("day", 0)),
            period=int(data.get("period", 0)),
        )


@dataclass
class TimetableProject:
    periods: list[Period] = field(default_factory=list)
    courses: list[Course] = field(default_factory=list)
    placements: list[Placement] = field(default_factory=list)
    semester_weeks: int = 20
    version: int = 1

    def course_by_id(self, course_id: str) -> Course | None:
        return next((course for course in self.courses if course.id == course_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "semester_weeks": self.semester_weeks,
            "periods": [asdict(p) for p in self.periods],
            "courses": [c.to_dict() for c in self.courses],
            "placements": [asdict(p) for p in self.placements],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimetableProject":
        return cls(
            version=int(data.get("version", 1)),
            semester_weeks=max(1, int(data.get("semester_weeks", 20))),
            periods=[Period.from_dict(item) for item in data.get("periods", [])],
            courses=[Course.from_dict(item) for item in data.get("courses", [])],
            placements=[Placement.from_dict(item) for item in data.get("placements", [])],
        )


def default_periods() -> list[Period]:
    times = [
        ("第1节", "08:00", "08:45"), ("第2节", "08:55", "09:40"),
        ("第3节", "10:00", "10:45"), ("第4节", "10:55", "11:40"),
        ("第5节", "14:00", "14:45"), ("第6节", "14:55", "15:40"),
        ("第7节", "16:00", "16:45"), ("第8节", "16:55", "17:40"),
        ("第9节", "19:00", "19:45"), ("第10节", "19:55", "20:40"),
    ]
    return [Period(name, start, end) for name, start, end in times]
