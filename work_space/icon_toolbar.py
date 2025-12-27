# work_space/icon_toolbar.py
# Панель инструментов: Пуск / Пауза(Продолжить) / Стоп
# Кнопки 20x20, без фона/границ, минимальный зазор.

from __future__ import annotations

import tkinter as tk
from typing import Optional, Callable


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self._tip: Optional[tk.Toplevel] = None
        self.widget.bind("<Enter>", self._show, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")  # чтобы не зависала

    def _show(self, _event=None):
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            self._tip,
            text=self.text,
            bg="#f3f1e6",   # "молочный"
            fg="#111111",
            bd=1,
            relief="solid",
            padx=8,
            pady=4,
            font=("Segoe UI", 9),
        )
        lbl.pack()

    def _hide(self, _event=None):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


class IconToolbar(tk.Frame):
    """
    Ожидаемые callbacks (если app передан):
      - app.start_experiment() / app.on_start()
      - app.toggle_pause_experiment() / app.on_pause()
      - app.stop_experiment() / app.on_stop()
    """

    def __init__(self, parent: tk.Widget, app=None, **kwargs):
        bg = kwargs.pop("bg", parent.cget("bg") if isinstance(parent, tk.Widget) else "#000000")
        super().__init__(parent, bg=bg, **kwargs)
        self.app = app

        self._is_paused = False

        self._build_ui()

    def _build_ui(self):
        # Контейнер без отступов
        self.configure(highlightthickness=0, bd=0)

        btn_style = dict(
            width=2,              # примерно 20px в зависимости от шрифта
            height=1,
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=0,
            pady=0,
            bg=self.cget("bg"),
            activebackground=self.cget("bg"),
            fg="#ffffff",
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )

        self.btn_start = tk.Button(self, text="▶", command=self._on_start, **btn_style)
        self.btn_pause = tk.Button(self, text="⏸", command=self._on_pause_resume, **btn_style)
        self.btn_stop = tk.Button(self, text="⏹", command=self._on_stop, **btn_style)

        # Минимальный зазор
        self.btn_start.grid(row=0, column=0, padx=(0, 2), pady=0, sticky="nsew")
        self.btn_pause.grid(row=0, column=1, padx=(0, 2), pady=0, sticky="nsew")
        self.btn_stop.grid(row=0, column=2, padx=(0, 0), pady=0, sticky="nsew")

        ToolTip(self.btn_start, "Пуск")
        ToolTip(self.btn_pause, "Пауза / Продолжить")
        ToolTip(self.btn_stop, "Стоп")

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)

    def set_running_state(self, running: bool, paused: bool = False):
        self._is_paused = bool(paused)
        # Можно визуально менять иконку
        self.btn_pause.configure(text="▶" if self._is_paused else "⏸")

    def _call_app(self, method_names: list[str]):
        if self.app is None:
            return
        for name in method_names:
            fn = getattr(self.app, name, None)
            if callable(fn):
                fn()
                return

    def _on_start(self):
        self._is_paused = False
        self.btn_pause.configure(text="⏸")
        self._call_app(["start_experiment", "on_start"])

    def _on_pause_resume(self):
        # Переключение паузы
        self._is_paused = not self._is_paused
        self.btn_pause.configure(text="▶" if self._is_paused else "⏸")
        self._call_app(["toggle_pause_experiment", "pause_resume_experiment", "on_pause"])

    def _on_stop(self):
        self._is_paused = False
        self.btn_pause.configure(text="⏸")
        self._call_app(["stop_experiment", "on_stop"])
