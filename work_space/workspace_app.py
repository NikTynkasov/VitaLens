# work_space/workspace_app.py
# Рабочая область VitaLens: фон + меню + панель инструментов + окно логирования (внизу)

import os
import sys
import importlib
import importlib.util
import json
import math
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any, List, Tuple, Callable
try:
    from PIL import Image, ImageTk  # type: ignore
    _PIL_OK = True
except Exception:
    Image = None
    ImageTk = None
    _PIL_OK = False


class ToolbarPanel:
    """
    Фиксированная панель инструментов, приклеенная к левому краю.

    Требования:
    - только 3 кнопки: Пуск, Пауза/Продолжить, Стоп
    - кнопки 20x20, без границ и без фона, с минимальным расстоянием
    - фон панели "прозрачный": показывает фон рабочей области (снимок фоновой картинки)
    """

    PANEL_WIDTH = 60
    ICON_SIZE = 20
    BTN_SIZE = 20
    BTN_GAP = 0
    TOP_PAD = 8

    def __init__(self, root: tk.Tk, app: "WorkspaceApp", initial_state: Optional[Dict[str, Any]] = None):
        self.root = root
        self.app = app

        self._bg_imgtk: Optional[tk.PhotoImage] = None
        self._window_bg_pil = None  # PIL.Image фон окна (w x h), если доступно
        self._bg_update_job_fast = None
        self._bg_update_job_quality = None
        self._bg_last_h = None

        self.frame = tk.Frame(
            root,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            width=self.PANEL_WIDTH
        )

        self._bg_label = tk.Label(self.frame, bd=0, highlightthickness=0)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()

        self._run_pil = None
        self._pause_pil = None
        self._resume_pil = None
        self._stop_pil = None

        self._run_w: Optional[tk.Label] = None
        self._pause_w: Optional[tk.Label] = None
        self._stop_w: Optional[tk.Label] = None

        self._run_imgtk: Optional[tk.PhotoImage] = None
        self._pause_imgtk: Optional[tk.PhotoImage] = None
        self._stop_imgtk: Optional[tk.PhotoImage] = None

        x = max(0, (self.PANEL_WIDTH - self.BTN_SIZE) // 2)
        y0 = self.TOP_PAD
        self._btn_geom = {
            "run": (x, y0),
            "pause": (x, y0 + self.BTN_SIZE + self.BTN_GAP),
            "stop": (x, y0 + (self.BTN_SIZE + self.BTN_GAP) * 2),
        }

        self._load_icons()
        self._build_widgets()
        self._place_at_left()

        if isinstance(initial_state, dict):
            self.apply_state(initial_state)

    def _place_at_left(self):
        try:
            self.frame.place_forget()
        except Exception:
            pass
        self.frame.place(x=0, y=0, relheight=1, width=self.PANEL_WIDTH)
        self.frame.lift()

    def destroy(self):
        try:
            self.frame.destroy()
        except Exception:
            pass

    def hide(self):
        try:
            self.frame.place_forget()
        except Exception:
            pass

    def show(self):
        try:
            if not self.frame.winfo_ismapped():
                self._place_at_left()
        except Exception:
            pass

    def get_state(self) -> Dict[str, Any]:
        return {"visible": bool(self.frame.winfo_ismapped())}

    def apply_state(self, state: Dict[str, Any]):
        visible = bool(state.get("visible", True))
        if not visible:
            self.hide()
        else:
            self.show()

    def update_background_snapshot(self, window_bg_pil):
        if not (_PIL_OK and Image is not None and ImageTk is not None):
            return
        if window_bg_pil is None:
            return

        self._window_bg_pil = window_bg_pil
        self._schedule_bg_update()

    def _schedule_bg_update(self):
        try:
            if self._bg_update_job_fast is not None:
                self.root.after_cancel(self._bg_update_job_fast)
        except Exception:
            pass
        try:
            if self._bg_update_job_quality is not None:
                self.root.after_cancel(self._bg_update_job_quality)
        except Exception:
            pass

        try:
            self._bg_update_job_fast = self.root.after(40, lambda: self._do_bg_update(quality=False))
            self._bg_update_job_quality = self.root.after(250, lambda: self._do_bg_update(quality=True))
        except Exception:
            self._bg_update_job_fast = None
            self._bg_update_job_quality = None

    def _do_bg_update(self, quality: bool):
        if not (_PIL_OK and Image is not None and ImageTk is not None):
            return
        window_bg_pil = getattr(self, "_window_bg_pil", None)
        if window_bg_pil is None:
            return

        try:
            w = int(self.PANEL_WIDTH)
            h = max(1, int(self.root.winfo_height()))
            if (not quality) and self._bg_last_h == h:
                # быстрый проход — не пересчитываем без необходимости
                return
            self._bg_last_h = h

            crop = window_bg_pil.crop((0, 0, w, h))
            # В тулбаре crop уже нужного размера, resize не требуется
            self._bg_imgtk = ImageTk.PhotoImage(crop)
            self._bg_label.configure(image=self._bg_imgtk)
            self._bg_label.lower()
        except Exception:
            pass

        self._refresh_button_images()

    def _project_root(self) -> str:
        return getattr(self.app, "project_root", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def _load_icon_pil(self, rel_path: str, size: int):
        if not (_PIL_OK and Image is not None):
            return None
        try:
            abs_path = os.path.join(self._project_root(), rel_path)
            if not os.path.exists(abs_path):
                return None
            img = Image.open(abs_path).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            return img
        except Exception:
            return None

    def _load_icons(self):
        self._run_pil = self._load_icon_pil("images/btn/btn_start.png", self.ICON_SIZE)
        self._pause_pil = self._load_icon_pil("images/btn/btn_pause.png", self.ICON_SIZE)
        self._stop_pil = self._load_icon_pil("images/btn/btn_stop.png", self.ICON_SIZE)
        self._resume_pil = self._run_pil

    def _build_widgets(self):
        self._run_w = self._make_icon_widget(
            tooltip_fn=lambda: "Пуск (F5)",
            command=self._on_run_clicked,
            fallback_text="▶"
        )
        self._pause_w = self._make_icon_widget(
            tooltip_fn=lambda: "Пауза/Продолжить (F6)",
            command=self._on_pause_clicked,
            fallback_text="⏸"
        )
        self._stop_w = self._make_icon_widget(
            tooltip_fn=lambda: "Стоп (F7)",
            command=self._on_stop_clicked,
            fallback_text="■"
        )

        rx, ry = self._btn_geom["run"]
        px, py = self._btn_geom["pause"]
        sx, sy = self._btn_geom["stop"]

        self._run_w.place(x=rx, y=ry, width=self.BTN_SIZE, height=self.BTN_SIZE)
        self._pause_w.place(x=px, y=py, width=self.BTN_SIZE, height=self.BTN_SIZE)
        self._stop_w.place(x=sx, y=sy, width=self.BTN_SIZE, height=self.BTN_SIZE)

        self._refresh_button_images()

    def _make_icon_widget(self, tooltip_fn, command, fallback_text=""):
        lbl = tk.Label(
            self.frame,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            padx=0,
            pady=0,
            text=fallback_text,
            font=("Segoe UI", 10, "bold"),
            fg="white",
        )
        lbl.configure(cursor="hand2")

        tip = tk.Toplevel(self.root)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip_lbl = tk.Label(
            tip,
            text="",
            bg="#111111",
            fg="#ffffff",
            bd=0,
            padx=6,
            pady=3,
            font=("Segoe UI", 9)
        )
        tip_lbl.pack()

        def _show_tip(event):
            try:
                text = tooltip_fn() if callable(tooltip_fn) else ""
                if not text:
                    return
                tip_lbl.config(text=text)
                x = event.x_root + 10
                y = event.y_root + 10
                tip.geometry(f"+{x}+{y}")
                tip.deiconify()
            except Exception:
                pass

        def _hide_tip(_event=None):
            try:
                tip.withdraw()
            except Exception:
                pass

        def _click(_event=None):
            try:
                _hide_tip()
                if callable(command):
                    command()
            except Exception:
                pass

        lbl.bind("<Enter>", _show_tip, add="+")
        lbl.bind("<Leave>", _hide_tip, add="+")
        lbl.bind("<Button-1>", _click, add="+")
        return lbl

    def _get_bg_crop_for_button(self, x: int, y: int, size: int):
        if not (_PIL_OK and Image is not None):
            return None
        if self._window_bg_pil is None:
            return None
        try:
            crop = self._window_bg_pil.crop((x, y, x + size, y + size))
            return crop
        except Exception:
            return None

    def _compose_button_image(self, bg_crop_pil, icon_pil):
        if not (_PIL_OK and Image is not None and ImageTk is not None):
            return None
        if bg_crop_pil is None:
            bg_crop_pil = Image.new("RGBA", (self.BTN_SIZE, self.BTN_SIZE), (0, 0, 0, 0))

        out = bg_crop_pil.copy()
        if icon_pil is not None:
            try:
                ix, iy = icon_pil.size
                ox = max(0, (self.BTN_SIZE - ix) // 2)
                oy = max(0, (self.BTN_SIZE - iy) // 2)
                out.alpha_composite(icon_pil, (ox, oy))
            except Exception:
                pass
        return ImageTk.PhotoImage(out)

    def _refresh_button_images(self):
        if not (_PIL_OK and Image is not None and ImageTk is not None):
            return

        paused = bool(getattr(self.app, "_sim_paused", False))
        run_icon = self._run_pil
        pause_icon = self._resume_pil if paused else self._pause_pil
        stop_icon = self._stop_pil

        for key, icon in (("run", run_icon), ("pause", pause_icon), ("stop", stop_icon)):
            x, y = self._btn_geom[key]
            bg = self._get_bg_crop_for_button(x, y, self.BTN_SIZE)
            img = self._compose_button_image(bg, icon)

            if key == "run":
                self._run_imgtk = img
                if self._run_w is not None and img is not None:
                    self._run_w.configure(image=img, text="")
            elif key == "pause":
                self._pause_imgtk = img
                if self._pause_w is not None and img is not None:
                    self._pause_w.configure(image=img, text="")
            elif key == "stop":
                self._stop_imgtk = img
                if self._stop_w is not None and img is not None:
                    self._stop_w.configure(image=img, text="")

    def _on_run_clicked(self):
        fn = getattr(self.app, "start_simulation", None)
        if callable(fn):
            fn()

    def _on_pause_clicked(self):
        fn = getattr(self.app, "toggle_pause_simulation", None)
        if callable(fn):
            fn()
        else:
            fn2 = getattr(self.app, "stop_simulation", None)
            if callable(fn2):
                fn2()
        self._refresh_button_images()

    def _on_stop_clicked(self):
        fn = getattr(self.app, "reset_simulation", None)
        if callable(fn):
            fn()
        try:
            if hasattr(self.app, "_sim_paused"):
                setattr(self.app, "_sim_paused", False)
        except Exception:
            pass
        self._refresh_button_images()


class WorkspaceApp:
    """
    Этап UI:
    - фон images/background.png
    - верхнее меню (menu_bar.py)
    - панель инструментов (ToolbarPanel), видимость через меню Вид
    - окно логирования внизу (высота 100px), на всю ширину окна (без отступа слева)
    """

    LOG_PANEL_HEIGHT = 100

    # молочный фон
    LOG_BG = "#f3efe6"
    LOG_BORDER_TOP = "#b8b3aa"
    LOG_TEXT_FG = "#111111"

    def __init__(self, master=None):
        self.root = tk.Toplevel(master) if master else tk.Tk()
        self.root.title("VitaLens — Рабочая область")
        self.root.geometry("1200x800")

        self.module_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.module_dir)

        if self.project_root not in sys.path:
            sys.path.insert(0, self.project_root)

        self.ui_layout = "background_only"

        self.current_experiment = None
        self.window_visibility = {
            "control_panel": True,
            "visualization": True,
            "monitoring": True,
            "statusbar": True,
            "icon_toolbar": True,
        }

        self.visualization_mode = tk.StringVar(value="Чашка Петри")
        self.exp_name_var = tk.StringVar(value="Эксперимент")
        self.duration_var = tk.IntVar(value=1)

        self.status_var = tk.StringVar(value="Готов к работе")
        self.progress_var = tk.DoubleVar(value=0)
        self.ph_auto_co2_var = tk.BooleanVar(value=False)

        self.time_var = tk.StringVar(value="Время: 00:00:00")
        self.cell_count_var = tk.StringVar(value="Клеток: 0")

        self._bg_label = None
        self._bg_pil_original = None
        self._bg_pil_window = None
        self._bg_imgtk = None

        # Debounce ресайза фонового изображения окна (иначе <Configure> дергает очень часто)
        self._bg_resize_job_fast = None
        self._bg_resize_job_quality = None
        self._bg_last_win_wh = None

        self._toolbar: Optional[ToolbarPanel] = None
        self._toolbar_state: Dict[str, Any] = {}

        # панель эксперимента (настройки + мониторинг) в рабочей области
        self._exp_dashboard_panel = None
        self._exp_dashboard_state: Dict[str, Any] = {}


        # experiment control panel (плавающее поле управления)
        self._exp_control_panel = None
        self._exp_control_panel_state: Dict[str, Any] = {}
        self.applied_settings: Dict[str, Any] = {}
        self.runtime_settings: Dict[str, Any] = {}
        self.applied_gases_config: Dict[str, float] = {}
        self.runtime_gases_config: Dict[str, float] = {}
        self._runtime_gases_staged: Dict[str, float] = {}

        # -------------------------
        # Bio-sim engine (расчёт роста культуры)
        # -------------------------
        self._engine_module = None
        self._engine = None
        self._engine_loop_job = None
        self._engine_tick_ms = 1000  # шаг движка (мс)
        self._engine_dt_hours = 1.0 / 3600.0  # 1 сек = 1/3600 часа
        self._engine_import_error = ""

        # Флаг: настройки эксперимента применены (нужен для запуска и для чекпоинтов графиков)
        self.experiment_settings_applied: bool = False

        # Чекпоинты параметров для построения графиков (key -> bool)
        self.plot_checkpoints: Dict[str, bool] = {}
        self._experiment_running = False
        self._experiment_paused = False
        self._experiment_control_protocol: list[str] = []

        # log panel
        self.log_frame: Optional[tk.Frame] = None
        self.log_text: Optional[tk.Text] = None
        self.log_scroll: Optional[ttk.Scrollbar] = None
        self._log_top_border: Optional[tk.Frame] = None
        self._log_content: Optional[tk.Frame] = None

        # resize grip for log panel height
        self._log_resize_grip: Optional[tk.Frame] = None
        self._log_resize_active = False
        self._log_resize_start_y = 0
        self._log_resize_start_h = int(getattr(self, 'LOG_PANEL_HEIGHT', 100) or 100)

        self._sim_paused = False
        self._settings_cache: Dict[str, Any] = {}

        # ====================== Графики (встроенная панель в рабочей области) ======================
        # Чекпоинты "График" (key -> bool). Управляются из панели Управление экспериментом.
        self.plot_checkpoints: Dict[str, bool] = {}
        # Состояние панели графиков (позиция/размер/режим)
        self._plot_panel_state: Dict[str, Any] = {}
        self._culture_growth_win = None
        # Экземпляр панели графиков (PlotPanel из plot_panel.py)
        self._plot_panel = None
        # Данные временных рядов (key -> [(t, y), ...])
        self._plot_series: Dict[str, List[Tuple[float, float]]] = {}
        self._plot_t0: Optional[float] = None
        self._plot_sample_job = None

        self.load_settings()

        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _settings_path(self) -> str:
        return os.path.join(self.module_dir, "settings.json")

    def load_settings(self):
        path = self._settings_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._settings_cache = json.load(f) or {}
            except Exception:
                self._settings_cache = {}
        else:
            self._settings_cache = {}

        state = self._settings_cache.get("toolbar_state")
        if isinstance(state, dict):
            self._toolbar_state = state

        vis = self._settings_cache.get("window_visibility")
        if isinstance(vis, dict):
            for k in self.window_visibility.keys():
                if k in vis:
                    self.window_visibility[k] = bool(vis.get(k))

        cps = self._settings_cache.get("experiment_control_panel_state")
        if isinstance(cps, dict):
            self._exp_control_panel_state = dict(cps)


        dsh = self._settings_cache.get("experiment_dashboard_state")
        if isinstance(dsh, dict):
            self._exp_dashboard_state = dict(dsh)

        pc = self._settings_cache.get("plot_checkpoints")
        if isinstance(pc, dict):
            try:
                self.plot_checkpoints = {str(k): bool(v) for k, v in pc.items()}
            except Exception:
                self.plot_checkpoints = {}

        pps = self._settings_cache.get("plot_panel_state")
        if isinstance(pps, dict):
            self._plot_panel_state = dict(pps)


        # restore adjustable log panel height
        try:
            lph = self._settings_cache.get("log_panel_height")
            if lph is not None:
                lph_i = int(lph)
                if lph_i >= 50:
                    self.LOG_PANEL_HEIGHT = lph_i
        except Exception:
            pass
    def save_settings(self):
        self._settings_cache["toolbar_state"] = self._toolbar_state
        self._settings_cache["window_visibility"] = self.window_visibility
        if isinstance(getattr(self, "_exp_control_panel_state", None), dict):
            self._settings_cache["experiment_control_panel_state"] = dict(self._exp_control_panel_state)


        if isinstance(getattr(self, "_exp_dashboard_state", None), dict):
            self._settings_cache["experiment_dashboard_state"] = dict(self._exp_dashboard_state)

        if isinstance(getattr(self, "plot_checkpoints", None), dict):
            self._settings_cache["plot_checkpoints"] = dict(self.plot_checkpoints)
        if isinstance(getattr(self, "_plot_panel_state", None), dict):
            self._settings_cache["plot_panel_state"] = dict(self._plot_panel_state)
        # persist adjustable log panel height
        try:
            self._settings_cache["log_panel_height"] = int(getattr(self, "LOG_PANEL_HEIGHT", 100) or 100)
        except Exception:
            pass
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as f:
                json.dump(self._settings_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    
    def on_experiment_control_panel_state_changed(self, state: Dict[str, Any]):
        if isinstance(state, dict):
            self._exp_control_panel_state = dict(state)
            self.save_settings()


    def on_experiment_dashboard_state_changed(self, state: Dict[str, Any]):
        if isinstance(state, dict):
            self._exp_dashboard_state = dict(state)
            self.save_settings()

    def on_toolbar_state_changed(self, state: Dict[str, Any]):
        if isinstance(state, dict):
            self._toolbar_state = state
            self.save_settings()

    def save_window_visibility_settings(self):
        self.save_settings()


    # ====================== Графики (встроенная панель в рабочей области) ======================

    def setup_plot_panel(self):
        """Инициализация/синхронизация встроенной панели графиков.
        Панель показывается только если есть активные чекпоинты 'График'.
        """
        try:
            # небольшая задержка, чтобы успели построиться панели и выставилась доступность чекпоинтов
            self.root.after(80, self._sync_plot_panel_from_checkpoints)
        except Exception:
            pass

    def _sync_plot_panel_from_checkpoints(self):
        keys = self._get_enabled_plot_keys()
        if keys:
            self._ensure_plot_panel()
            self._update_plot_panel(full_rebuild=True)
        else:
            self._hide_plot_panel()

    def on_plot_checkpoint_toggled(self, key: str, enabled: bool):
        """Колбэк из ExperimentControlPanel (чекпоинт 'График')."""
        k = str(key)
        if not isinstance(getattr(self, "plot_checkpoints", None), dict):
            self.plot_checkpoints = {}
        self.plot_checkpoints[k] = bool(enabled)
        try:
            self.save_settings()
        except Exception:
            pass

        keys = self._get_enabled_plot_keys()
        if keys:
            self._ensure_plot_panel()
            self._update_plot_panel(full_rebuild=True)
        else:
            self._hide_plot_panel()

    def on_plot_panel_state_changed(self, state: Dict[str, Any]):
        if isinstance(state, dict):
            self._plot_panel_state = dict(state)
            try:
                self.save_settings()
            except Exception:
                pass

    def _get_enabled_plot_keys(self) -> List[str]:
        keys: List[str] = []
        try:
            for k, v in (self.plot_checkpoints or {}).items():
                if bool(v):
                    keys.append(str(k))
        except Exception:
            return []
        return keys

    def _get_all_plot_keys(self) -> List[str]:
        """Ключи, которые пишем в историю графиков.

        Требование: если пользователь включил новый график в процессе эксперимента,
        его кривая должна начинаться от старта эксперимента, а не от момента включения.
        Для этого точки пишем по всем известным параметрам, а отображаем — только по выбранным.
        """
        keys: List[str] = []
        try:
            # 1) всё, что знает UI (стабильный список)
            labels = self._plot_labels() if hasattr(self, "_plot_labels") else {}
            if isinstance(labels, dict):
                for k in labels.keys():
                    keys.append(str(k))
        except Exception:
            pass

        try:
            # 2) то, что пользователь уже видел/переключал (чекпоинты)
            for k in (self.plot_checkpoints or {}).keys():
                keys.append(str(k))
        except Exception:
            pass

        try:
            # 3) уже накопленные серии
            for k in (self._plot_series or {}).keys():
                keys.append(str(k))
        except Exception:
            pass

        # уникально + стабильно по имени
        out = sorted(set(keys))
        return out


    def _plot_labels(self) -> Dict[str, str]:
        """Подписи вкладок/графиков.
        Если ключ неизвестен — используем сам ключ.
        """
        labels = {
            "temperature_c": "Температура (°C)",
            "humidity": "Влажность (%)",
            "ph": "pH",
            "do_percent": "Растворённый O₂ (DO) (%)",
            "osmolality": "Осмолярность (mOsm/kg)",
            "glucose": "Глюкоза (g/L)",
            "stirring_rpm": "Перемешивание (RPM)",
            "aeration_lpm": "Аэрация (L/min)",
            "feed_rate": "Подача среды (mL/h)",
            "harvest_rate": "Отбор (mL/h)",
            "light_lux": "Освещённость (lux)",
            "light_cycle": "Цикл (день/ночь)",
        }
        try:
            for k in self._get_enabled_plot_keys():
                if k not in labels:
                    labels[k] = k
        except Exception:
            pass
        return labels

    def _import_plot_panel_class(self):
        """Ленивый импорт PlotPanel из plot_panel.py (без matplotlib)."""
        # 1) локальный импорт (python workspace_app.py из work_space)
        try:
            if self.module_dir not in sys.path:
                sys.path.insert(0, self.module_dir)
            from plot_panel import PlotPanel  # type: ignore
            return PlotPanel
        except Exception:
            pass
        # 2) импорт через пакет work_space
        try:
            pkg_name = os.path.basename(self.module_dir)
            mod = importlib.import_module(f"{pkg_name}.plot_panel")
            return getattr(mod, "PlotPanel", None)
        except Exception:
            return None

    def _ensure_plot_panel(self):
        if getattr(self, "_plot_panel", None) is not None:
            try:
                self._plot_panel.show()
                self._plot_panel.lift()
                try:
                    w = self._get_plot_panel_widget()
                    if w is not None:
                        self._bind_raise_recursive(w, "plot")
                except Exception:
                    pass
            except Exception:
                pass
            return

        PlotPanelCls = self._import_plot_panel_class()
        if PlotPanelCls is None:
            try:
                self.add_log_entry("Панель графиков недоступна (plot_panel.py не найден).", "WARN")
            except Exception:
                pass
            return

        rm = {"left": 0, "top": 0, "right": 0, "bottom": 0}
        try:
            fn = getattr(self, "get_reserved_margins", None)
            if callable(fn):
                rm = fn()
        except Exception:
            rm = {"left": 0, "top": 0, "right": 0, "bottom": 0}

        try:
            rw = max(1, int(self.root.winfo_width()))
            rh = max(1, int(self.root.winfo_height()))
        except Exception:
            rw, rh = 1200, 800

        default_w = 520
        default_h = 320
        x = int(self._plot_panel_state.get("x", rm.get("left", 0) + 80))
        y = int(self._plot_panel_state.get("y", rm.get("top", 0) + 80))
        w = int(self._plot_panel_state.get("w", default_w))
        h = int(self._plot_panel_state.get("h", default_h))
        mode_all = bool(self._plot_panel_state.get("mode_all", False))
        visible = bool(self._plot_panel_state.get("visible", True))

        # ограничим в рабочей области (учёт лог-панели снизу и тулбара)
        max_x = max(rm.get("left", 0), rw - rm.get("right", 0) - 50)
        max_y = max(rm.get("top", 0), rh - rm.get("bottom", 0) - 50)
        x = max(rm.get("left", 0), min(x, max_x))
        y = max(rm.get("top", 0), min(y, max_y))

        try:
            self._plot_panel = PlotPanelCls(
                self.root,
                app=self,
                initial_state={
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "mode_all": mode_all,
                    "visible": visible,
                },
                on_state_changed=self.on_plot_panel_state_changed,
            )
            if visible:
                self._plot_panel.show()
            else:
                self._plot_panel.hide()
            try:
                w = self._get_plot_panel_widget()
                if w is not None:
                    self._bind_raise_recursive(w, "plot")
            except Exception:
                pass
        except Exception as e:
            self._plot_panel = None
            try:
                self.add_log_entry(f"Панель графиков не создана: {e}", "ERROR")
            except Exception:
                pass
            return

        try:
            self._update_plot_panel(full_rebuild=True)
        except Exception:
            pass

        # после создания — чтобы z-order был корректный
        try:
            self._layout_overlays()
        except Exception:
            pass

    def _hide_plot_panel(self):
        try:
            if getattr(self, "_plot_panel", None) is not None:
                self._plot_panel.hide()
                st = self._plot_panel.get_state()
                if isinstance(st, dict):
                    self._plot_panel_state = dict(st)
                self.save_settings()
        except Exception:
            pass

    def _update_plot_panel(self, full_rebuild: bool):
        if getattr(self, "_plot_panel", None) is None:
            return
        keys = self._get_enabled_plot_keys()
        if not keys:
            return
        try:
            self._plot_panel.set_labels(self._plot_labels())
            self._plot_panel.set_selected_keys(keys)
            self._plot_panel.update_series(dict(self._plot_series or {}), full_rebuild=bool(full_rebuild))
        except Exception:
            pass

    def _reset_plot_series_for_new_run(self):
        self._plot_series = {}
        try:
            import time as _time
            self._plot_t0 = _time.monotonic()
        except Exception:
            self._plot_t0 = None
        try:
            if getattr(self, "_plot_panel", None) is not None:
                self._update_plot_panel(full_rebuild=True)
        except Exception:
            pass

    def _append_plot_sample(self, key: str, value: Any):
        try:
            y = float(value)
        except Exception:
            return

        import time as _time
        if self._plot_t0 is None:
            self._plot_t0 = _time.monotonic()
        t = float(_time.monotonic() - float(self._plot_t0))

        k = str(key)
        try:
            if k not in self._plot_series:
                self._plot_series[k] = []
            self._plot_series[k].append((t, y))
            # ограничение объёма: последние 3600 точек (~1 час при 1 Гц)
            if len(self._plot_series[k]) > 3600:
                self._plot_series[k] = self._plot_series[k][-3600:]
        except Exception:
            return

        self._update_plot_panel(full_rebuild=False)

    def _start_plot_sampling(self):
        # перезапуск таймера
        self._stop_plot_sampling()

        def _tick():
            self._plot_sample_job = None

            if not bool(getattr(self, "_experiment_running", False)):
                return

            # При паузе ничего не пишем, просто ждём
            if bool(getattr(self, "_sim_paused", False)):
                self._plot_sample_job = self.root.after(500, _tick)
                return

            # Пишем историю по всем известным ключам, чтобы при включении нового графика
            # кривая начиналась от старта эксперимента.
            keys = self._get_all_plot_keys()
            for k in keys:
                try:
                    v = self.get_runtime_parameter(k)
                    if v is None:
                        continue
                    self._append_plot_sample(k, v)
                except Exception:
                    continue

            self._plot_sample_job = self.root.after(1000, _tick)

        try:
            self._plot_sample_job = self.root.after(1000, _tick)
        except Exception:
            self._plot_sample_job = None

    def _stop_plot_sampling(self):
        try:
            if self._plot_sample_job is not None:
                self.root.after_cancel(self._plot_sample_job)
        except Exception:
            pass
        self._plot_sample_job = None

    def get_experiment_elapsed_seconds(self) -> int:
        """Текущее время эксперимента (с момента старта), в секундах."""
        try:
            if not bool(getattr(self, "_experiment_running", False)):
                return 0
            t0 = getattr(self, "_plot_t0", None)
            if t0 is None:
                return 0
            import time as _time
            sec = int(max(0.0, float(_time.monotonic()) - float(t0)))
            return sec
        except Exception:
            return 0


    def setup_ui(self):
        self.create_menu_bar()
        self.setup_background()
        self.setup_toolbar()
        self.setup_experiment_dashboard_panel()
        # Панель управления экспериментом удалена (управление через тулбар)
        self.setup_log_panel()
        self.setup_plot_panel()

        try:
            if getattr(self, "menu_bar", None) is not None and hasattr(self.menu_bar, "panel_vars"):
                pv = getattr(self.menu_bar, "panel_vars")
                if isinstance(pv, dict) and "icon_toolbar" in pv:
                    pv["icon_toolbar"].set(bool(self.window_visibility.get("icon_toolbar", True)))
        except Exception:
            pass

        self._layout_overlays()

    def create_menu_bar(self):
        try:
            pkg_name = os.path.basename(self.module_dir)  # work_space
            mod = importlib.import_module(f"{pkg_name}.menu_bar")
            create_menu_bar = getattr(mod, "create_menu_bar", None)
            if callable(create_menu_bar):
                self.menu_bar = create_menu_bar(self.root, self)
                return
        except Exception:
            pass

        try:
            from .menu_bar import create_menu_bar  # type: ignore
            self.menu_bar = create_menu_bar(self.root, self)
            return
        except Exception:
            pass

        try:
            if self.module_dir not in sys.path:
                sys.path.insert(0, self.module_dir)
            from menu_bar import create_menu_bar  # type: ignore
            self.menu_bar = create_menu_bar(self.root, self)
            return
        except Exception:
            self.menu_bar = None
            self._create_simple_menu()

    def _create_simple_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)

        self._simple_toolbar_var = tk.BooleanVar(value=self.window_visibility.get("icon_toolbar", True))

        def _toggle():
            self.window_visibility["icon_toolbar"] = bool(self._simple_toolbar_var.get())
            self.save_window_visibility_settings()
            self.rebuild_interface()

        view_menu.add_checkbutton(label="Панель инструментов", variable=self._simple_toolbar_var, command=_toggle)

    def _find_background_path(self) -> Optional[str]:
        p = os.path.join(self.project_root, "images", "background.png")
        return p if os.path.exists(p) else None

    def setup_background(self):
        bg_path = self._find_background_path()
        if not bg_path:
            return

        if self._bg_label is None:
            self._bg_label = tk.Label(self.root, bd=0, highlightthickness=0)
            self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self._bg_label.lower()
            self.root.bind("<Configure>", lambda _e: self._schedule_resize_background(), add="+")
        self.root.bind("<F8>", lambda e: self.open_culture_growth_table())

        if _PIL_OK and Image is not None and ImageTk is not None:
            try:
                self._bg_pil_original = Image.open(bg_path).convert("RGBA")
            except Exception:
                self._bg_pil_original = None

        self._resize_background()

    def _schedule_resize_background(self):
        """Запланировать обновление фона окна (быстро + качественно после паузы)."""
        try:
            w = max(1, self.root.winfo_width())
            h = max(1, self.root.winfo_height())
            wh = (w, h)
        except Exception:
            wh = None

        # Если размер окна не изменился — не пересчитываем
        if wh is not None and self._bg_last_win_wh == wh:
            return
        self._bg_last_win_wh = wh

        try:
            if self._bg_resize_job_fast is not None:
                self.root.after_cancel(self._bg_resize_job_fast)
        except Exception:
            pass
        try:
            if self._bg_resize_job_quality is not None:
                self.root.after_cancel(self._bg_resize_job_quality)
        except Exception:
            pass

        try:
            # Быстрое обновление (BILINEAR) — чтобы интерфейс был отзывчивым
            self._bg_resize_job_fast = self.root.after(40, lambda: self._resize_background(quality=False))
            # Качественное обновление (LANCZOS) — после небольшой паузы
            self._bg_resize_job_quality = self.root.after(280, lambda: self._resize_background(quality=True))
        except Exception:
            self._bg_resize_job_fast = None
            self._bg_resize_job_quality = None

    def _resize_background(self, quality: bool = True):
        if self._bg_label is None:
            return

        w = max(1, self.root.winfo_width())
        h = max(1, self.root.winfo_height())
        if w < 5 or h < 5:
            return

        if self._bg_pil_original is None or not (_PIL_OK and ImageTk is not None):
            try:
                img = tk.PhotoImage(file=self._find_background_path())
                self._bg_imgtk = img
                self._bg_label.configure(image=self._bg_imgtk)
            except Exception:
                pass
            self._bg_pil_window = None
            self._layout_overlays()
            return

        img = self._bg_pil_original
        iw, ih = img.size
        scale = max(w / iw, h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        resized = img.resize((nw, nh), Image.LANCZOS if quality else Image.BILINEAR)
        left = max(0, (nw - w) // 2)
        top = max(0, (nh - h) // 2)
        cropped = resized.crop((left, top, left + w, top + h))
        self._bg_pil_window = cropped

        self._bg_imgtk = ImageTk.PhotoImage(cropped)
        self._bg_label.configure(image=self._bg_imgtk)
        self._bg_label.lower()

        try:
            if self._toolbar is not None and self._bg_pil_window is not None:
                self._toolbar.update_background_snapshot(self._bg_pil_window)
        except Exception:
            pass

        try:
            if self._exp_dashboard_panel is not None and self._bg_pil_window is not None:
                self._exp_dashboard_panel.update_background_snapshot(self._bg_pil_window)
        except Exception:
            pass

        self._layout_overlays()

    def setup_toolbar(self):
        enabled = bool(self.window_visibility.get("icon_toolbar", True))

        if not enabled:
            if self._toolbar is not None:
                self._toolbar.hide()
            return

        if self._toolbar is None:
            self._toolbar = ToolbarPanel(self.root, self, initial_state=self._toolbar_state)
        else:
            if self._toolbar_state:
                self._toolbar.apply_state(self._toolbar_state)
            self._toolbar.show()

        try:
            if self._toolbar is not None and self._bg_pil_window is not None:
                self._toolbar.update_background_snapshot(self._bg_pil_window)
        except Exception:
            pass

        if self._toolbar is not None and self._toolbar.frame.winfo_exists():
            self._toolbar.frame.lift()

    
    def setup_experiment_dashboard_panel(self):
        """Единая панель эксперимента (настройки + мониторинг), встроенная в рабочую область."""
        enabled = bool(self.window_visibility.get("monitoring", True))

        # Если панель выключена — скрываем
        if not enabled:
            try:
                if self._exp_dashboard_panel is not None:
                    self._exp_dashboard_panel.hide()
            except Exception:
                pass
            return

        # Создание при первом показе
        if self._exp_dashboard_panel is None:
            try:
                from experiment_dashboard_panel import ExperimentDashboardPanel
                self._exp_dashboard_panel = ExperimentDashboardPanel(
                    parent=self.root,
                    app=self,
                    state=dict(getattr(self, "_exp_dashboard_state", {}) or {}),
                    on_state_changed=getattr(self, "on_experiment_dashboard_state_changed", None),
                )
            except Exception as e:
                try:
                    self.add_log_entry(f"Ошибка инициализации панели эксперимента: {e}", "ERROR")
                except Exception:
                    pass
                self._exp_dashboard_panel = None
                return
        else:
            try:
                self._exp_dashboard_panel.show()
            except Exception:
                pass

        try:
            self._exp_dashboard_panel.reposition()
        except Exception:
            pass
        try:
            self._exp_dashboard_panel.frame.lift()
        except Exception:
            pass

    def setup_experiment_settings_panel(self):
        """Поле настройки эксперимента справа от кнопок (до правого края окна).

        ВАЖНО: это единственное добавление к исходному файлу — отдельная панель
        подгружается из work_space/experiment_settings_panel.py.
        """
        enabled = bool(self.window_visibility.get("icon_toolbar", True))

        if not enabled:
            if self._exp_dashboard_panel is not None:
                try:
                    self._exp_settings_panel.hide()
                except Exception:
                    pass
            return

        if self._exp_settings_panel is None:
            panel_cls = None

            # 1) Импорт через пакет work_space.experiment_settings_panel
            try:
                pkg_name = os.path.basename(self.module_dir)  # work_space
                mod = importlib.import_module(f"{pkg_name}.experiment_settings_panel")
                panel_cls = getattr(mod, "ExperimentSettingsPanel", None)
            except Exception:
                panel_cls = None

            # 2) Fallback: относительный импорт
            if panel_cls is None:
                try:
                    from .experiment_settings_panel import ExperimentSettingsPanel  # type: ignore
                    panel_cls = ExperimentSettingsPanel
                except Exception:
                    panel_cls = None

            # 3) Fallback: импорт из текущей директории (если запуск не как пакет)
            if panel_cls is None:
                try:
                    if self.module_dir not in sys.path:
                        sys.path.insert(0, self.module_dir)
                    from experiment_settings_panel import ExperimentSettingsPanel  # type: ignore
                    panel_cls = ExperimentSettingsPanel
                except Exception:
                    panel_cls = None

            if panel_cls is None:
                # Не меняем остальную логику — просто не создаём панель
                try:
                    self.add_log_entry("Панель настроек эксперимента не создана: не найден ExperimentSettingsPanel", "ERROR")
                except Exception:
                    pass
                return

            try:
                self._exp_settings_panel = panel_cls(self.root, self, x_offset=ToolbarPanel.PANEL_WIDTH)
            except Exception as e:
                self._exp_dashboard_panel = None
                try:
                    self.add_log_entry(f"Панель настроек эксперимента не создана: {e}", "ERROR")
                except Exception:
                    pass
                return
        else:
            try:
                self._exp_settings_panel.show()
            except Exception:
                pass

        # Обновляем фон панели, если фон окна уже рассчитан
        try:
            if self._bg_pil_window is not None and self._exp_settings_panel is not None:
                self._exp_dashboard_panel.update_background_snapshot(self._bg_pil_window)
        except Exception:
            pass

        # Гарантируем позиционирование (от правого края тулбара до правого края окна)
        try:
            if self._exp_dashboard_panel is not None:
                self._exp_dashboard_panel.reposition()
        except Exception:
            pass

    # -------------------------
    # log panel (bottom)
    # -------------------------

    
    def setup_experiment_control_panel(self):

    
        """Панель управления экспериментом отключена."""

    
        return



    def setup_log_panel(self):
        if self.log_frame is not None and self.log_frame.winfo_exists():
            return

        # Внешний контейнер (молочный фон)
        self.log_frame = tk.Frame(
            self.root,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            bg=self.LOG_BG
        )

        # Изменяемая граница (перетаскивание меняет высоту окна логирования)
        self._log_resize_grip = tk.Frame(
            self.log_frame,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            bg=self.LOG_BG,
            height=6,
            cursor="sb_v_double_arrow"
        )
        self._log_resize_grip.pack(side="top", fill="x")

        # Видимая граница по верхней грани (тонкая линия)
        self._log_top_border = tk.Frame(self._log_resize_grip, height=1, bg=self.LOG_BORDER_TOP, bd=0, highlightthickness=0)
        self._log_top_border.pack(side="bottom", fill="x")

        # Bind resize events
        self._log_resize_grip.bind("<ButtonPress-1>", self._on_log_resize_start, add="+")
        self._log_resize_grip.bind("<B1-Motion>", self._on_log_resize_move, add="+")
        self._log_resize_grip.bind("<ButtonRelease-1>", self._on_log_resize_end, add="+")

        # Контент внутри (тоже молочный, чтобы не было "дыр")
        self._log_content = tk.Frame(self.log_frame, bd=0, highlightthickness=0, bg=self.LOG_BG)
        self._log_content.pack(side="top", fill="both", expand=True)

        self.log_text = tk.Text(
            self._log_content,
            height=1,
            wrap="word",
            bd=0,
            highlightthickness=0,
            bg=self.LOG_BG,
            fg=self.LOG_TEXT_FG,
            insertbackground=self.LOG_TEXT_FG,
            font=("Consolas", 9),
            padx=10,
            pady=6
        )
        self.log_text.configure(state=tk.DISABLED)

        self.log_scroll = ttk.Scrollbar(self._log_content, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.log_scroll.set)

        self.log_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        self.add_log_entry("Окно логирования активировано", "INFO")

    def _layout_overlays(self):
        # фон вниз
        try:
            if self._bg_label is not None:
                self._bg_label.lower()
        except Exception:
            pass

        # toolbar поверх фона
        try:
            if self._toolbar is not None and self.window_visibility.get("icon_toolbar", True):
                if self._toolbar.frame.winfo_exists() and self._toolbar.frame.winfo_ismapped():
                    self._toolbar.frame.lift()
        except Exception:
            pass

        # поле настройки эксперимента справа от кнопок
        try:
            if self._exp_dashboard_panel is not None and self.window_visibility.get("monitoring", True):
                self._exp_dashboard_panel.reposition()
                self._exp_dashboard_panel.frame.lift()
        except Exception:
            pass


        # Панель графиков (встроенная): держим над фоном и настройками, но под управлением
        try:
            if getattr(self, "_plot_panel", None) is not None:
                pnl = getattr(self._plot_panel, "frame", None)
                if pnl is not None and pnl.winfo_exists() and pnl.winfo_ismapped():
                    pnl.lift()
        except Exception:
            pass

        # поле изменения параметров во время эксперимента ДОЛЖНО быть поверх поля настроек
        try:
            if self._exp_control_panel is not None:
                # если панель показана/существует — поднимаем над остальными оверлеями
                if hasattr(self._exp_control_panel, "frame") and self._exp_control_panel.frame.winfo_exists():
                    # не трогаем геометрию здесь — только z-order
                    self._exp_control_panel.frame.lift()
        except Exception:
            pass

        # Лог-панель: БЕЗ ОТСТУПА СЛЕВА (x=0), на всю ширину окна
        if self.log_frame is not None and self.log_frame.winfo_exists():
            try:
                w = max(1, int(self.root.winfo_width()))
                h = max(1, int(self.root.winfo_height()))

                log_h = int(self.LOG_PANEL_HEIGHT)
                if log_h < 50:
                    log_h = 50

                x = 0
                y = max(0, h - log_h)
                width = w

                self.log_frame.place(x=x, y=y, width=width, height=log_h)
                self.log_frame.lift()

                # keep docked panels aligned after log panel reposition
                try:
                    if self._exp_control_panel is not None:
                        fn = getattr(self._exp_control_panel, "reposition", None)
                        if callable(fn):
                            fn()
                except Exception:
                    pass

            except Exception:
                pass


    def get_reserved_margins(self) -> Dict[str, int]:
        """Возвращает зарезервированные отступы (left/top/right/bottom) под оверлеи.

        Сейчас учитывается:
        - панель инструментов (кнопки Пуск/Пауза/Стоп), если она отображается;
        - окно логирования снизу (если отображается).
        """
        left = top = right = bottom = 0

        try:
            rw = max(1, int(self.root.winfo_width()))
            rh = max(1, int(self.root.winfo_height()))
        except Exception:
            return {"left": 0, "top": 0, "right": 0, "bottom": 0}

        # Reserve area for the toolbar panel if it is visible
        try:
            tb = None
            if getattr(self, "_toolbar", None) is not None:
                tb = getattr(self._toolbar, "frame", None)

            if (
                tb is not None
                and tb.winfo_exists()
                and tb.winfo_ismapped()
                and bool(self.window_visibility.get("icon_toolbar", True))
            ):
                x = int(tb.winfo_x())
                y = int(tb.winfo_y())
                w = max(1, int(tb.winfo_width()))
                h = max(1, int(tb.winfo_height()))

                # Determine whether the toolbar is docked vertically or horizontally
                if h >= int(rh * 0.7):  # vertical dock (left/right)
                    if x <= rw // 2:
                        left = max(left, x + w)
                    else:
                        right = max(right, max(0, rw - x))
                elif w >= int(rw * 0.7):  # horizontal dock (top/bottom)
                    if y <= rh // 2:
                        top = max(top, y + h)
                    else:
                        bottom = max(bottom, max(0, rh - y))
                else:
                    # Floating small panel: reserve by nearest edges (future-proof)
                    edge_pad = 8
                    if x <= edge_pad:
                        left = max(left, x + w)
                    if y <= edge_pad:
                        top = max(top, y + h)
                    if (x + w) >= (rw - edge_pad):
                        right = max(right, max(0, rw - x))
                    if (y + h) >= (rh - edge_pad):
                        bottom = max(bottom, max(0, rh - y))
        except Exception:
            pass

        # Reserve area for the bottom log panel (if visible)
        try:
            lf = getattr(self, "log_frame", None)
            if lf is not None and lf.winfo_exists() and lf.winfo_ismapped():
                log_h = int(getattr(self, "LOG_PANEL_HEIGHT", 0) or 0)
                if log_h > 0:
                    bottom = max(bottom, log_h)
        except Exception:
            pass

        return {
            "left": int(max(0, left)),
            "top": int(max(0, top)),
            "right": int(max(0, right)),
            "bottom": int(max(0, bottom)),
        }

    def rebuild_interface(self):
        self._resize_background()
        self.setup_toolbar()
        self.setup_experiment_dashboard_panel()
        self.setup_log_panel()
        self._layout_overlays()

    # -------------------------
    # logging API
    # -------------------------

    # -------------------------
    # Log panel height resizing (drag the top border)
    # -------------------------
    def _on_log_resize_start(self, event=None):
        try:
            self._log_resize_active = True
            self._log_resize_start_y = int(getattr(event, "y_root", 0) or 0)
            self._log_resize_start_h = int(getattr(self, "LOG_PANEL_HEIGHT", 100) or 100)
        except Exception:
            self._log_resize_active = False

    def _on_log_resize_move(self, event=None):
        if not getattr(self, "_log_resize_active", False):
            return
        try:
            y_root = int(getattr(event, "y_root", 0) or 0)
            dy = y_root - int(getattr(self, "_log_resize_start_y", 0) or 0)
            # dragging up (dy < 0) should increase log height, dragging down decreases
            new_h = int(getattr(self, "_log_resize_start_h", 100) or 100) - dy

            # clamp
            try:
                rh = max(1, int(self.root.winfo_height()))
            except Exception:
                rh = 1
            min_h = 60
            max_h = max(min_h, rh - 200)
            new_h = max(min_h, min(int(new_h), int(max_h)))

            self.LOG_PANEL_HEIGHT = int(new_h)
            self._layout_overlays()
            self.save_settings()
        except Exception:
            pass

    def _on_log_resize_end(self, _event=None):
        self._log_resize_active = False
        try:
            self.save_settings()
        except Exception:
            pass


    def add_log_entry(self, text: str, level: str = "INFO"):
        try:
            msg = f"[{level}] {text}\n"
        except Exception:
            msg = f"[INFO] {text}\n"

        try:
            print(msg, end="")
        except Exception:
            pass

        try:
            if self.log_text is not None and self.log_text.winfo_exists():
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.insert("end", msg)
                self.log_text.see("end")
                self.log_text.configure(state=tk.DISABLED)
        except Exception:
            pass

    # -------------------------
    # stubs for menu_bar.py
    # -------------------------

    def _ui_not_ready(self):
        messagebox.showinfo(
            "Рабочая область",
            "Сейчас включён режим макета: фон + меню + панель инструментов + лог.\n"
            "Остальные панели будут возвращаться по шагам."
        )

    def create_new_experiment(self):
        self.add_log_entry("Новый эксперимент", "INFO")
        self._ui_not_ready()

    def menu_open_experiment(self):
        self.add_log_entry("Открыть эксперимент", "INFO")
        self._ui_not_ready()

    def save_experiment(self):
        self.add_log_entry("Сохранить эксперимент", "INFO")
        self._ui_not_ready()

    # -------------------------
    # Pre-start validation
    # -------------------------

    
    def set_experiment_settings_applied(self, applied: bool):
        try:
            self.experiment_settings_applied = bool(applied)
        except Exception:
            self.experiment_settings_applied = False

        # После смены статуса — обновим панель управления (чекпоинты/отображение)
        try:
            if self._exp_control_panel is not None:
                self._exp_control_panel.refresh_all()
        except Exception:
            pass

    def is_experiment_settings_applied(self) -> bool:
        try:
            return bool(getattr(self, "experiment_settings_applied", False))
        except Exception:
            return False

    def validate_experiment_before_start(self) -> bool:
        """Проверка обязательных настроек перед запуском эксперимента.

        Логика:
        - обязательны выбор посуды/реактора, среды, культуры;
        - имя эксперимента не пустое, длительность > 0;
        - числовые параметры должны быть корректны (диапазоны);
        - газовая смесь должна быть задана и давать 100% (допуск ±0.5%).
        """
        missing: list[str] = []
        issues: list[str] = []

        # Настройки должны быть применены перед запуском
        if not self.is_experiment_settings_applied():
            missing.append("Настройки эксперимента не применены (нажмите 'Применить')")

        # --- обязательные выборы из справочников
        try:
            vessel_id = str(self.vessel_id_var.get()).strip()
        except Exception:
            vessel_id = ""
        try:
            medium_id = str(self.medium_id_var.get()).strip()
        except Exception:
            medium_id = ""
        try:
            culture_id = str(self.culture_id_var.get()).strip()
        except Exception:
            culture_id = ""

        if not vessel_id:
            missing.append("Посуда / реактор")
        if not medium_id:
            missing.append("Среда")
        if not culture_id:
            missing.append("Изначальная культура")

        # --- имя эксперимента, длительность
        try:
            exp_name = str(self.exp_name_var.get()).strip()
        except Exception:
            exp_name = ""
        if not exp_name:
            issues.append("Название эксперимента не задано")

        try:
            dur = int(self.duration_var.get())
            if dur <= 0:
                issues.append("Длительность должна быть больше 0")
        except Exception:
            issues.append("Длительность задана некорректно")

        # --- числовые параметры (базовые условия)
        def _get_float(var_name: str, label: str, min_v: float | None = None, max_v: float | None = None):
            try:
                v = getattr(self, var_name, None)
                raw = v.get() if hasattr(v, "get") else v
                val = float(raw)
            except Exception:
                issues.append(f"{label}: некорректное значение")
                return

            if min_v is not None and val < min_v:
                issues.append(f"{label}: значение меньше {min_v:g}")
            if max_v is not None and val > max_v:
                issues.append(f"{label}: значение больше {max_v:g}")

        def _get_int(var_name: str, label: str, min_v: int | None = None, max_v: int | None = None):
            try:
                v = getattr(self, var_name, None)
                raw = v.get() if hasattr(v, "get") else v
                val = int(raw)
            except Exception:
                issues.append(f"{label}: некорректное значение")
                return

            if min_v is not None and val < min_v:
                issues.append(f"{label}: значение меньше {min_v}")
            if max_v is not None and val > max_v:
                issues.append(f"{label}: значение больше {max_v}")

        _get_float("temperature_c_var", "Температура (°C)", -20.0, 120.0)

        # Влажность только если включена (для реакторов отключается)
        try:
            hum_enabled = bool(self.humidity_enabled_var.get())
        except Exception:
            hum_enabled = True
        if hum_enabled:
            _get_int("humidity_var", "Влажность (%)", 0, 100)

        _get_float("ph_var", "pH", 0.0, 14.0)
        _get_float("do_var", "DO (%)", 0.0, 100.0)
        _get_float("osmolality_var", "Осмолярность (mOsm/kg)", 0.0, 20000.0)
        _get_float("glucose_var", "Глюкоза (g/L)", 0.0, 100000.0)

        _get_int("stirring_rpm_var", "Перемешивание (RPM)", 0, 300000)
        _get_float("aeration_lpm_var", "Аэрация (L/min)", 0.0, 100000.0)
        _get_float("feed_rate_var", "Подача (mL/h)", 0.0, 1000000.0)
        _get_float("harvest_rate_var", "Отбор (mL/h)", 0.0, 1000000.0)

        _get_float("light_lux_var", "Освещённость (lux)", 0.0, 10000000.0)

        # --- газы: должны давать 100% (допуск ±0.5%)
        cfg = self._collect_current_gases_config()
        if not cfg:
            issues.append("Газовая смесь не задана")
        else:
            total = 0.0
            bad_keys = []
            for k, v in cfg.items():
                try:
                    fv = float(v)
                except Exception:
                    bad_keys.append(str(k))
                    continue
                if fv < 0.0 or fv > 100.0:
                    issues.append(f"Газы: {k} должно быть в диапазоне 0–100%")
                total += fv
            if bad_keys:
                issues.append("Газы: некорректные значения для " + ", ".join(bad_keys))

            tol = 0.5
            if abs(total - 100.0) > tol:
                issues.append(f"Газы: суммарная концентрация = {total:g}% (должно быть 100% ±{tol:g}%)")

        if not missing and not issues:
            return True

        # Сообщение пользователю
        parts = []
        if missing:
            parts.append("Не выбрано:")
            parts.extend([f"  • {x}" for x in missing])
        if issues:
            parts.append("Некорректные/неполные значения:")
            parts.extend([f"  • {x}" for x in issues])
        msg = "\n".join(parts) if parts else "Не удалось проверить настройки."

        try:
            messagebox.showwarning("Запуск эксперимента", msg)
        except Exception:
            pass

        try:
            # В лог — одной строкой, чтобы не разрывать формат
            log_msg = "Запуск отклонён: " + ("; ".join(missing + issues) if (missing or issues) else "ошибка проверки")
            self.add_log_entry(log_msg, "ERROR")
        except Exception:
            pass

        return False

    def start_simulation(self):
        # Всегда фиксируем applied-снимок перед запуском (точка отсчёта)
        try:
            self.apply_settings()
        except Exception:
            pass

        # Проверяем обязательные настройки (справочники/условия/газы) перед запуском
        if not self.validate_experiment_before_start():
            return

        self._experiment_running = True
        self._sim_paused = False

        # На старте runtime = applied (точка отсчёта)
        self.runtime_settings = dict(self.applied_settings or {})
        self.runtime_gases_config = dict(self.applied_gases_config or {})
        self._runtime_gases_staged = {}

        # Движок: инициализация + таймер шага
        try:
            self._engine_init_for_run()
        except Exception:
            self._engine = None
            try:
                import traceback
                tb = traceback.format_exc()
                self.add_log_entry("Движок не запущен: ошибка инициализации", "ERROR")
                # печатаем кратко причину (последняя строка traceback)
                try:
                    last = (tb.strip().splitlines()[-1] if tb else "")
                except Exception:
                    last = ""
                if last:
                    self.add_log_entry(last, "ERROR")
            except Exception:
                pass

        try:
            self._start_engine_loop()
        except Exception:
            pass

        # Графики: новый прогон + запуск периодической записи точек
        self._reset_plot_series_for_new_run()
        self._start_plot_sampling()

        try:
            self.add_log_entry("Старт симуляции", "INFO")
        except Exception:
            pass

        if self._exp_control_panel is not None:
            try:
                self._exp_control_panel.set_running(True, False)
            except Exception:
                pass

    def toggle_pause_simulation(self):
        if not self._experiment_running:
            # если не запущено — просто переключаем флаг (на будущее)
            self._sim_paused = not self._sim_paused
        else:
            self._sim_paused = not self._sim_paused

        try:
            self.add_log_entry("Пауза" if self._sim_paused else "Продолжить", "INFO")
        except Exception:
            pass

        if self._exp_control_panel is not None:
            try:
                self._exp_control_panel.set_running(bool(self._experiment_running), bool(self._sim_paused))
            except Exception:
                pass

    def stop_simulation(self):
        self._experiment_running = False
        self._sim_paused = False

        # Графики: остановить запись точек
        self._stop_plot_sampling()
        # Движок: остановить таймер и сбросить экземпляр
        try:
            self._stop_engine_loop()
        except Exception:
            pass
        try:
            self._engine = None
        except Exception:
            pass
        try:
            self.add_log_entry("Остановить симуляцию", "INFO")
        except Exception:
            pass

        # По остановке runtime возвращаем к applied (как базовое состояние)
        try:
            self.runtime_settings = dict(self.applied_settings or {})
            self.runtime_gases_config = dict(self.applied_gases_config or {})
            self._runtime_gases_staged = {}
        except Exception:
            pass

        if self._exp_control_panel is not None:
            try:
                self._exp_control_panel.set_running(False, False)
            except Exception:
                pass

    def reset_simulation(self):
        self.add_log_entry("Сброс симуляции", "INFO")
        self._ui_not_ready()

    def open_analysis(self):
        self.add_log_entry("Открыть анализ", "INFO")
        self._ui_not_ready()

    def export_results(self):
        self.add_log_entry("Экспорт результатов", "INFO")
        self._ui_not_ready()

    def apply_settings(self):
        """Применить настройки из панели настроек.

        Снимок значений сохраняется как "applied" и (если эксперимент не запущен) переносится в runtime.
        """
        snap = self._collect_current_condition_settings()
        self.applied_settings = dict(snap)
        self.applied_gases_config = dict(self._collect_current_gases_config())

        # Для мониторинга ожидается ключ volume_ml (мл)
        try:
            vv = (self.applied_settings or {}).get("vessel_volume", 0.0)
            vt = (self.applied_settings or {}).get("vessel_type", "")
            vn = (self.applied_settings or {}).get("vessel_name", "")
            v_ml = float(self._normalize_volume_to_ml(vv, vt, vn))
            self.applied_settings["volume_ml"] = v_ml
            # DO: отделяем уставку от фактического значения
            try:
                if "do_setpoint" not in self.applied_settings and "do_percent" in self.applied_settings:
                    self.applied_settings["do_setpoint"] = float(self.applied_settings.get("do_percent") or 0.0)
            except Exception:
                pass
            # фиксируем нормализованный объём в applied_settings, чтобы везде был единый формат (мл)
            self.applied_settings["vessel_volume"] = v_ml
            self.applied_settings["vessel_volume_l"] = v_ml / 1000.0
            self.applied_settings["vessel_volume_unit"] = "ml"
        except Exception:
            self.applied_settings["volume_ml"] = 0.0

        # Применение настроек фиксируем флагом (нужно для валидации запуска и чекпоинтов графиков)
        self.set_experiment_settings_applied(True)

        # Если эксперимент не запущен — runtime копируется из applied
        if not self._experiment_running:
            self.runtime_settings = dict(self.applied_settings)
            self.runtime_gases_config = dict(self.applied_gases_config)
            self._runtime_gases_staged = {}
        else:
            # Если эксперимент уже идёт — применяем новые уставки к runtime и движку
            try:
                if not isinstance(self.runtime_settings, dict):
                    self.runtime_settings = {}
                self.runtime_settings.update(dict(self.applied_settings))
            except Exception:
                pass
            try:
                self.runtime_gases_config = dict(self.applied_gases_config)
            except Exception:
                pass
            try:
                self._engine_apply_runtime_controls_to_model()
            except Exception:
                pass

        try:
            self.add_log_entry("Настройки применены", "SUCCESS")
        except Exception:
            try:
                self.add_log_entry("Настройки применены", "INFO")
            except Exception:
                pass

        # Обновить панель управления (если создана)
        if self._exp_control_panel is not None:
            try:
                self._exp_control_panel.refresh_all()
            except Exception:
                pass

    
    def _collect_current_gases_config(self) -> Dict[str, float]:
        cfg: Dict[str, float] = {}
        try:
            if isinstance(getattr(self, "gases_config", None), dict):
                for k, v in getattr(self, "gases_config", {}).items():
                    try:
                        cfg[str(k)] = float(v)
                    except Exception:
                        cfg[str(k)] = 0.0
        except Exception:
            cfg = {}
        return cfg

    def _normalize_volume_to_ml(self, volume_value: object, vessel_type: str = "", vessel_name: str = "") -> float:
        """Нормализует объём сосуда к мл.

        В разных справочниках объём может храниться как в мл, так и в литрах.
        Здесь реализована безопасная эвристика:
        - если значение >= 100 — считаем, что это уже мл;
        - если тип/название явно указывает на литры или на биореактор — переводим в мл;
        - если значение <= 5 и это не "мелкая посуда" — считаем литрами.
        """
        try:
            v = float(volume_value)
        except Exception:
            return 10.0

        if v <= 0:
            return 10.0

        t = (vessel_type or "").strip().lower()
        n = (vessel_name or "").strip().lower()

        # 1) явные признаки литров
        has_l_mark = (" литр" in n) or ("литров" in n) or (" л" in f" {n}") or (" l" in f" {n}") or ("liter" in n)

        # 2) типы посуды
        is_bioreactor = any(k in t for k in ("биореактор", "реактор", "фермент", "bioreactor", "reactor", "ferment"))
        is_smallware = any(k in t for k in ("чаш", "петри", "флакон", "планш", "пробир", "dish", "petri", "flask", "plate", "tube"))

        # Если уже похоже на мл
        if v >= 100:
            return v

        # Если явно литры или биореактор (и не мелкая посуда) — переводим в мл
        if has_l_mark or (is_bioreactor and not is_smallware):
            return v * 1000.0

        # Осторожная эвристика для "малых" значений: 0.5, 1, 2, 5 часто означают литры
        if v <= 5 and not is_smallware:
            return v * 1000.0

        # Иначе считаем, что это мл
        return v

    def _collect_current_condition_settings(self) -> Dict[str, Any]:
        # Берём значения из переменных, которые создает ExperimentSettingsPanel
        def _get(name: str, default: Any) -> Any:
            try:
                var = getattr(self, name, None)
                if var is None:
                    return default
                if hasattr(var, "get"):
                    return var.get()
                return var
            except Exception:
                return default

        # --- Нормализация объёма сосуда ---
        vessel_type = str(_get("vessel_type_var", "") or "")
        vessel_name = str(_get("vessel_name_var", "Не выбрано") or "Не выбрано")
        try:
            raw_vessel_volume = float(_get("vessel_volume_var", 0.0) or 0.0)
        except Exception:
            raw_vessel_volume = 0.0

        vessel_volume_ml = self._normalize_volume_to_ml(raw_vessel_volume, vessel_type, vessel_name)
        vessel_volume_l = (vessel_volume_ml / 1000.0) if vessel_volume_ml else 0.0



        # --- Заселение культуры (×10^6): поддержка альтернативных имён переменных ---
        inoc_mln = None
        try:
            inoc_mln = float(_get("culture_inoculation_mln_var", 1.0))
        except Exception:
            inoc_mln = 1.0

        # Если в проекте используется другое имя переменной — подхватываем его
        _alt_names = [
            "inoculation_mln_var",
            "inoc_mln_var",
            "culture_inoc_mln_var",
            "inoculum_mln_var",
            "initial_biomass_mln_var",
        ]
        for _n in _alt_names:
            try:
                if hasattr(self, _n) and getattr(self, _n) is not None:
                    _v = getattr(self, _n)
                    _vv = float(_v.get() if hasattr(_v, "get") else _v)
                    # предпочитаем альтернативу, если основной — значение по умолчанию
                    if (inoc_mln == 1.0 and _vv != 1.0) or inoc_mln is None:
                        inoc_mln = _vv
                        # делаем алиас, чтобы дальше везде использовалась одна переменная
                        try:
                            setattr(self, "culture_inoculation_mln_var", _v)
                        except Exception:
                            pass
                        break
            except Exception:
                continue

        inoc_mln = float(inoc_mln or 0.0)
        snap: Dict[str, Any] = {
            "temperature_c": float(_get("temperature_c_var", 37.0)),
            "vessel_id": str(_get("vessel_id_var", "")),
            "vessel_name": vessel_name,
            "vessel_type": vessel_type,
            "vessel_volume": float(vessel_volume_ml),
            "vessel_volume_raw": float(raw_vessel_volume),
            "vessel_volume_l": float(vessel_volume_l),
            "vessel_volume_unit": "ml",
            "medium_id": str(_get("medium_id_var", "")),
            "medium_name": str(_get("medium_name_var", "Не выбрано")),
            "culture_id": str(_get("culture_id_var", "")),
            "culture_name": str(_get("culture_name_var", "Не выбрано")),

            "culture_inoculation_mln": float(inoc_mln),
            "culture_inoculation_cells": float(inoc_mln) * 1000000.0,
            "glucose_added_mg_total": float(_get("glucose_added_total_mg_var", 0.0)),

            "humidity": int(_get("humidity_var", 60)),
            "humidity_enabled": bool(_get("humidity_enabled_var", True)),
            "ph": float(_get("ph_var", 7.4)),
            "ph_setpoint": float(_get("ph_var", 7.4)),
            "do_setpoint": float(_get("do_var", 100.0)),
            "do_percent": float(_get("do_var", 100.0)),
            "osmolality": float(_get("osmolality_var", 300.0)),
            "glucose": float(_get("glucose_var", 0.0)),
            "stirring_rpm": int(_get("stirring_rpm_var", 0)),
            "aeration_lpm": float(_get("aeration_lpm_var", 0.0)),
            "feed_rate": float(_get("feed_rate_var", 0.0)),
            "harvest_rate": float(_get("harvest_rate_var", 0.0)),
            "light_lux": float(_get("light_lux_var", 0.0)),
            "light_cycle": str(_get("light_cycle_var", "")),
        }
        return snap

    # -------------------------
    # Control panel getters
    # -------------------------
    def get_applied_parameter(self, key: str) -> Any:
        return (self.applied_settings or {}).get(key)

    def get_runtime_parameter(self, key: str) -> Any:
        return (self.runtime_settings or {}).get(key)

    def get_applied_gases_config(self) -> Dict[str, float]:
        return dict(self.applied_gases_config or {})

    def get_runtime_gases_config(self) -> Dict[str, float]:
        return dict(self.runtime_gases_config or {})

    def set_runtime_gases_config_staged(self, cfg: Dict[str, float]):
        if isinstance(cfg, dict):
            self._runtime_gases_staged = dict(cfg)

    def apply_runtime_parameter(self, key: str, value: Any):
        # применяем только во время эксперимента
        if not self._experiment_running:
            return
        if not isinstance(self.runtime_settings, dict):
            self.runtime_settings = {}
        self.runtime_settings[str(key)] = value

        try:
            self._engine_apply_runtime_controls_to_model()
        except Exception:
            pass

        # Если параметр отмечен чекпоинтом — добавляем точку сразу
        try:
            if bool(getattr(self, "plot_checkpoints", {}).get(str(key), False)):
                self._ensure_plot_panel()
                self._append_plot_sample(str(key), value)
        except Exception:
            pass
        self._push_control_protocol(f"{key} = {value}")
        try:
            self.add_log_entry(f"Изменение параметра: {key} = {value}", "INFO")
        except Exception:
            pass


    def add_glucose_mg(self, mg: float):
        """Внести глюкозу (мг). Обновляет накопительную сумму и, по возможности,
        корректирует текущий параметр glucose.

        Примечание: единицы `glucose` в модели могут отличаться. Здесь применяется
        консервативная логика: добавляем mg/volume_ml к текущему значению.
        """
        try:
            mg_val = float(mg)
        except Exception:
            return
        if mg_val <= 0:
            return

        # Обновляем сумму (и в runtime, и в UI-переменной)
        try:
            if not isinstance(self.runtime_settings, dict):
                self.runtime_settings = dict(self.applied_settings or {})
        except Exception:
            self.runtime_settings = {}

        try:
            cur_total = float(self.runtime_settings.get('glucose_added_mg_total', 0.0) or 0.0)
        except Exception:
            cur_total = 0.0
        new_total = cur_total + mg_val
        self.runtime_settings['glucose_added_mg_total'] = new_total

        try:
            if hasattr(self, 'glucose_added_total_mg_var'):
                self.glucose_added_total_mg_var.set(new_total)
        except Exception:
            pass

        # Попытка изменить текущий glucose
        try:
            vol_ml = float(self.runtime_settings.get('volume_ml', 0.0) or 0.0)
        except Exception:
            vol_ml = 0.0
        if vol_ml <= 0:
            try:
                vol_ml = float((self.applied_settings or {}).get('volume_ml', 0.0) or 0.0)
            except Exception:
                vol_ml = 0.0
        if vol_ml <= 0:
            vol_ml = 1.0

        try:
            cur_glu = float(self.runtime_settings.get('glucose', 0.0) or 0.0)
        except Exception:
            cur_glu = 0.0

        # Пересчёт: mg добавленной глюкозы -> ΔC (мг/л) относительно текущего объёма (мл)
        # ΔC(мг/л) = mg * 1000 / volume_ml
        delta = (mg_val * 1000.0) / vol_ml
        new_glu = cur_glu + delta
        self.runtime_settings['glucose'] = new_glu

        try:
            self._engine_apply_runtime_controls_to_model()
        except Exception:
            pass

        # Если параметр отмечен чекпоинтом — добавляем точку
        try:
            if bool(getattr(self, 'plot_checkpoints', {}).get('glucose', False)):
                self._ensure_plot_panel()
                self._append_plot_sample('glucose', new_glu)
        except Exception:
            pass

        self._push_control_protocol(f"glucose += {mg_val} mg (total {new_total} mg)")
        try:
            self.add_log_entry(f"Внесение глюкозы: +{mg_val:.0f} мг (итого {new_total:.0f} мг)", "INFO")
        except Exception:
            pass

    def apply_runtime_gases(self):
        if not self._experiment_running:
            return
        staged = dict(self._runtime_gases_staged or {})
        if staged:
            self.runtime_gases_config = dict(staged)
            self._runtime_gases_staged = {}
        else:
            # если не было staged — ничего не делаем
            pass
        self._push_control_protocol("gases = " + self._format_gases(self.runtime_gases_config))
        try:
            self._engine_apply_runtime_controls_to_model()
        except Exception:
            pass
        try:
            self.add_log_entry("Изменение газовой смеси (runtime)", "INFO")
        except Exception:
            pass

    def reset_runtime_to_applied(self):
        # сброс уставок к базовым (можно и до запуска)
        self.runtime_settings = dict(self.applied_settings or {})
        self.runtime_gases_config = dict(self.applied_gases_config or {})
        self._runtime_gases_staged = {}
        self._push_control_protocol("Сброс runtime к applied")
        try:
            self.add_log_entry("Сброс уставок к базовым", "INFO")
        except Exception:
            pass

    def safe_mode_runtime(self):
        # безопасный режим = полный сброс runtime к applied
        self.reset_runtime_to_applied()
        self._push_control_protocol("Безопасный режим")

    def _format_gases(self, cfg: Dict[str, float]) -> str:
        if not cfg:
            return "—"
        parts = []
        for k, v in cfg.items():
            try:
                parts.append(f"{k} {float(v):.2f}%".rstrip("0").rstrip("."))
            except Exception:
                parts.append(f"{k} {v}%")
        return ", ".join(parts)

    # -------------------------
    # Protocol (mini-history inside control panel)
    # -------------------------
    def _push_control_protocol(self, text: str):
        try:
            lst = getattr(self, "_experiment_control_protocol", None)
            if not isinstance(lst, list):
                lst = []
                self._experiment_control_protocol = lst
        except Exception:
            self._experiment_control_protocol = []
            lst = self._experiment_control_protocol

        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        lst.append(f"{ts}  {text}")
        # keep list size reasonable
        if len(lst) > 200:
            del lst[:-200]

    def get_experiment_control_protocol(self):
        try:
            return list(getattr(self, "_experiment_control_protocol", []) or [])
        except Exception:
            return []

    def update_visualization(self):
        self.add_log_entry("Обновить визуализацию", "INFO")
        self._ui_not_ready()

    def capture_image(self):
        self.add_log_entry("Снимок", "INFO")
        self._ui_not_ready()

    def search_log(self):
        self.add_log_entry("Поиск в логе", "INFO")
        self._ui_not_ready()

    def clear_log(self):
        self.add_log_entry("Очистка лога", "INFO")
        if self.log_text is not None and self.log_text.winfo_exists():
            try:
                self.log_text.configure(state=tk.NORMAL)
                self.log_text.delete("1.0", "end")
                self.log_text.configure(state=tk.DISABLED)
            except Exception:
                pass

    def add_microorganism(self):
        self.add_log_entry("Добавить микроорганизм", "INFO")
        self._ui_not_ready()

    def add_nutrient(self):
        self.add_log_entry("Добавить питательную среду", "INFO")
        self._ui_not_ready()

    def open_window_settings_dialog(self):
        self.add_log_entry("Настройки окон", "INFO")
        self._ui_not_ready()

    def export_settings(self):
        self.add_log_entry("Экспорт настроек", "INFO")
        self._ui_not_ready()

    def import_settings(self):
        self.add_log_entry("Импорт настроек", "INFO")
        self._ui_not_ready()

    def reset_settings(self):
        self.add_log_entry("Сброс настроек", "INFO")
        self._ui_not_ready()

    def return_to_main_menu(self):
        self.on_close()

    def show_about(self):
        messagebox.showinfo("О программе", "VitaLens — рабочая область (этап макета)")

    def on_close(self):
        # Графики: остановить таймер
        try:
            self._stop_plot_sampling()
        except Exception:
            pass

        try:
            if self._toolbar is not None:
                self._toolbar.destroy()
                self._toolbar = None
        except Exception:
            pass
        try:
            if self._exp_dashboard_panel is not None:
                self._exp_dashboard_panel.destroy()
                self._exp_dashboard_panel = None
        except Exception:
            pass

        try:
            if self.log_frame is not None and self.log_frame.winfo_exists():
                self.log_frame.destroy()
        except Exception:
            pass
        # Сохраняем положение/режим панели графиков
        try:
            if getattr(self, "_plot_panel", None) is not None and hasattr(self._plot_panel, "get_state"):
                st = self._plot_panel.get_state()
                if isinstance(st, dict):
                    self._plot_panel_state = dict(st)
        except Exception:
            pass

        try:
            self.save_settings()
        except Exception:
            pass

        self.root.destroy()


    # =====================================================================
    # Growth monitoring window (F8)
    # =====================================================================

    # -------------------------
    # Overlay z-order helpers (графики / рост культуры)
    # -------------------------
    def _get_plot_panel_widget(self):
        """Пытается получить tk.Widget, отвечающий за окно/панель графиков."""
        pp = getattr(self, "_plot_panel", None)
        if pp is None:
            return None
        for attr in ("win", "window", "toplevel", "top", "root"):
            try:
                w = getattr(pp, attr, None)
                if w is not None and hasattr(w, "lift") and hasattr(w, "bind"):
                    return w
            except Exception:
                continue
        if hasattr(pp, "lift") and hasattr(pp, "bind"):
            return pp
        return None

    def _bind_raise_recursive(self, widget, target: str):
        """Поднимает выбранное окно поверх остальных при клике/фокусе, рекурсивно по детям."""
        if widget is None:
            return

        def _raise(_e=None):
            try:
                self._raise_overlay(target)
            except Exception:
                pass

        try:
            widget.bind("<Button-1>", _raise, add="+")
            widget.bind("<FocusIn>", _raise, add="+")
        except Exception:
            pass

        try:
            for ch in widget.winfo_children():
                self._bind_raise_recursive(ch, target)
        except Exception:
            pass

    def _raise_overlay(self, target: str):
        """Поднимает выбранное окно/панель поверх остальных оверлеев."""
        target = str(target or "").strip().lower()
        ppw = self._get_plot_panel_widget()
        gw = getattr(self, "_culture_growth_win", None)

        try:
            if target == "plot" and ppw is not None:
                ppw.lift()
            if target == "growth" and gw is not None:
                gw.lift()
        except Exception:
            pass

        # Форсируем порядок для Toplevel (на некоторых WM помогает)
        try:
            if target == "plot" and ppw is not None and isinstance(ppw, tk.Toplevel):
                ppw.attributes("-topmost", True)
                ppw.attributes("-topmost", False)
            if target == "growth" and gw is not None and isinstance(gw, tk.Toplevel):
                gw.attributes("-topmost", True)
                gw.attributes("-topmost", False)
        except Exception:
            pass


    def open_culture_growth_table(self):

        """Открыть окно мониторинга роста культуры (F8)."""
        try:
            from culture_growth_table import CultureGrowthTable  # type: ignore
        except Exception:
            try:
                from .culture_growth_table import CultureGrowthTable  # type: ignore
            except Exception:
                CultureGrowthTable = None  # type: ignore

        if CultureGrowthTable is None:
            try:
                messagebox.showwarning("Рост культуры", "Не удалось открыть окно мониторинга (culture_growth_table.py не найден).")
            except Exception:
                pass
            return

        # Если окно уже открыто — поднимаем его наверх
        try:
            w0 = getattr(self, "_culture_growth_win", None)
            if w0 is not None and hasattr(w0, "winfo_exists") and w0.winfo_exists():
                try:
                    w0.deiconify()
                except Exception:
                    pass
                try:
                    w0.lift()
                    w0.focus_force()
                except Exception:
                    pass
                try:
                    self._raise_overlay("growth")
                except Exception:
                    pass
                return
        except Exception:
            pass

        try:
            win = tk.Toplevel(self.root)
            win.title("Рост культуры — мониторинг")
            win.geometry("1200x800")
            win.transient(self.root)

            # Немодальное окно (НЕЛЬЗЯ grab_set) — иначе блокируется редактирование параметров.
            self._culture_growth_win = win

            try:
                self._bind_raise_recursive(win, "growth")
            except Exception:
                pass

            try:
                win.lift()
                win.focus_set()
                self._raise_overlay("growth")
            except Exception:
                pass

            def _on_close():
                try:
                    if getattr(self, "_culture_growth_win", None) is win:
                        self._culture_growth_win = None
                except Exception:
                    pass
                try:
                    win.destroy()
                except Exception:
                    pass

            try:
                win.protocol("WM_DELETE_WINDOW", _on_close)
            except Exception:
                pass

            table = CultureGrowthTable(win, self)
            table.pack(fill="both", expand=True)
        except Exception:
            try:
                messagebox.showerror("Рост культуры", "Ошибка при открытии окна мониторинга.")
            except Exception:
                pass


    # =====================================================================
    # Bio-sim engine: загрузка, инициализация, шаг, синхронизация
    # =====================================================================
    def _load_bio_sim_engine_module(self):
        """Загружает bio_sim_engine.py. Возвращает модуль или None."""
        if self._engine_module is not None:
            return self._engine_module

        # 1) обычный импорт (project_root добавлен в sys.path в __init__)
        try:
            # пробуем импорт из пакета core (если движок лежит в core/bio_sim_engine.py)
            try:
                import core.bio_sim_engine as mod  # type: ignore
                self._engine_module = mod
                self._engine_import_error = ""
                return mod
            except Exception:
                pass

            import bio_sim_engine as mod  # type: ignore
            self._engine_module = mod
            self._engine_import_error = ""
            return mod
        except Exception as e:
            self._engine_import_error = f"import bio_sim_engine failed: {e}"

        # 2) загрузка по пути (work_space -> project_root)
        try:
            candidates = [
                os.path.join(self.module_dir, "bio_sim_engine.py"),
                os.path.join(self.project_root, "bio_sim_engine.py"),
                os.path.join(self.project_root, "core", "bio_sim_engine.py"),
                os.path.join(self.project_root, "engine", "bio_sim_engine.py"),
            ]
            for p in candidates:
                if p and os.path.exists(p):
                    spec = importlib.util.spec_from_file_location("bio_sim_engine", p)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                        self._engine_module = mod
                        self._engine_import_error = ""
                        return mod
        except Exception as e:
            self._engine_import_error = f"path load bio_sim_engine failed: {e}"

        return None

    def _engine_get_selected_culture_name(self) -> str:
        try:
            v = getattr(self, "culture_name_var", None)
            if v is not None and hasattr(v, "get"):
                s = str(v.get() or "").strip()
                if s and s.lower() != "не выбрано":
                    return s
        except Exception:
            pass
        try:
            return str((self.applied_settings or {}).get("culture_name", "") or "").strip()
        except Exception:
            return ""

    def _engine_get_selected_culture_id(self) -> str:
        try:
            v = getattr(self, "culture_id_var", None)
            if v is not None and hasattr(v, "get"):
                return str(v.get() or "").strip()
        except Exception:
            pass
        try:
            return str((self.applied_settings or {}).get("culture_id", "") or "").strip()
        except Exception:
            return ""

    def _engine_find_cell_line(self, mod, kb, culture_name: str, culture_id: str, applied: dict):
        """Пытается найти CellLine в KnowledgeBase по имени/ID, иначе создаёт fallback."""
        try:
            cell_lines = getattr(kb, "cell_lines", None)
            if isinstance(cell_lines, dict):
                if culture_id and culture_id in cell_lines:
                    return cell_lines[culture_id]
                needle = (culture_name or "").strip().lower()
                cid_l = (culture_id or "").strip().lower()
                for k, cl in cell_lines.items():
                    try:
                        nm = str(getattr(cl, "name", "")).strip().lower()
                        _id = str(getattr(cl, "id", k)).strip().lower()
                        if needle and (needle == nm or needle in nm):
                            return cl
                        if cid_l and (cid_l == _id or cid_l == str(k).strip().lower()):
                            return cl
                    except Exception:
                        continue
        except Exception:
            pass

        # fallback-профиль (на будущее: заполнится из справочника)
        profile = {}
        try:
            if isinstance(applied.get("culture_profile"), dict):
                profile = dict(applied.get("culture_profile"))
        except Exception:
            profile = {}

        def _f(key: str, default: float) -> float:
            try:
                v = profile.get(key, None)
                if v is None:
                    return float(default)
                return float(v)
            except Exception:
                return float(default)

        opt_t = _f("optimal_temperature", applied.get("temperature_c", 37.0))
        opt_ph = _f("optimal_ph", applied.get("ph", 7.4))

        props = {
            "doubling_time": _f("doubling_time", 24.0),
            "optimal_temperature": opt_t,
            "optimal_ph": opt_ph,
            "max_density": _f("max_density", 2e6),
            "glucose_consumption": _f("glucose_consumption", 0.2),
            "oxygen_consumption": _f("oxygen_consumption", 0.02),
            "lactate_production": _f("lactate_production", 0.1),
            "viability_threshold": _f("viability_threshold", 0.8),
            "apoptosis_threshold": _f("apoptosis_threshold", 0.3),
            "temperature_range": tuple(profile.get("temperature_range", (opt_t - 1.0, opt_t + 1.0))),
            "ph_range": tuple(profile.get("ph_range", (opt_ph - 0.3, opt_ph + 0.3))),
        }

        try:
            EntityType = getattr(mod, "EntityType")
            CellLine = getattr(mod, "CellLine")
            return CellLine(id=(culture_id or culture_name or "culture"), name=(culture_name or culture_id or "Культура"),
                            entity_type=EntityType.CELL_LINE, properties=props)
        except Exception:
            return None

    def _engine_init_for_run(self) -> None:
        """Создаёт экземпляр CultureVessel и популяцию по выбранной культуре."""
        mod = self._load_bio_sim_engine_module()
        if mod is None:
            self._engine = None
            return

        applied = dict(getattr(self, "applied_settings", {}) or {})
        gases = dict(getattr(self, "applied_gases_config", {}) or {})

        try:
            raw_v = applied.get("vessel_volume", 0.0)
            vt = applied.get("vessel_type", "")
            vn = applied.get("vessel_name", "")
            volume_ml = float(self._normalize_volume_to_ml(raw_v, vt, vn))
        except Exception:
            volume_ml = 0.0

        if volume_ml <= 0:
            volume_ml = 10.0
        volume_val = volume_ml  # мл

        # параметры среды
        try:
            temperature = float(applied.get("temperature_c", 37.0))
        except Exception:
            temperature = 37.0
        try:
            ph = float(applied.get("ph_setpoint", applied.get("ph", 7.4)))
        except Exception:
            ph = 7.4
        try:
            do_percent = float(applied.get("do_percent", 100.0))
        except Exception:
            do_percent = 100.0
        oxygen = max(0.0, min(1.0, do_percent / 100.0))

        co2_percent = 0.0
        try:
            for k, v in gases.items():
                if str(k).strip().lower() in ("co2", "co₂"):
                    co2_percent = float(v)
                    break
        except Exception:
            co2_percent = 0.0
        co2 = max(0.0, min(1.0, co2_percent / 100.0))

        try:
            osmolality = float(applied.get("osmolality", 300.0))
        except Exception:
            osmolality = 300.0

        try:
            glucose = float(applied.get("glucose", 0.0))
        except Exception:
            glucose = 0.0

        # создание Environment
        try:
            Environment = getattr(mod, "Environment")
            env = Environment(
                temperature=temperature,
                ph=ph,
                oxygen=oxygen,
                co2=co2,
                volume=volume_val,
                osmolality=osmolality
            )
            try:
                env.update_concentration("glucose", glucose)
            except Exception:
                try:
                    env.concentrations["glucose"] = glucose
                except Exception:
                    pass
        except Exception:
            self._engine = None
            return

        # KnowledgeBase
        kb = None
        try:
            KnowledgeBase = getattr(mod, "KnowledgeBase", None)
            if KnowledgeBase is not None:
                kb = KnowledgeBase()
        except Exception:
            kb = None

        # CultureVessel
        try:
            CultureVessel = getattr(mod, "CultureVessel")
            vessel = CultureVessel(vessel_id="vessel", volume=volume_val, environment=env, knowledge_base=kb)
        except Exception:
            # на некоторых версиях сигнатура может быть другой
            try:
                CultureVessel = getattr(mod, "CultureVessel")
                vessel = CultureVessel(volume=volume_val, environment=env, knowledge_base=kb)
            except Exception:
                vessel = None

        if vessel is None:
            self._engine = None
            return

        culture_name = self._engine_get_selected_culture_name()
        culture_id = self._engine_get_selected_culture_id()
        cl = self._engine_find_cell_line(mod, getattr(vessel, "knowledge_base", None), culture_name, culture_id, applied)

        if cl is None:
            self._engine = None
            return

        # Заселение культуры (Численность ×10^6) -> initial_count
        try:
            inoc_cells = float((getattr(self, "runtime_settings", {}) or {}).get("culture_inoculation_cells", 0.0) or 0.0)
        except Exception:
            inoc_cells = 0.0
        if inoc_cells <= 0.0:
            try:
                inoc_mln = float((getattr(self, "runtime_settings", {}) or {}).get("culture_inoculation_mln", 0.0) or 0.0)
            except Exception:
                inoc_mln = 0.0
            inoc_cells = float(inoc_mln) * 1000000.0

        # Начальная биомасса: runtime может хранить как клетки (biomass_cells),
        # либо как ×10^6 (biomass). Приводим к абсолютному числу клеток.
        try:
            rt0 = (getattr(self, "runtime_settings", {}) or {})
        except Exception:
            rt0 = {}
        try:
            init_biomass = float(rt0.get("biomass_cells", 0.0) or 0.0)
        except Exception:
            init_biomass = 0.0
        if init_biomass <= 0.0:
            try:
                v0 = float(rt0.get("biomass", 0.0) or 0.0)
                # если похоже на значение в ×10^6 — конвертируем
                init_biomass = (v0 * 1000000.0) if v0 > 0.0 and v0 < 100000.0 else v0
            except Exception:
                init_biomass = 0.0

        # приоритет — заселение культуры
        if inoc_cells > 0.0:
            init_biomass = inoc_cells

        # Добавление культуры (инициализация популяции)
        # ВНИМАНИЕ: в текущей реализации core/bio_sim_engine.py volume_added не может быть 0,
        # иначе будет деление на ноль при расчёте концентрации.
        try:
            volume_now = float(getattr(vessel, "volume", 0.0) or 0.0)
        except Exception:
            volume_now = 0.0

        # Объём инокулята (мл): по умолчанию 1 мл, но не больше текущего объёма сосуда, если он задан
        if volume_now > 0:
            inoculum_ml = max(0.1, min(1.0, volume_now))
        else:
            inoculum_ml = 1.0

        try:
            # если у движка есть сигнатура initial_count
            vessel.add_culture(cl, initial_count=max(0.0, init_biomass), concentration=None)
        except Exception:
            try:
                # базовая сигнатура: cell_count / volume_added
                vessel.add_culture(cl, cell_count=max(0.0, init_biomass), volume_added=inoculum_ml, concentration=None)
            except Exception:
                try:
                    # если параметр concentration отсутствует
                    vessel.add_culture(cl, cell_count=max(0.0, init_biomass), volume_added=inoculum_ml)
                except Exception:
                    pass

        self._engine = vessel

        # сразу синхронизируем runtime
        try:
            self._engine_sync_runtime_from_model()
        except Exception:
            pass



    def _engine_apply_runtime_controls_to_model(self) -> None:
        """Прокидывает runtime-настройки (панель управления/газы) в объект движка.
        Нужна, чтобы изменения параметров реально влияли на расчёты роста и среды.
        """
        eng = getattr(self, "_engine", None)
        if eng is None:
            return

        rt = getattr(self, "runtime_settings", None)
        if not isinstance(rt, dict):
            rt = {}

        # --- базовые параметры среды ---
        try:
            env = getattr(eng, "environment", None)
            if env is not None:
                if "temperature_c" in rt:
                    try:
                        env.temperature = float(rt.get("temperature_c"))
                    except Exception:
                        pass
                # pH: фактическое значение может управляться CO2 (авто), уставка хранится отдельно
                ph_sp = None
                try:
                    ph_sp = float(rt.get('ph_setpoint', rt.get('ph', None))) if (rt.get('ph_setpoint', rt.get('ph', None)) is not None) else None
                except Exception:
                    ph_sp = None
                auto_ph = False
                try:
                    v = getattr(self, 'ph_auto_co2_var', None)
                    auto_ph = bool(v.get()) if v is not None else False
                except Exception:
                    auto_ph = False
                if ph_sp is not None:
                    try:
                        setattr(env, 'ph_base', float(ph_sp))
                    except Exception:
                        pass
                    if not auto_ph:
                        try:
                            env.ph = float(ph_sp)
                        except Exception:
                            pass
                if "do_percent" in rt:
                    try:
                        env.oxygen = max(0.0, min(1.5, float(rt.get("do_percent")) / 100.0))
                    except Exception:
                        pass
                if "osmolality" in rt:
                    try:
                        env.osmolality = float(rt.get("osmolality"))
                    except Exception:
                        pass
                if "glucose" in rt:
                    try:
                        # runtime: мг/л -> engine: мг/мл (концентрации в движке задаются на 1 мл)
                        g_mg_l = float(rt.get("glucose"))
                        g_mg_ml = max(0.0, g_mg_l / 1000.0)
                        try:
                            env.concentrations["glucose"] = g_mg_ml
                        except Exception:
                            try:
                                if not hasattr(env, "concentrations") or env.concentrations is None:
                                    env.concentrations = {}
                                env.concentrations["glucose"] = g_mg_ml
                            except Exception:
                                pass
                    except Exception:
                        pass
        except Exception:
            pass

        # --- управление мешалкой/аэрацией/газами ---
        stirring = None
        aeration = None
        try:
            if "stirring_rpm" in rt:
                stirring = float(rt.get("stirring_rpm"))
        except Exception:
            stirring = None
        try:
            if "aeration_lpm" in rt:
                aeration = float(rt.get("aeration_lpm"))
        except Exception:
            aeration = None

        inlet = None
        try:
            gcfg = dict(getattr(self, "runtime_gases_config", {}) or {})
            if gcfg:
                def _get(name, default=None):
                    for k, v in gcfg.items():
                        if str(k).strip().lower() == str(name).strip().lower():
                            return v
                    return default
                o2 = _get("O2", _get("o2", 21.0))
                co2 = _get("CO2", _get("co2", 0.04))
                n2 = _get("N2", _get("n2", None))
                def _norm(x, default):
                    try:
                        xv = float(x)
                    except Exception:
                        return default
                    if xv > 1.5:
                        xv = xv / 100.0
                    return max(0.0, min(1.0, xv))
                o2 = _norm(o2, 0.21)
                co2 = _norm(co2, 0.0004)
                if n2 is None:
                    n2 = max(0.0, 1.0 - o2 - co2)
                else:
                    n2 = _norm(n2, max(0.0, 1.0 - o2 - co2))
                inlet = {"O2": o2, "CO2": co2, "N2": n2}
        except Exception:
            inlet = None

        try:
            if hasattr(eng, "set_controls"):
                eng.set_controls(stirring_rpm=stirring, aeration_lpm=aeration, inlet_gases=inlet)
            else:
                if stirring is not None:
                    setattr(eng, "stirring_rpm", stirring)
                if aeration is not None:
                    setattr(eng, "aeration_lpm", aeration)
                if inlet is not None:
                    setattr(eng, "inlet_gases", inlet)
        except Exception:
            pass

    def _engine_update_ph_by_co2(self) -> None:
        """Простая динамика pH от подачи CO2, используется только при включенном авто-режиме.

        Идея: без CO2 pH имеет слабый дрейф вверх, CO2 снижает pH; также есть буферное
        стремление к уставке (ph_setpoint). Контроллер CO2 реализован в панели мониторинга.
        """
        try:
            v = getattr(self, 'ph_auto_co2_var', None)
            if v is None or not bool(v.get()):
                return
        except Exception:
            return

        eng = getattr(self, '_engine', None)
        if eng is None:
            return

        rt = getattr(self, 'runtime_settings', None)
        if not isinstance(rt, dict):
            return

        env = getattr(eng, 'environment', None)
        if env is None:
            return

        try:
            ph = float(getattr(env, 'ph', rt.get('ph', 7.4)))
        except Exception:
            ph = float(rt.get('ph', 7.4) or 7.4)

        try:
            ph_sp = float(rt.get('ph_setpoint', rt.get('ph', 7.4)))
        except Exception:
            ph_sp = float(rt.get('ph', 7.4) or 7.4)

        # CO2 доля (0..1)
        co2 = 0.0
        try:
            inlet = getattr(eng, 'inlet_gases', None)
            if isinstance(inlet, dict):
                for k, val in inlet.items():
                    if str(k).strip().lower() in ('co2', 'co₂'):
                        co2 = float(val)
                        break
        except Exception:
            co2 = 0.0

        co2 = max(0.0, min(1.0, co2))
        co2_percent = co2 * 100.0

        # параметры динамики (можно позже вынести в настройки)
        drift_up_per_h = 0.004   # дрейф pH вверх без CO2
        k_co2_per_h_per_percent = 0.010  # вклад CO2 (на 1% CO2)
        k_buffer_per_h = 0.120   # буфер к уставке

        try:
            dt_h = float(getattr(self, '_engine_dt_hours', 0.0) or 0.0)
        except Exception:
            dt_h = 0.0
        if dt_h <= 0:
            return

        dpH = (drift_up_per_h - k_co2_per_h_per_percent * co2_percent + k_buffer_per_h * (ph_sp - ph)) * dt_h
        new_ph = ph + dpH
        new_ph = max(0.0, min(14.0, new_ph))

        try:
            env.ph = float(new_ph)
        except Exception:
            pass

    def _engine_step_and_sync(self) -> None:
        eng = getattr(self, "_engine", None)
        if eng is None:
            return
        # применяем runtime-управление к движку (аэрация/мешалка/газы/температура/pH)
        try:
            self._engine_apply_runtime_controls_to_model()
        except Exception:
            pass

        # pH может зависеть от CO2 (авто режим) — обновляем перед шагом
        try:
            self._engine_update_ph_by_co2()
        except Exception:
            pass

        try:
            eng.simulate_step(self._engine_dt_hours)
        except Exception:
            return
        self._engine_sync_runtime_from_model()

    def _engine_sync_runtime_from_model(self) -> None:
        eng = getattr(self, "_engine", None)
        if eng is None:
            return

        rt = getattr(self, "runtime_settings", None)
        if not isinstance(rt, dict):
            return

        try:
            env = getattr(eng, "environment", None)
            if env is not None:
                rt["temperature_c"] = float(getattr(env, "temperature", rt.get("temperature_c", 0.0)))
                rt["ph"] = float(getattr(env, "ph", rt.get("ph", 0.0)))
                try:
                    rt["do_percent"] = float(getattr(env, "oxygen", 0.0)) * 100.0
                except Exception:
                    pass
                try:
                    rt["osmolality"] = float(getattr(env, "osmolality", rt.get("osmolality", 0.0)))
                except Exception:
                    pass
                # Концентрации (engine: мг/мл -> runtime: мг/л)
                try:
                    conc = getattr(env, "concentrations", {}) or {}
                    glu_mg_ml = float(conc.get("glucose", 0.0) or 0.0)
                    rt["glucose"] = max(0.0, glu_mg_ml * 1000.0)
                except Exception:
                    pass
                # CO2 (если доступно в модели)
                try:
                    rt["co2_percent"] = float(getattr(env, "co2", rt.get("co2_percent", 0.0)))
                except Exception:
                    pass
                # Объём (мл) — нужен для таблицы мониторинга
                try:
                    rt["volume_ml"] = float(getattr(eng, "volume", getattr(env, "volume", rt.get("volume_ml", 0.0))))
                except Exception:
                    pass
        except Exception:
            pass

        try:
            pops = getattr(eng, "cell_populations", {}) or {}
            if isinstance(pops, dict) and pops:
                pop = next(iter(pops.values()))
                # Биомасса: показываем в ×10^6 (млн клеток), но сохраняем и абсолютные клетки
                try:
                    cells = float(getattr(pop, "cell_count", 0.0) or 0.0)
                except Exception:
                    cells = 0.0
                rt["biomass_cells"] = cells
                rt["biomass"] = max(0.0, cells / 1000000.0)

                # Жизнеспособность (%)
                try:
                    v = float(getattr(pop, "viability", 0.0) or 0.0)
                except Exception:
                    v = 0.0
                rt["viability_percent"] = max(0.0, min(100.0, v * 100.0))
                # совместимость со старым ключом
                rt["viability"] = rt["viability_percent"]

                # Скорость роста (/ч)
                rt["growth_rate"] = float(getattr(pop, "growth_rate", 0.0) or 0.0)

                # Стресс (0..1)
                rt["stress"] = float(getattr(pop, "stress_level", 0.0) or 0.0)
                rt["stress_level"] = rt["stress"]
                try:
                    gr = float(getattr(pop, "growth_rate", 0.0))
                    if gr > 0:
                        rt["doubling_time_h"] = float(math.log(2.0) / gr)
                except Exception:
                    pass
        except Exception:
            pass

    def _start_engine_loop(self) -> None:
        self._stop_engine_loop()
        try:
            self._engine_loop_job = self.root.after(self._engine_tick_ms, self._engine_loop_tick)
        except Exception:
            self._engine_loop_job = None

    def _stop_engine_loop(self) -> None:
        try:
            if self._engine_loop_job is not None:
                self.root.after_cancel(self._engine_loop_job)
        except Exception:
            pass
        self._engine_loop_job = None

    def _engine_loop_tick(self) -> None:
        try:
            running = bool(getattr(self, "_experiment_running", False))
            paused = bool(getattr(self, "_sim_paused", False))
        except Exception:
            running = False
            paused = False

        if running and (not paused):
            try:
                if getattr(self, "_engine", None) is not None:
                    self._engine_step_and_sync()
            except Exception:
                pass

        try:
            self._engine_loop_job = self.root.after(self._engine_tick_ms, self._engine_loop_tick)
        except Exception:
            self._engine_loop_job = None



    # -------------------------
    # Biomass operations
    # -------------------------
    def add_biomass_mln(self, mln_cells: float) -> None:
        """Добавить биомассу к уже имеющейся (в ×10^6 клеток)."""
        try:
            mln = float(mln_cells)
        except Exception:
            return
        if mln <= 0:
            return
        self.add_biomass_cells(mln * 1000000.0)

    def add_biomass_cells(self, add_cells: float) -> None:
        """Добавить биомассу к уже имеющейся (в клетках)."""
        try:
            add_n = float(add_cells)
        except Exception:
            return
        if add_n <= 0:
            return

        # Гарантируем runtime_settings
        try:
            if not isinstance(self.runtime_settings, dict):
                self.runtime_settings = dict(self.applied_settings or {})
        except Exception:
            self.runtime_settings = {}

        # Обновляем накопительную сумму (млн)
        try:
            prev_total_mln = float((self.runtime_settings or {}).get("biomass_added_total_mln", 0.0) or 0.0)
        except Exception:
            prev_total_mln = 0.0
        new_total_mln = prev_total_mln + (add_n / 1000000.0)
        self.runtime_settings["biomass_added_total_mln"] = new_total_mln
        try:
            if hasattr(self, "biomass_added_total_mln_var") and getattr(self, "biomass_added_total_mln_var") is not None:
                self.biomass_added_total_mln_var.set(float(new_total_mln))
        except Exception:
            pass

        # Движок: увеличиваем количество клеток в первой популяции
        eng = getattr(self, "_engine", None)
        pop_updated = False
        if eng is not None:
            try:
                pops = getattr(eng, "cell_populations", None)
                if isinstance(pops, dict) and pops:
                    pop = next(iter(pops.values()))
                    try:
                        pop.cell_count = float(getattr(pop, "cell_count", 0.0) or 0.0) + add_n
                        pop_updated = True
                    except Exception:
                        pass
            except Exception:
                pass

        # Runtime: обновляем биомассу (в ×10^6)
        try:
            if pop_updated and eng is not None:
                # обновим из модели на следующем тике; но сразу поставим приближённо
                cur_mln = float((self.runtime_settings or {}).get("biomass", 0.0) or 0.0)
                self.runtime_settings["biomass"] = max(0.0, cur_mln + (add_n / 1000000.0))
            else:
                cur_mln = float((self.runtime_settings or {}).get("biomass", 0.0) or 0.0)
                self.runtime_settings["biomass"] = max(0.0, cur_mln + (add_n / 1000000.0))
        except Exception:
            pass

        try:
            self.add_log_entry(f"Добавлена биомасса: {add_n/1000000.0:.2f} ×10^6", "INFO")
        except Exception:
            pass


def run_workspace():
    app = WorkspaceApp()
    app.root.mainloop()


if __name__ == "__main__":
    run_workspace()
