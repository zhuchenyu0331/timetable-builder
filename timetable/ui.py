from __future__ import annotations

import re
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk
from typing import Callable

from .exporter import ExportError, default_export_path, export_project_png
from .logic import ScheduleError, ScheduleService
from .models import DAYS, Course, Period, TimetableProject, WeekRule
from .storage import ProjectStore, StorageError


BG = "#F4F6FA"
PANEL = "#FFFFFF"
TEXT = "#1F2937"
MUTED = "#718096"
PRIMARY = "#4F6EF7"
BORDER = "#DDE3ED"


def contrast_text(hex_color: str) -> str:
    try:
        value = hex_color.lstrip("#")
        r, g, b = (int(value[i : i + 2], 16) for i in (0, 2, 4))
        return "#1F2937" if (r * 299 + g * 587 + b * 114) / 1000 > 168 else "#FFFFFF"
    except (ValueError, TypeError):
        return "#FFFFFF"


class CourseDialog(tk.Toplevel):
    KIND_LABELS = {
        "全部周次": "all", "指定范围": "range", "范围内单周": "odd",
        "范围内双周": "even", "自定义周次": "custom",
    }

    def __init__(self, parent: tk.Misc, semester_weeks: int, color: str, course: Course | None = None):
        super().__init__(parent)
        self.result: Course | None = None
        self.course = course
        self.semester_weeks = semester_weeks
        self.color = course.color if course else color
        self.title("编辑课程" if course else "创建课程")
        self.geometry("470x525")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=BG)

        body = ttk.Frame(self, padding=24)
        body.pack(fill="both", expand=True)
        self.name_var = tk.StringVar(value=course.name if course else "")
        self.location_var = tk.StringVar(value=course.location if course else "")
        self.duration_var = tk.StringVar(value=str(course.duration if course else 2))
        reverse = {value: key for key, value in self.KIND_LABELS.items()}
        self.kind_var = tk.StringVar(value=reverse.get(course.week_rule.kind, "全部周次") if course else "全部周次")
        self.start_var = tk.StringVar(value=str(course.week_rule.start if course else 1))
        self.end_var = tk.StringVar(value=str(course.week_rule.end if course else semester_weeks))
        custom = "、".join(map(str, course.week_rule.weeks)) if course else "1、3、5"
        self.custom_var = tk.StringVar(value=custom)

        ttk.Label(body, text="课程名称 *").pack(anchor="w")
        name_entry = ttk.Entry(body, textvariable=self.name_var)
        name_entry.pack(fill="x", pady=(5, 14))
        ttk.Label(body, text="上课地点").pack(anchor="w")
        ttk.Entry(body, textvariable=self.location_var).pack(fill="x", pady=(5, 14))

        row = ttk.Frame(body)
        row.pack(fill="x")
        left, right = ttk.Frame(row), ttk.Frame(row)
        left.pack(side="left", fill="x", expand=True, padx=(0, 8))
        right.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ttk.Label(left, text="持续节数 *").pack(anchor="w")
        ttk.Spinbox(left, from_=1, to=20, textvariable=self.duration_var).pack(fill="x", pady=(5, 14))
        ttk.Label(right, text="课程颜色").pack(anchor="w")
        color_row = ttk.Frame(right)
        color_row.pack(fill="x", pady=(5, 14))
        self.color_swatch = tk.Label(color_row, bg=self.color, width=5, height=1, relief="flat")
        self.color_swatch.pack(side="left", ipady=4)
        ttk.Button(color_row, text="选择颜色", command=self.choose_color).pack(side="left", padx=8)

        ttk.Label(body, text="上课周次 *").pack(anchor="w")
        kind_box = ttk.Combobox(body, values=list(self.KIND_LABELS), textvariable=self.kind_var, state="readonly")
        kind_box.pack(fill="x", pady=(5, 10))
        kind_box.bind("<<ComboboxSelected>>", lambda _event: self.update_week_fields())

        self.range_frame = ttk.Frame(body)
        ttk.Label(self.range_frame, text="从第").pack(side="left")
        ttk.Spinbox(self.range_frame, from_=1, to=semester_weeks, width=7, textvariable=self.start_var).pack(side="left", padx=6)
        ttk.Label(self.range_frame, text="周 到第").pack(side="left")
        ttk.Spinbox(self.range_frame, from_=1, to=semester_weeks, width=7, textvariable=self.end_var).pack(side="left", padx=6)
        ttk.Label(self.range_frame, text="周").pack(side="left")
        self.custom_frame = ttk.Frame(body)
        ttk.Entry(self.custom_frame, textvariable=self.custom_var).pack(fill="x")
        ttk.Label(self.custom_frame, text="用逗号、顿号或空格分隔，例如：1、3、5、8、10", foreground=MUTED).pack(anchor="w", pady=(5, 0))

        buttons = ttk.Frame(body)
        buttons.pack(side="bottom", fill="x", pady=(20, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="保存课程", style="Accent.TButton", command=self.submit).pack(side="right", padx=8)
        self.update_week_fields()
        self.bind("<Return>", lambda _event: self.submit())
        self.bind("<Escape>", lambda _event: self.destroy())
        name_entry.focus_set()
        self.wait_visibility()

    def choose_color(self) -> None:
        selected = colorchooser.askcolor(self.color, title="选择课程颜色", parent=self)[1]
        if selected:
            self.color = selected.upper()
            self.color_swatch.configure(bg=self.color)

    def update_week_fields(self) -> None:
        self.range_frame.pack_forget()
        self.custom_frame.pack_forget()
        kind = self.KIND_LABELS[self.kind_var.get()]
        if kind in {"range", "odd", "even"}:
            self.range_frame.pack(fill="x", pady=(0, 12))
        elif kind == "custom":
            self.custom_frame.pack(fill="x", pady=(0, 12))

    def submit(self) -> None:
        try:
            duration = int(self.duration_var.get())
            if not 1 <= duration <= 20:
                raise ValueError
            kind = self.KIND_LABELS[self.kind_var.get()]
            start, end, weeks = 1, self.semester_weeks, []
            if kind in {"range", "odd", "even"}:
                start, end = int(self.start_var.get()), int(self.end_var.get())
                if not 1 <= start <= end <= self.semester_weeks:
                    raise ScheduleError(f"周次范围应在 1-{self.semester_weeks} 周内，且开始周不晚于结束周。")
            elif kind == "custom":
                parts = [part for part in re.split(r"[,，、\s]+", self.custom_var.get().strip()) if part]
                weeks = sorted({int(part) for part in parts})
                if not weeks or weeks[0] < 1 or weeks[-1] > self.semester_weeks:
                    raise ScheduleError(f"自定义周次应在 1-{self.semester_weeks} 周内。")
            name = self.name_var.get().strip()
            if not name:
                raise ScheduleError("请输入课程名称。")
            self.result = Course(
                id=self.course.id if self.course else None,  # type: ignore[arg-type]
                name=name,
                location=self.location_var.get().strip(),
                week_rule=WeekRule(kind=kind, start=start, end=end, weeks=weeks),
                duration=duration,
                color=self.color,
            ) if self.course else Course(
                name=name, location=self.location_var.get().strip(),
                week_rule=WeekRule(kind=kind, start=start, end=end, weeks=weeks),
                duration=duration, color=self.color,
            )
        except ValueError:
            messagebox.showwarning("输入有误", "持续节数和周次必须是有效整数。", parent=self)
            return
        except ScheduleError as exc:
            messagebox.showwarning("输入有误", str(exc), parent=self)
            return
        self.destroy()


class PeriodDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, periods: list[Period]):
        super().__init__(parent)
        self.result: list[Period] | None = None
        self.periods = [Period(p.name, p.start_time, p.end_time, p.id) for p in periods]
        self.title("节次设置")
        self.geometry("610x520")
        self.transient(parent)
        self.grab_set()
        self.configure(bg=BG)

        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="设置全周共用的节次名称与时间", style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        columns = ("name", "start", "end")
        self.tree = ttk.Treeview(body, columns=columns, show="headings", height=12, selectmode="browse")
        for key, title, width in (("name", "节次名称", 200), ("start", "开始时间", 130), ("end", "结束时间", 130)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected())
        self.refresh()

        actions = ttk.Frame(body)
        actions.pack(fill="x", pady=12)
        ttk.Button(actions, text="＋ 添加节次", command=self.add_period).pack(side="left")
        ttk.Button(actions, text="编辑", command=self.edit_selected).pack(side="left", padx=8)
        ttk.Button(actions, text="删除", command=self.delete_selected).pack(side="left")
        ttk.Button(actions, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="应用设置", style="Accent.TButton", command=self.submit).pack(side="right", padx=8)

    def refresh(self, selected: int | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, period in enumerate(self.periods):
            item = self.tree.insert("", "end", iid=str(index), values=(period.name, period.start_time, period.end_time))
            if selected == index:
                self.tree.selection_set(item)

    def selected_index(self) -> int | None:
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def edit_form(self, title: str, period: Period | None = None) -> Period | None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("350x265")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        name = tk.StringVar(value=period.name if period else f"第{len(self.periods) + 1}节")
        start = tk.StringVar(value=period.start_time if period else "08:00")
        end = tk.StringVar(value=period.end_time if period else "08:45")
        for label, variable in (("节次名称", name), ("开始时间（HH:MM）", start), ("结束时间（HH:MM）", end)):
            ttk.Label(frame, text=label).pack(anchor="w")
            ttk.Entry(frame, textvariable=variable).pack(fill="x", pady=(3, 9))
        result: list[Period] = []

        def save() -> None:
            time_pattern = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
            if not name.get().strip() or not time_pattern.match(start.get()) or not time_pattern.match(end.get()):
                messagebox.showwarning("输入有误", "请填写节次名称，并使用 HH:MM 格式的时间。", parent=dialog)
                return
            if start.get() >= end.get():
                messagebox.showwarning("输入有误", "结束时间必须晚于开始时间。", parent=dialog)
                return
            if period:
                result.append(Period(name.get().strip(), start.get(), end.get(), period.id))
            else:
                result.append(Period(name.get().strip(), start.get(), end.get()))
            dialog.destroy()

        ttk.Button(frame, text="确定", style="Accent.TButton", command=save).pack(side="right", pady=4)
        ttk.Button(frame, text="取消", command=dialog.destroy).pack(side="right", padx=8, pady=4)
        dialog.bind("<Return>", lambda _event: save())
        dialog.wait_window()
        return result[0] if result else None

    def add_period(self) -> None:
        period = self.edit_form("添加节次")
        if period:
            self.periods.append(period)
            self.refresh(len(self.periods) - 1)

    def edit_selected(self) -> None:
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("提示", "请先选择一个节次。", parent=self)
            return
        period = self.edit_form("编辑节次", self.periods[index])
        if period:
            self.periods[index] = period
            self.refresh(index)

    def delete_selected(self) -> None:
        index = self.selected_index()
        if index is None:
            messagebox.showinfo("提示", "请先选择一个节次。", parent=self)
            return
        self.periods.pop(index)
        self.refresh(min(index, len(self.periods) - 1) if self.periods else None)

    def submit(self) -> None:
        self.result = self.periods
        self.destroy()


class TimetableCanvas(ttk.Frame):
    LABEL_WIDTH = 100
    DAY_WIDTH = 119
    HEADER_HEIGHT = 58
    ROW_HEIGHT = 98

    def __init__(self, parent: tk.Misc, app: "MainWindow"):
        super().__init__(parent)
        self.app = app
        self.canvas = tk.Canvas(self, bg=PANEL, highlightthickness=0)
        xscroll = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self._drag_placement_id: str | None = None
        self._press_xy = (0, 0)
        self.context = tk.Menu(self, tearoff=False)
        self.context.add_command(label="编辑课程", command=self._context_edit)
        self.context.add_command(label="修改颜色", command=self._context_color)
        self.context.add_separator()
        self.context.add_command(label="从课表删除", command=self._context_delete)
        self._context_placement_id: str | None = None
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self.redraw()

    @property
    def grid_width(self) -> int:
        return self.LABEL_WIDTH + self.DAY_WIDTH * 7

    @property
    def grid_height(self) -> int:
        return self.HEADER_HEIGHT + self.ROW_HEIGHT * len(self.app.project.periods)

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def redraw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        periods = self.app.project.periods
        height = max(self.grid_height, 300)
        canvas.configure(scrollregion=(0, 0, self.grid_width, height))
        canvas.create_rectangle(0, 0, self.grid_width, self.HEADER_HEIGHT, fill="#EEF3FF", outline="")
        canvas.create_text(self.LABEL_WIDTH / 2, self.HEADER_HEIGHT / 2, text="节次 / 时间", fill=TEXT, font=("Microsoft YaHei UI", 10, "bold"))
        for day, label in enumerate(DAYS):
            x = self.LABEL_WIDTH + day * self.DAY_WIDTH
            canvas.create_text(x + self.DAY_WIDTH / 2, self.HEADER_HEIGHT / 2, text=label, fill=TEXT, font=("Microsoft YaHei UI", 11, "bold"))
        if not periods:
            canvas.create_text(self.grid_width / 2, 180, text="还没有节次\n请点击右上角“节次设置”开始", justify="center", fill=MUTED, font=("Microsoft YaHei UI", 13))
            return
        for row, period in enumerate(periods):
            y = self.HEADER_HEIGHT + row * self.ROW_HEIGHT
            fill = "#FAFBFD" if row % 2 == 0 else "#FFFFFF"
            canvas.create_rectangle(0, y, self.grid_width, y + self.ROW_HEIGHT, fill=fill, outline="")
            canvas.create_text(self.LABEL_WIDTH / 2, y + 35, text=period.name, fill=TEXT, font=("Microsoft YaHei UI", 10, "bold"))
            canvas.create_text(self.LABEL_WIDTH / 2, y + 61, text=f"{period.start_time} - {period.end_time}", fill=MUTED, font=("Microsoft YaHei UI", 8))
        for x in (0, self.LABEL_WIDTH, *[self.LABEL_WIDTH + i * self.DAY_WIDTH for i in range(1, 8)]):
            canvas.create_line(x, 0, x, self.grid_height, fill=BORDER)
        for row in range(len(periods) + 1):
            y = self.HEADER_HEIGHT + row * self.ROW_HEIGHT
            canvas.create_line(0, y, self.grid_width, y, fill=BORDER)
        for placement in self.app.project.placements:
            self.draw_placement(placement)

    def draw_placement(self, placement) -> None:
        course = self.app.project.course_by_id(placement.course_id)
        if course is None or placement.period >= len(self.app.project.periods) or not 0 <= placement.day < 7:
            return
        duration = min(course.duration, len(self.app.project.periods) - placement.period)
        x0 = self.LABEL_WIDTH + placement.day * self.DAY_WIDTH + 6
        y0 = self.HEADER_HEIGHT + placement.period * self.ROW_HEIGHT + 6
        x1 = x0 + self.DAY_WIDTH - 12
        y1 = y0 + duration * self.ROW_HEIGHT - 12
        tag = f"placement:{placement.id}"
        canvas = self.canvas
        canvas.create_rectangle(x0, y0, x1, y1, fill=course.color, outline="", width=0, tags=(tag, "course-card"))
        text_color = contrast_text(course.color)
        usable = max(1, int((x1 - x0 - 18) / 13))
        name = course.name if len(course.name) <= usable else course.name[: usable - 1] + "…"
        detail = f"{course.location or '地点未填写'}\n{course.week_rule.label()}\n{course.duration} 节"
        canvas.create_text(x0 + 10, y0 + 12, text=name, anchor="nw", width=x1 - x0 - 20, fill=text_color, font=("Microsoft YaHei UI", 10, "bold"), tags=(tag, "course-card"))
        canvas.create_text(x0 + 10, y0 + 42, text=detail, anchor="nw", width=x1 - x0 - 20, fill=text_color, font=("Microsoft YaHei UI", 8), tags=(tag, "course-card"))
        canvas.tag_bind(tag, "<ButtonPress-1>", lambda event, pid=placement.id: self._placement_press(event, pid))
        canvas.tag_bind(tag, "<Double-1>", lambda _event, cid=course.id: self.app.edit_course(cid))
        canvas.tag_bind(tag, "<Button-3>", lambda event, pid=placement.id: self._show_context(event, pid))

    def _placement_press(self, event: tk.Event, placement_id: str) -> None:
        self._drag_placement_id = placement_id
        self._press_xy = (event.x_root, event.y_root)
        self.canvas.configure(cursor="fleur")

    def _canvas_release(self, event: tk.Event) -> None:
        self.canvas.configure(cursor="")
        placement_id = self._drag_placement_id
        if not placement_id:
            return
        self._drag_placement_id = None
        if abs(event.x_root - self._press_xy[0]) + abs(event.y_root - self._press_xy[1]) < 5:
            return
        cell = self.cell_from_root(event.x_root, event.y_root)
        if cell is not None:
            self.app.move_placement(placement_id, *cell)

    def _show_context(self, event: tk.Event, placement_id: str) -> None:
        self._context_placement_id = placement_id
        self.context.tk_popup(event.x_root, event.y_root)

    def _context_edit(self) -> None:
        placement = next((p for p in self.app.project.placements if p.id == self._context_placement_id), None)
        if placement:
            self.app.edit_course(placement.course_id)

    def _context_color(self) -> None:
        placement = next((p for p in self.app.project.placements if p.id == self._context_placement_id), None)
        if placement:
            self.app.change_course_color(placement.course_id)

    def _context_delete(self) -> None:
        if self._context_placement_id:
            self.app.delete_placement(self._context_placement_id)

    def cell_from_root(self, root_x: int, root_y: int) -> tuple[int, int] | None:
        local_x = self.canvas.canvasx(root_x - self.canvas.winfo_rootx())
        local_y = self.canvas.canvasy(root_y - self.canvas.winfo_rooty())
        day = int((local_x - self.LABEL_WIDTH) // self.DAY_WIDTH)
        period = int((local_y - self.HEADER_HEIGHT) // self.ROW_HEIGHT)
        if 0 <= day < 7 and 0 <= period < len(self.app.project.periods):
            return day, period
        return None


class MainWindow(tk.Tk):
    def __init__(self, data_file: Path):
        super().__init__()
        self.data_file = data_file
        self.store = ProjectStore(data_file)
        self.load_error: str | None = None
        try:
            self.project = self.store.load()
        except StorageError as exc:
            self.project = TimetableProject()
            self.load_error = str(exc)
        self.service = ScheduleService(self.project)
        self.dirty = False
        self.drag_window: tk.Toplevel | None = None
        self.drag_course_id: str | None = None
        self.title("课表制作器 · Timetable Builder")
        self.geometry("1440x850")
        self.minsize(1020, 640)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._configure_style()
        self._build_ui()
        self.refresh_all()
        self.bind("<Control-s>", lambda _event: self.save_project())
        if self.load_error:
            self.after(200, lambda: messagebox.showwarning("项目读取失败", self.load_error + "\n已创建空白课表，原文件未被修改。", parent=self))

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 9), background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Heading.TLabel", font=("Microsoft YaHei UI", 13, "bold"), foreground=TEXT)
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 18, "bold"), foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", padding=(12, 8), borderwidth=0)
        style.configure("Accent.TButton", background=PRIMARY, foreground="#FFFFFF")
        style.map("Accent.TButton", background=[("active", "#3D5BE0")], foreground=[("disabled", "#CBD5E1")])
        style.configure("Treeview", rowheight=31, background=PANEL, fieldbackground=PANEL)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(22, 16))
        header.pack(fill="x")
        title_wrap = ttk.Frame(header)
        title_wrap.pack(side="left")
        ttk.Label(title_wrap, text="课表制作器", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_wrap, text="拖动课程卡片，轻松安排一周课程", style="Muted.TLabel").pack(anchor="w")
        ttk.Button(header, text="导出课表图片", style="Accent.TButton", command=self.export_png).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="保存项目", command=self.save_project).pack(side="right", padx=8)
        ttk.Button(header, text="节次设置", command=self.edit_periods).pack(side="right")

        main = ttk.Frame(self, padding=(22, 0, 22, 12))
        main.pack(fill="both", expand=True)
        sidebar = ttk.Frame(main, style="Panel.TFrame", padding=16, width=270)
        sidebar.pack(side="left", fill="y", padx=(0, 14))
        sidebar.pack_propagate(False)
        top = ttk.Frame(sidebar, style="Panel.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="课程卡片", style="Heading.TLabel", background=PANEL).pack(side="left")
        ttk.Button(top, text="＋ 新建", style="Accent.TButton", command=self.create_course).pack(side="right")
        ttk.Label(sidebar, text="拖动卡片到右侧的星期与节次", style="Panel.TLabel", foreground=MUTED).pack(anchor="w", pady=(8, 12))

        self.course_canvas = tk.Canvas(sidebar, bg=PANEL, highlightthickness=0, width=250)
        self.course_scroll = ttk.Scrollbar(sidebar, orient="vertical", command=self.course_canvas.yview)
        self.course_list = ttk.Frame(self.course_canvas, style="Panel.TFrame")
        self.course_window = self.course_canvas.create_window((0, 0), window=self.course_list, anchor="nw")
        self.course_canvas.configure(yscrollcommand=self.course_scroll.set)
        self.course_canvas.pack(side="left", fill="both", expand=True)
        self.course_scroll.pack(side="right", fill="y")
        self.course_list.bind("<Configure>", self._sidebar_configure)
        self.course_canvas.bind("<Configure>", lambda event: self.course_canvas.itemconfigure(self.course_window, width=event.width))
        self.course_canvas.bind("<MouseWheel>", lambda event: self.course_canvas.yview_scroll(int(-event.delta / 120), "units"))

        timetable_panel = ttk.Frame(main, style="Panel.TFrame", padding=8)
        timetable_panel.pack(side="left", fill="both", expand=True)
        self.timetable = TimetableCanvas(timetable_panel, self)
        self.timetable.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="就绪")
        status = ttk.Frame(self, padding=(22, 7))
        status.pack(fill="x")
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        self.summary_label = ttk.Label(status, style="Muted.TLabel")
        self.summary_label.pack(side="right")

    def _sidebar_configure(self, _event: tk.Event) -> None:
        self.course_canvas.configure(scrollregion=self.course_canvas.bbox("all"))

    def refresh_all(self) -> None:
        self.refresh_courses()
        self.timetable.redraw()
        self.summary_label.configure(text=f"{len(self.project.periods)} 个节次 · {len(self.project.courses)} 门课程 · {len(self.project.placements)} 个安排")

    def refresh_courses(self) -> None:
        for child in self.course_list.winfo_children():
            child.destroy()
        if not self.project.courses:
            ttk.Label(self.course_list, text="暂无课程\n点击“＋ 新建”创建第一门课程", style="Panel.TLabel", foreground=MUTED, justify="center").pack(fill="x", pady=50)
            return
        for course in self.project.courses:
            card = tk.Frame(self.course_list, bg=course.color, padx=12, pady=10, cursor="hand2")
            card.pack(fill="x", pady=(0, 10), padx=(0, 5))
            color = contrast_text(course.color)
            title = tk.Label(card, text=course.name, bg=course.color, fg=color, font=("Microsoft YaHei UI", 11, "bold"), anchor="w")
            title.pack(fill="x")
            detail = tk.Label(card, text=f"{course.location or '地点未填写'}\n{course.week_rule.label()} · {course.duration} 节", bg=course.color, fg=color, font=("Microsoft YaHei UI", 8), anchor="w", justify="left")
            detail.pack(fill="x", pady=(4, 2))
            actions = tk.Frame(card, bg=course.color)
            actions.pack(fill="x", pady=(6, 0))
            edit = tk.Label(actions, text="编辑", bg=course.color, fg=color, cursor="hand2", font=("Microsoft YaHei UI", 8, "underline"))
            edit.pack(side="left")
            delete = tk.Label(actions, text="删除", bg=course.color, fg=color, cursor="hand2", font=("Microsoft YaHei UI", 8, "underline"))
            delete.pack(side="right")
            edit.bind("<Button-1>", lambda _event, cid=course.id: self.edit_course(cid))
            delete.bind("<Button-1>", lambda _event, cid=course.id: self.delete_course(cid))
            for widget in (card, title, detail):
                widget.bind("<ButtonPress-1>", lambda event, cid=course.id: self.start_course_drag(event, cid))
                widget.bind("<B1-Motion>", self.update_course_drag)
                widget.bind("<ButtonRelease-1>", self.finish_course_drag)

    def create_course(self) -> None:
        dialog = CourseDialog(self, self.project.semester_weeks, self.service.next_color())
        self.wait_window(dialog)
        if dialog.result:
            try:
                self.service.add_course(dialog.result)
                self.changed("课程已创建。请将卡片拖到课表中。")
            except ScheduleError as exc:
                messagebox.showwarning("无法创建课程", str(exc), parent=self)

    def edit_course(self, course_id: str) -> None:
        course = self.project.course_by_id(course_id)
        if not course:
            return
        dialog = CourseDialog(self, self.project.semester_weeks, course.color, course)
        self.wait_window(dialog)
        if dialog.result:
            try:
                self.service.update_course(dialog.result)
                self.changed("课程信息已更新。")
            except ScheduleError as exc:
                messagebox.showwarning("无法更新课程", str(exc), parent=self)

    def change_course_color(self, course_id: str) -> None:
        course = self.project.course_by_id(course_id)
        if not course:
            return
        selected = colorchooser.askcolor(course.color, title="修改课程颜色", parent=self)[1]
        if selected:
            updated = Course(course.name, course.location, course.week_rule, course.duration, selected.upper(), course.id)
            self.service.update_course(updated)
            self.changed("课程颜色已更新。")

    def delete_course(self, course_id: str) -> None:
        course = self.project.course_by_id(course_id)
        if course and messagebox.askyesno("删除课程", f"确定删除“{course.name}”吗？\n课表中的所有相关安排也会删除。", parent=self):
            self.service.delete_course(course_id)
            self.changed("课程及其所有安排已删除。")

    def start_course_drag(self, event: tk.Event, course_id: str) -> None:
        course = self.project.course_by_id(course_id)
        if not course:
            return
        self.drag_course_id = course_id
        self.drag_window = tk.Toplevel(self)
        self.drag_window.overrideredirect(True)
        self.drag_window.attributes("-topmost", True)
        label = tk.Label(self.drag_window, text=f"{course.name}\n释放以放入课表", bg=course.color, fg=contrast_text(course.color), padx=14, pady=8, font=("Microsoft YaHei UI", 9, "bold"))
        label.pack()
        self.update_course_drag(event)

    def update_course_drag(self, event: tk.Event) -> None:
        if self.drag_window:
            self.drag_window.geometry(f"+{event.x_root + 14}+{event.y_root + 14}")

    def finish_course_drag(self, event: tk.Event) -> None:
        if self.drag_window:
            self.drag_window.destroy()
            self.drag_window = None
        course_id, self.drag_course_id = self.drag_course_id, None
        cell = self.timetable.cell_from_root(event.x_root, event.y_root)
        if course_id and cell:
            self.place_course(course_id, *cell)
        elif course_id:
            self.status("请将课程卡片释放在有效的课表单元格中。")

    def place_course(self, course_id: str, day: int, period: int) -> bool:
        try:
            self.service.place_course(course_id, day, period)
            self.changed(f"课程已安排到{DAYS[day]} {self.project.periods[period].name}。")
            return True
        except ScheduleError as exc:
            self.bell()
            messagebox.showwarning("无法放置：课程冲突", str(exc), parent=self)
            self.status(f"冲突：{exc}")
            return False

    def move_placement(self, placement_id: str, day: int, period: int) -> bool:
        try:
            self.service.move_placement(placement_id, day, period)
            self.changed(f"课程已移动到{DAYS[day]} {self.project.periods[period].name}。")
            return True
        except ScheduleError as exc:
            self.bell()
            messagebox.showwarning("无法移动：课程冲突", str(exc), parent=self)
            self.status(f"冲突：{exc}")
            return False

    def delete_placement(self, placement_id: str) -> None:
        self.service.delete_placement(placement_id)
        self.changed("已从课表中删除该次安排，课程卡片仍保留在左侧。")

    def edit_periods(self) -> None:
        dialog = PeriodDialog(self, self.project.periods)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        old_periods = list(self.project.periods)
        new_index = {period.id: index for index, period in enumerate(dialog.result)}
        invalid = []
        remapped: dict[str, int] = {}
        for placement in self.project.placements:
            course = self.project.course_by_id(placement.course_id)
            if not course or placement.period + course.duration > len(old_periods):
                invalid.append(placement)
                continue
            occupied_ids = [period.id for period in old_periods[placement.period : placement.period + course.duration]]
            positions = [new_index.get(period_id) for period_id in occupied_ids]
            valid_positions = [position for position in positions if position is not None]
            if len(valid_positions) != course.duration or valid_positions != list(range(valid_positions[0], valid_positions[0] + course.duration)):
                invalid.append(placement)
            else:
                remapped[placement.id] = valid_positions[0]
        if invalid and not messagebox.askyesno("节次减少", f"有 {len(invalid)} 个课程安排超出新的节次范围。\n应用后将删除这些安排，是否继续？", parent=self):
            return
        invalid_ids = {p.id for p in invalid}
        self.project.placements = [p for p in self.project.placements if p.id not in invalid_ids]
        for placement in self.project.placements:
            placement.period = remapped.get(placement.id, placement.period)
        self.project.periods = dialog.result
        self.changed("节次设置已更新。")

    def changed(self, message: str) -> None:
        self.dirty = True
        self.refresh_all()
        self.status(message)

    def status(self, message: str) -> None:
        self.status_var.set(message)

    def save_project(self, quiet: bool = False) -> bool:
        try:
            self.store.save(self.project)
            self.dirty = False
            self.status(f"项目已保存：{self.data_file}")
            if not quiet:
                messagebox.showinfo("保存成功", f"课表项目已保存到：\n{self.data_file}", parent=self)
            return True
        except StorageError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self)
            self.status(str(exc))
            return False

    def export_png(self, destination: Path | None = None, quiet: bool = False) -> Path | None:
        destination = destination or default_export_path()
        try:
            output = export_project_png(self.project, destination)
            self.status(f"PNG 已导出：{output}")
            if not quiet:
                messagebox.showinfo("导出成功", f"高清课表图片已保存到：\n{output}", parent=self)
            return output
        except ExportError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self)
            self.status(str(exc))
            return None

    def on_close(self) -> None:
        if self.dirty:
            choice = messagebox.askyesnocancel("保存更改", "关闭前是否保存当前课表？", parent=self)
            if choice is None:
                return
            if choice and not self.save_project(quiet=True):
                return
        self.destroy()
