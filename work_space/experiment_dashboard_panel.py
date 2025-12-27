# [file name experiment_dashboard_panel.py]
# Единая панель эксперимента: свойства + уставки + мониторинг
# Встраивается в рабочую область (WorkspaceApp), без отдельного окна.

from __future__ import annotations

import math
import sqlite3
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except Exception:
        return default


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _try_import_reference_module(module_names: List[str]):
    """Пытается импортировать модуль справочника по нескольким именам."""
    last_err = None
    for name in module_names:
        try:
            __import__(name)
            return sys.modules[name]
        except Exception as e:
            last_err = e
    return None


def _get_microbiology_db_path(required_table: str) -> Optional[str]:
    """Находит путь к microbiology.db через существующие справочники (get_db_path)."""
    candidates = [
        ["microorganisms", "database.reference_books.microorganisms"],
        ["culture_media", "database.reference_books.culture_media"],
        ["bioreactor_params", "database.reference_books.bioreactor_params"],
        ["substances", "database.reference_books.substances"],
    ]
    for names in candidates:
        mod = _try_import_reference_module(names)
        if mod is None:
            continue
        fn = getattr(mod, "get_db_path", None)
        if callable(fn):
            try:
                return str(fn(required_table))
            except Exception:
                continue
    return None


def _connect_ro(db_path: str) -> Optional[sqlite3.Connection]:
    try:
        # uri=True позволяет file:... ?mode=ro
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception:
        try:
            return sqlite3.connect(db_path)
        except Exception:
            return None


@dataclass
class TileSpec:
    key: str
    title: str
    unit: str
    current_key: str
    setpoint_key: Optional[str] = None
    var_name: Optional[str] = None  # имя переменной в app (tk.Variable) для уставки до запуска
    fmt: str = "{:.2f}"
    kind: str = "control"  # control | monitor | action


class ExperimentDashboardPanel:
    """Единая панель эксперимента (встроенная)."""

    HEADER_H = 52
    LEFT_W = 360
    PADDING = 10

    TILE_WIDTH = 200  # прямоугольные плитки
    TILE_HEIGHT = 180

    def __init__(
        self,
        parent: tk.Misc,
        app: Any,
        state: Optional[Dict[str, Any]] = None,
        on_state_changed: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.parent = parent
        self.app = app
        self.on_state_changed = on_state_changed

        self.state: Dict[str, Any] = dict(state or {})
        self._limits: Dict[str, Dict[str, Any]] = dict(self.state.get("limits", {}) or {})
        self._selected_tile_key: str = str(self.state.get("selected_tile_key", "") or "")

        self._ui_job: Optional[str] = None
        self._refresh_job: Optional[str] = None

        self._tile_widgets: Dict[str, Dict[str, Any]] = {}
        self._tile_history: Dict[str, List[float]] = {}
        self._tile_specs_left: List[TileSpec] = []
        self._tile_specs_right: List[TileSpec] = []
        self._tile_specs_bottom: List[TileSpec] = []

        self._db_path: Optional[str] = None
        self._db: Optional[sqlite3.Connection] = None

        # Переменные для автоматического управления
        self._ph_auto_last_ts: float = 0.0
        self._do_auto_last_ts: float = 0.0
        self._glucose_history: List[Tuple[float, float]] = []  # (time, concentration)
        self._biomass_history: List[Tuple[float, float]] = []  # (time, biomass)

        self._ensure_app_vars()
        self._load_db()
        self._build_ui()
        self.reposition()
        self._start_refresh_loop()

    # ---------------------- lifecycle ----------------------

    @property
    def frame(self) -> tk.Frame:
        return self._frame

    def destroy(self):
        try:
            if self._refresh_job is not None:
                self.parent.after_cancel(self._refresh_job)
        except Exception:
            pass
        self._refresh_job = None

        try:
            if self._db is not None:
                self._db.close()
        except Exception:
            pass
        self._db = None

        try:
            if self._frame is not None and self._frame.winfo_exists():
                self._frame.destroy()
        except Exception:
            pass

    def show(self):
        self.reposition()
        try:
            self._frame.place_configure()
        except Exception:
            pass

    def hide(self):
        try:
            self._frame.place_forget()
        except Exception:
            pass

    def reposition(self):
        """Растягивает панель на всю рабочую область, исключая нижний лог."""
        try:
            self.parent.update_idletasks()
        except Exception:
            pass

        w = max(200, int(getattr(self.parent, "winfo_width")()))
        h = max(200, int(getattr(self.parent, "winfo_height")()))

        log_h = int(getattr(self.app, "LOG_PANEL_HEIGHT", 100) or 100)
        status_h = 0
        try:
            if bool(getattr(self.app, "window_visibility", {}).get("statusbar", True)):
                status_h = 24
        except Exception:
            status_h = 0

        # Если лог-панели нет/скрыта — не вычитаем
        try:
            lf = getattr(self.app, "log_frame", None)
            if lf is None or (hasattr(lf, "winfo_exists") and not lf.winfo_exists()):
                log_h = 0
        except Exception:
            pass

        avail_h = max(200, h - log_h - status_h)
        self._frame.place(x=0, y=0, width=w, height=avail_h)

        try:
            self._layout_root_grid()
        except Exception:
            pass

    def update_background_snapshot(self, pil_img: Any):
        """Заглушка под единый механизм 'стекла' (как у панели инструментов)."""
        self._bg_snapshot = pil_img

    # ---------------------- app vars ----------------------

    def _ensure_app_vars(self):
        """Гарантирует наличие переменных, на которые опирается WorkspaceApp."""
        def ensure(name: str, var: tk.Variable):
            if not hasattr(self.app, name) or getattr(self.app, name) is None:
                setattr(self.app, name, var)

        # Базовые (обязательные для валидации)
        ensure("vessel_id_var", tk.StringVar(value=""))
        ensure("vessel_type_var", tk.StringVar(value=""))
        ensure("vessel_name_var", tk.StringVar(value="Не выбрано"))
        ensure("vessel_volume_var", tk.DoubleVar(value=0.0))

        ensure("medium_id_var", tk.StringVar(value=""))
        ensure("medium_name_var", tk.StringVar(value="Не выбрано"))

        ensure("culture_id_var", tk.StringVar(value=""))
        ensure("culture_name_var", tk.StringVar(value="Не выбрано"))

        # Заселение культуры (множитель x10^6)
        ensure("culture_inoculation_mln_var", tk.DoubleVar(value=1.0))

        # Внесение глюкозы (мг): ввод и накопление
        ensure("glucose_add_mg_var", tk.DoubleVar(value=0.0))
        ensure("glucose_added_total_mg_var", tk.DoubleVar(value=0.0))

        # Добавление биомассы (×10^6): ввод и накопление
        ensure("biomass_add_mln_var", tk.DoubleVar(value=0.0))
        ensure("biomass_added_total_mln_var", tk.DoubleVar(value=0.0))

        # Условия (нужны для apply_settings/валидации)
        ensure("temperature_c_var", tk.DoubleVar(value=37.0))
        ensure("humidity_var", tk.IntVar(value=60))
        ensure("humidity_enabled_var", tk.BooleanVar(value=True))
        ensure("ph_var", tk.DoubleVar(value=7.4))
        ensure("do_var", tk.DoubleVar(value=100.0))
        ensure("osmolality_var", tk.DoubleVar(value=300.0))
        ensure("glucose_var", tk.DoubleVar(value=0.0))
        ensure("stirring_rpm_var", tk.IntVar(value=0))
        ensure("aeration_lpm_var", tk.DoubleVar(value=0.0))
        ensure("feed_rate_var", tk.DoubleVar(value=0.0))
        ensure("harvest_rate_var", tk.DoubleVar(value=0.0))
        ensure("light_lux_var", tk.DoubleVar(value=0.0))
        ensure("light_cycle_var", tk.StringVar(value=""))

        # Имя и длительность, если вдруг отсутствуют
        ensure("exp_name_var", tk.StringVar(value=""))
        ensure("duration_var", tk.IntVar(value=24))

        # Газовая смесь (дикт на app)
        if not hasattr(self.app, "gases_config") or not isinstance(getattr(self.app, "gases_config", None), dict):
            self.app.gases_config = {"O2": 21.0, "CO2": 0.04, "N2": 78.96}

        # Доп. свойства (не участвуют в валидации, но полезны)
        if not hasattr(self.app, "operator_var") or getattr(self.app, "operator_var", None) is None:
            self.app.operator_var = tk.StringVar(value="")

        # Автоуправление pH по CO2
        if not hasattr(self.app, 'ph_auto_co2_var') or getattr(self.app, 'ph_auto_co2_var', None) is None:
            self.app.ph_auto_co2_var = tk.BooleanVar(value=False)
        
        # Автоуправление DO по аэрации
        if not hasattr(self.app, 'do_auto_aeration_var') or getattr(self.app, 'do_auto_aeration_var', None) is None:
            self.app.do_auto_aeration_var = tk.BooleanVar(value=False)

    # ---------------------- DB ----------------------

    def _load_db(self):
        db_path = _get_microbiology_db_path("microorganisms") or _get_microbiology_db_path("culture_media") or _get_microbiology_db_path("bioreactor_params")
        if not db_path:
            self._db_path = None
            self._db = None
            return
        self._db_path = db_path
        self._db = _connect_ro(db_path)

    def _db_query(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
        if self._db is None:
            return []
        try:
            cur = self._db.cursor()
            cur.execute(sql, params)
            return cur.fetchall() or []
        except Exception:
            return []

    # ---------------------- UI build ----------------------

    def _build_ui(self):
        self._frame = tk.Frame(self.parent, bg="#f7f7f7", highlightthickness=0)

        # корневая сетка: слева свойства, справа дашборд
        self._frame.grid_columnconfigure(0, weight=0, minsize=self.LEFT_W)
        self._frame.grid_columnconfigure(1, weight=1)
        self._frame.grid_rowconfigure(0, weight=1)

        self._left = tk.Frame(self._frame, bg="#f7f7f7")
        self._right = tk.Frame(self._frame, bg="#f7f7f7")
        self._left.grid(row=0, column=0, sticky="nsew", padx=(self.PADDING, self.PADDING//2), pady=self.PADDING)
        self._right.grid(row=0, column=1, sticky="nsew", padx=(self.PADDING//2, self.PADDING), pady=self.PADDING)

        self._build_left_properties()
        self._build_right_dashboard()

    def _layout_root_grid(self):
        # адаптация ширины левой панели под окно
        try:
            w = int(self._frame.winfo_width())
            if w < 950:
                # компактнее
                self._frame.grid_columnconfigure(0, minsize=320)
            else:
                self._frame.grid_columnconfigure(0, minsize=self.LEFT_W)
        except Exception:
            pass

    # ---------------------- Left: properties ----------------------

    def _build_left_properties(self):
        # заголовок
        hdr = tk.Frame(self._left, bg="#f7f7f7")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Свойства эксперимента", bg="#f7f7f7", fg="#222", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(hdr, text="Справочники + базовые уставки (applied)", bg="#f7f7f7", fg="#555", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        card = tk.Frame(self._left, bg="#ffffff", highlightthickness=1, highlightbackground="#e3e3e3")
        card.pack(fill="both", expand=True)
        card.grid_columnconfigure(0, weight=1)

        # поля: название/длительность/оператор
        self._field_entry(card, 0, "Название эксперимента", getattr(self.app, "exp_name_var"), width=30)
        self._field_entry(card, 1, "Длительность (ч)", getattr(self.app, "duration_var"), width=10, is_int=True)
        self._field_entry(card, 2, "Оператор", getattr(self.app, "operator_var"), width=30)

        sep = ttk.Separator(card, orient="horizontal")
        sep.grid(row=3, column=0, sticky="ew", padx=12, pady=10)

        # справочник: биореактор
        self._build_bioreactor_select(card, row_start=4)

        # справочник: питательная среда
        self._build_media_select(card, row_start=8)

        # справочник: микроорганизм/культура
        self._build_culture_select(card, row_start=12)

        # базовые уставки (до старта)
        sep2 = ttk.Separator(card, orient="horizontal")
        sep2.grid(row=16, column=0, sticky="ew", padx=12, pady=10)

        tk.Label(card, text="Базовые уставки", bg="#ffffff", fg="#222", font=("Segoe UI", 10, "bold")).grid(row=17, column=0, sticky="w", padx=12, pady=(0, 6))

        grid = tk.Frame(card, bg="#ffffff")
        grid.grid(row=18, column=0, sticky="ew", padx=12)
        for c in range(2):
            grid.grid_columnconfigure(c, weight=1)

        self._mini_setpoint(grid, 0, 0, "T, °C", getattr(self.app, "temperature_c_var"), width=8, is_float=True)
        self._mini_setpoint(grid, 0, 1, "pH", getattr(self.app, "ph_var"), width=8, is_float=True)
        self._mini_setpoint(grid, 1, 0, "DO, %", getattr(self.app, "do_var"), width=8, is_float=True)
        self._mini_setpoint(grid, 1, 1, "RPM", getattr(self.app, "stirring_rpm_var"), width=8, is_int=True)
        self._mini_setpoint(grid, 2, 0, "Аэрация, L/min", getattr(self.app, "aeration_lpm_var"), width=8, is_float=True)
        self._mini_setpoint(grid, 2, 1, "Подача, mL/h", getattr(self.app, "feed_rate_var"), width=8, is_float=True)

        # газовая смесь (applied)
        tk.Label(card, text="Газовая смесь (applied)", bg="#ffffff", fg="#222", font=("Segoe UI", 10, "bold")).grid(row=19, column=0, sticky="w", padx=12, pady=(10, 6))
        gas = tk.Frame(card, bg="#ffffff")
        gas.grid(row=20, column=0, sticky="ew", padx=12)
        for c in range(3):
            gas.grid_columnconfigure(c, weight=1)

        self._gas_o2 = tk.DoubleVar(value=_safe_float(self.app.gases_config.get("O2", 21.0), 21.0))
        self._gas_co2 = tk.DoubleVar(value=_safe_float(self.app.gases_config.get("CO2", 0.04), 0.04))
        self._gas_n2 = tk.DoubleVar(value=_safe_float(self.app.gases_config.get("N2", 78.96), 78.96))

        self._mini_setpoint(gas, 0, 0, "O₂, %", self._gas_o2, width=6, is_float=True)
        self._mini_setpoint(gas, 0, 1, "CO₂, %", self._gas_co2, width=6, is_float=True)
        self._mini_setpoint(gas, 0, 2, "N₂, %", self._gas_n2, width=6, is_float=True)

        btns = tk.Frame(card, bg="#ffffff")
        btns.grid(row=21, column=0, sticky="ew", padx=12, pady=12)
        btns.grid_columnconfigure(0, weight=1)
        btns.grid_columnconfigure(1, weight=1)

        ttk.Button(btns, text="Применить настройки", command=self._apply_settings).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Сбросить runtime к applied", command=self._reset_runtime_to_applied).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Рендер курсора/фокус
        card.grid_rowconfigure(15, weight=1)

    def _field_entry(self, parent: tk.Frame, row: int, label: str, var: tk.Variable, width: int = 24, is_int: bool = False):
        f = tk.Frame(parent, bg="#ffffff")
        f.grid(row=row, column=0, sticky="ew", padx=12, pady=6)
        f.grid_columnconfigure(1, weight=1)
        tk.Label(f, text=label, bg="#ffffff", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        e = ttk.Entry(f, textvariable=var, width=width)
        e.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        if is_int:
            e.configure(validate="key", validatecommand=(parent.register(lambda s: s == "" or s.isdigit()), "%P"))

    def _mini_setpoint(self, parent: tk.Frame, r: int, c: int, label: str, var: tk.Variable, width: int = 7, is_float: bool = False, is_int: bool = False):
        wrap = tk.Frame(parent, bg="#ffffff")
        wrap.grid(row=r, column=c, sticky="ew", padx=4, pady=4)
        tk.Label(wrap, text=label, bg="#ffffff", fg="#444", font=("Segoe UI", 8)).pack(anchor="w")
        e = ttk.Entry(wrap, textvariable=var, width=width)
        e.pack(anchor="w")
        if is_int:
            e.configure(validate="key", validatecommand=(parent.register(lambda s: s == "" or s.isdigit()), "%P"))
        if is_float:
            e.configure(validate="key", validatecommand=(parent.register(lambda s: s == "" or self._is_float(s)), "%P"))

    @staticmethod
    def _is_float(s: str) -> bool:
        try:
            float(s.replace(",", "."))
            return True
        except Exception:
            return False

    # ---- select bioreactor
    def _build_bioreactor_select(self, parent: tk.Frame, row_start: int):
        tk.Label(parent, text="Биореактор / система", bg="#ffffff", fg="#222", font=("Segoe UI", 10, "bold")).grid(row=row_start, column=0, sticky="w", padx=12, pady=(0, 6))

        container = tk.Frame(parent, bg="#ffffff")
        container.grid(row=row_start + 1, column=0, sticky="ew", padx=12)
        container.grid_columnconfigure(1, weight=1)

        tk.Label(container, text="Тип системы", bg="#ffffff", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self._bio_type_var = tk.StringVar(value="")
        self._bio_type_cb = ttk.Combobox(container, textvariable=self._bio_type_var, state="readonly", values=[])
        self._bio_type_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self._bio_type_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_bio_type_changed())

        tk.Label(container, text="Конфигурация", bg="#ffffff", fg="#333", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._bio_cfg_var = tk.StringVar(value="")
        self._bio_cfg_cb = ttk.Combobox(container, textvariable=self._bio_cfg_var, state="readonly", values=[])
        self._bio_cfg_cb.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(6, 0))
        self._bio_cfg_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_bio_cfg_changed())

        # объем
        vol_wrap = tk.Frame(parent, bg="#ffffff")
        vol_wrap.grid(row=row_start + 2, column=0, sticky="ew", padx=12, pady=(6, 0))
        vol_wrap.grid_columnconfigure(1, weight=1)
        tk.Label(vol_wrap, text="Объём (мл/л)", bg="#ffffff", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self._vessel_volume_entry = ttk.Entry(vol_wrap, textvariable=getattr(self.app, "vessel_volume_var"), width=10)
        self._vessel_volume_entry.grid(row=0, column=1, sticky="w", padx=(10, 0))

        # заполнение из БД
        self._bio_records: List[Tuple[Any, Any, Any, Any, Any]] = []
        self._bio_by_type: Dict[str, List[Tuple[Any, Any, Any, Any, Any]]] = {}
        self._reload_bioreactor_lists()

    def _reload_bioreactor_lists(self):
        rows = self._db_query(
            "SELECT id, system_type, configuration, volume, stirring_speed FROM bioreactor_params ORDER BY system_type, configuration"
        )
        self._bio_records = rows
        by_type: Dict[str, List[Tuple[Any, Any, Any, Any, Any]]] = {}
        for rid, st, cfg, vol, rpm in rows:
            st_s = str(st or "").strip()
            cfg_s = str(cfg or "").strip()
            by_type.setdefault(st_s, []).append((rid, st_s, cfg_s, vol, rpm))
        self._bio_by_type = by_type
        types = [t for t in by_type.keys() if t]
        self._bio_type_cb.configure(values=types)

        # восстановление из app vars (если были)
        try:
            cur_type = str(getattr(self.app, "vessel_type_var").get() or "")
        except Exception:
            cur_type = ""
        if cur_type and cur_type in types:
            self._bio_type_var.set(cur_type)
            self._on_bio_type_changed(set_from_app=True)
        elif types:
            self._bio_type_var.set(types[0])
            self._on_bio_type_changed(set_from_app=False)

    def _on_bio_type_changed(self, set_from_app: bool = False):
        st = str(self._bio_type_var.get() or "")
        items = self._bio_by_type.get(st, [])
        cfgs = [x[2] for x in items if x[2]]
        self._bio_cfg_cb.configure(values=cfgs)
        if not cfgs:
            self._bio_cfg_var.set("")
            return
        # попытка восстановить из app
        try:
            app_name = str(getattr(self.app, "vessel_name_var").get() or "")
        except Exception:
            app_name = ""
        if set_from_app and app_name in cfgs:
            self._bio_cfg_var.set(app_name)
        else:
            self._bio_cfg_var.set(cfgs[0])
        self._on_bio_cfg_changed()

    def _on_bio_cfg_changed(self):
        st = str(self._bio_type_var.get() or "")
        cfg = str(self._bio_cfg_var.get() or "")
        items = self._bio_by_type.get(st, [])
        rec = None
        for it in items:
            if str(it[2]) == cfg:
                rec = it
                break
        if rec is None:
            return
        rid, st, cfg, vol, rpm = rec

        # app vars
        try:
            getattr(self.app, "vessel_id_var").set(str(rid))
            getattr(self.app, "vessel_type_var").set(str(st))
            getattr(self.app, "vessel_name_var").set(str(cfg))
        except Exception:
            pass

        # объем из БД (если есть)
        try:
            if vol is not None and str(vol) != "":
                getattr(self.app, "vessel_volume_var").set(_safe_float(vol, 0.0))
        except Exception:
            pass

        # RPM по умолчанию (если пользователь не выставлял)
        try:
            cur_rpm = _safe_int(getattr(self.app, "stirring_rpm_var").get(), 0)
            if cur_rpm <= 0 and rpm is not None:
                getattr(self.app, "stirring_rpm_var").set(_safe_int(rpm, 0))
        except Exception:
            pass

        self._emit_state()

    # ---- select media
    def _build_media_select(self, parent: tk.Frame, row_start: int):
        tk.Label(parent, text="Питательная среда", bg="#ffffff", fg="#222", font=("Segoe UI", 10, "bold")).grid(row=row_start, column=0, sticky="w", padx=12, pady=(12, 6))

        container = tk.Frame(parent, bg="#ffffff")
        container.grid(row=row_start + 1, column=0, sticky="ew", padx=12)
        container.grid_columnconfigure(1, weight=1)

        tk.Label(container, text="Тип", bg="#ffffff", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self._media_type_var = tk.StringVar(value="")
        self._media_type_cb = ttk.Combobox(container, textvariable=self._media_type_var, state="readonly", values=[])
        self._media_type_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self._media_type_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_media_type_changed())

        tk.Label(container, text="Наименование", bg="#ffffff", fg="#333", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self._media_name_var = tk.StringVar(value="")
        self._media_name_cb = ttk.Combobox(container, textvariable=self._media_name_var, state="readonly", values=[])
        self._media_name_cb.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(6, 0))
        self._media_name_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_media_name_changed())

        self._media_records: List[Tuple[Any, str, str]] = []
        self._media_by_type: Dict[str, List[Tuple[Any, str, str]]] = {}
        self._reload_media_lists()

    def _reload_media_lists(self):
        rows = self._db_query("SELECT id, media_type, name FROM culture_media ORDER BY media_type, name")
        self._media_records = [(rid, str(mt or "").strip(), str(nm or "").strip()) for rid, mt, nm in rows]
        by_type: Dict[str, List[Tuple[Any, str, str]]] = {}
        for rid, mt, nm in self._media_records:
            by_type.setdefault(mt, []).append((rid, mt, nm))
        self._media_by_type = by_type
        types = [t for t in by_type.keys() if t]
        self._media_type_cb.configure(values=types)

        # восстановление
        try:
            cur_name = str(getattr(self.app, "medium_name_var").get() or "")
        except Exception:
            cur_name = ""

        if types:
            # найти тип по имени
            found_type = ""
            for mt, items in by_type.items():
                for _, _, nm in items:
                    if nm == cur_name:
                        found_type = mt
                        break
                if found_type:
                    break
            self._media_type_var.set(found_type or types[0])
            self._on_media_type_changed(set_from_app=True)

    def _on_media_type_changed(self, set_from_app: bool = False):
        mt = str(self._media_type_var.get() or "")
        items = self._media_by_type.get(mt, [])
        names = [x[2] for x in items if x[2]]
        self._media_name_cb.configure(values=names)
        if not names:
            self._media_name_var.set("")
            return
        try:
            cur_name = str(getattr(self.app, "medium_name_var").get() or "")
        except Exception:
            cur_name = ""
        if set_from_app and cur_name in names:
            self._media_name_var.set(cur_name)
        else:
            self._media_name_var.set(names[0])
        self._on_media_name_changed()

    def _on_media_name_changed(self):
        mt = str(self._media_type_var.get() or "")
        nm = str(self._media_name_var.get() or "")
        items = self._media_by_type.get(mt, [])
        rid = ""
        for it in items:
            if it[2] == nm:
                rid = str(it[0])
                break
        try:
            getattr(self.app, "medium_id_var").set(rid)
            getattr(self.app, "medium_name_var").set(nm or "Не выбрано")
        except Exception:
            pass
        self._emit_state()

    # ---- select culture / microorganism
    def _build_culture_select(self, parent: tk.Frame, row_start: int):
        tk.Label(parent, text="Изначальная культура", bg="#ffffff", fg="#222", font=("Segoe UI", 10, "bold")).grid(row=row_start, column=0, sticky="w", padx=12, pady=(12, 6))

        container = tk.Frame(parent, bg="#ffffff")
        container.grid(row=row_start + 1, column=0, sticky="ew", padx=12)
        container.grid_columnconfigure(0, weight=1)

        self._culture_pick_var = tk.StringVar(value="")
        self._culture_cb = ttk.Combobox(container, textvariable=self._culture_pick_var, state="readonly", values=[])
        self._culture_cb.grid(row=0, column=0, sticky="ew")
        self._culture_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_culture_changed())

        # Заселение культуры (Численность [x] × 10^6)
        inoc = tk.Frame(container, bg="#ffffff")
        inoc.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        inoc.grid_columnconfigure(1, weight=1)
        tk.Label(inoc, text="Заселение культуры", bg="#ffffff", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        mult = tk.Frame(inoc, bg="#ffffff")
        mult.grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Entry(mult, textvariable=getattr(self.app, "culture_inoculation_mln_var"), width=10).grid(row=0, column=0, sticky="w")
        tk.Label(mult, text="×10⁶", bg="#ffffff", fg="#555", font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w", padx=(6, 0))

        self._culture_records: List[Tuple[str, str, str, str, Optional[float], Optional[float]]] = []
        self._culture_display_to_id: Dict[str, str] = {}
        self._culture_defaults: Dict[str, Dict[str, float]] = {}
        self._reload_culture_list()

    def _reload_culture_list(self):
        rows = self._db_query(
            "SELECT id, genus, species, strain, ph_optimum, temperature_optimum FROM microorganisms ORDER BY genus, species, strain"
        )
        recs = []
        for rid, g, s, st, ph, t in rows:
            rid_s = str(rid)
            g_s = str(g or "").strip()
            s_s = str(s or "").strip()
            st_s = str(st or "").strip()
            disp = f"{g_s} {s_s}".strip()
            if st_s and st_s.lower() not in ("none", "null"):
                disp = f"{disp} ({st_s})"
            disp = disp.strip() if disp else rid_s
            recs.append((rid_s, g_s, s_s, st_s, ph, t))
            self._culture_display_to_id[disp] = rid_s
            self._culture_defaults[rid_s] = {
                "ph": _safe_float(ph, 0.0),
                "t": _safe_float(t, 0.0),
            }
        self._culture_records = recs

        displays = list(self._culture_display_to_id.keys())
        self._culture_cb.configure(values=displays)

        # восстановление
        try:
            cur_name = str(getattr(self.app, "culture_name_var").get() or "")
        except Exception:
            cur_name = ""
        if cur_name in displays:
            self._culture_pick_var.set(cur_name)
            self._on_culture_changed(set_from_app=True)
        elif displays:
            self._culture_pick_var.set(displays[0])
            self._on_culture_changed(set_from_app=False)

    def _on_culture_changed(self, set_from_app: bool = False):
        disp = str(self._culture_pick_var.get() or "")
        rid = self._culture_display_to_id.get(disp, "")
        try:
            getattr(self.app, "culture_id_var").set(rid)
            getattr(self.app, "culture_name_var").set(disp or "Не выбрано")
        except Exception:
            pass

        # автоподстановка T/pH, если заполнено в справочнике и пользователь не менял явно
        if rid:
            d = self._culture_defaults.get(rid, {})
            ph = _safe_float(d.get("ph", 0.0), 0.0)
            tc = _safe_float(d.get("t", 0.0), 0.0)
            try:
                if ph > 0:
                    getattr(self.app, "ph_var").set(ph)
                if tc > -50:
                    getattr(self.app, "temperature_c_var").set(tc)
            except Exception:
                pass

        self._emit_state()

    # ---------------------- right: dashboard ----------------------


    def _build_right_dashboard(self):
        self._right.grid_rowconfigure(0, weight=1)
        self._right.grid_columnconfigure(0, weight=1)

        card = tk.Frame(self._right, bg="#ffffff", highlightthickness=1, highlightbackground="#e3e3e3")
        card.grid(row=0, column=0, sticky="nsew")

        # сетка: header + dashboard + details
        card.grid_rowconfigure(0, weight=0, minsize=self.HEADER_H)
        card.grid_rowconfigure(1, weight=1)
        card.grid_rowconfigure(2, weight=0, minsize=150)
        card.grid_columnconfigure(0, weight=1)

        # ---------------- header ----------------
        self._hdr = tk.Frame(card, bg="#ffffff")
        self._hdr.grid(row=0, column=0, sticky="ew")
        self._hdr.grid_columnconfigure(0, weight=1)
        self._hdr.grid_columnconfigure(1, weight=0)

        tk.Label(self._hdr, text="Мониторинг и управление", bg="#ffffff", fg="#222",
                 font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))
        self._hdr_status = tk.Label(self._hdr, text="—", bg="#ffffff", fg="#666", font=("Segoe UI", 9))
        self._hdr_status.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        btnbar = tk.Frame(self._hdr, bg="#ffffff")
        btnbar.grid(row=0, column=1, rowspan=2, sticky="e", padx=12, pady=8)

        self._btn_start = ttk.Button(btnbar, text="Пуск", command=self._start)
        self._btn_pause = ttk.Button(btnbar, text="Пауза", command=self._pause)
        self._btn_stop = ttk.Button(btnbar, text="Стоп", command=self._stop)

        self._btn_start.grid(row=0, column=0, padx=(0, 6))
        self._btn_pause.grid(row=0, column=1, padx=6)
        self._btn_stop.grid(row=0, column=2, padx=(6, 0))

        # ---------------- dashboard grid ----------------
        self._mid = tk.Frame(card, bg="#ffffff")
        self._mid.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)
        self._mid.grid_columnconfigure(0, weight=1, uniform="dashcol")
        self._mid.grid_columnconfigure(1, weight=2, uniform="dashcol")
        self._mid.grid_columnconfigure(2, weight=1, uniform="dashcol")

        # строки: 3 строки плиток + емкость + нижняя панель
        self._mid.grid_rowconfigure(0, weight=0)
        self._mid.grid_rowconfigure(1, weight=0)
        self._mid.grid_rowconfigure(2, weight=0)
        self._mid.grid_rowconfigure(3, weight=1)
        self._mid.grid_rowconfigure(4, weight=0)

        self._build_tiles_specs()

        # ---- row 0: [Температура] | [O2][CO2][N2] | [Биомасса][Добавить]...[заглушки]
        r0_l = tk.Frame(self._mid, bg="#ffffff")
        r0_c = tk.Frame(self._mid, bg="#ffffff")
        r0_r = tk.Frame(self._mid, bg="#ffffff")
        r0_l.grid(row=0, column=0, sticky="nw", padx=(0, 8), pady=(0, 8))
        r0_c.grid(row=0, column=1, sticky="n", pady=(0, 8))
        r0_r.grid(row=0, column=2, sticky="ne", padx=(8, 0), pady=(0, 8))

        self._create_tile(r0_l, self._tile_specs["temperature"], width=200, height=180).grid(row=0, column=0, sticky="n")

        self._build_gas_tiles(r0_c)

        # правая верхняя строка: биомасса + добавить + заглушки
        top_actions = tk.Frame(r0_r, bg=self._tiles_bg)
        top_actions.pack(anchor="ne")

        # Биомасса + добавление биомассы (добавляет к текущей)
        self._create_tile(top_actions, self._tile_specs["biomass"]).grid(row=0, column=0, sticky="n", padx=(0, 10))
        self._create_tile(top_actions, self._tile_specs["biomass_add"]).grid(row=0, column=1, sticky="n")



        # ---- row 1: [DO][Аэрация] | [Перемешивание] | [Жизнеспособность][Удвоение]
        r1_l = tk.Frame(self._mid, bg="#ffffff")
        r1_c = tk.Frame(self._mid, bg="#ffffff")
        r1_r = tk.Frame(self._mid, bg="#ffffff")
        r1_l.grid(row=1, column=0, sticky="nw", padx=(0, 8), pady=(0, 8))
        r1_c.grid(row=1, column=1, sticky="n", pady=(0, 8))
        r1_r.grid(row=1, column=2, sticky="ne", padx=(8, 0), pady=(0, 8))

        # DO + Аэрация рядом
        pair_left = tk.Frame(r1_l, bg="#ffffff")
        pair_left.grid(row=0, column=0, sticky="n")
        pair_left.grid_columnconfigure(0, weight=1)
        pair_left.grid_columnconfigure(1, weight=1)
        self._create_tile(pair_left, self._tile_specs["do"], width=155, height=180).grid(row=0, column=0, padx=(0, 6), sticky="n")
        self._create_tile(pair_left, self._tile_specs["aeration"], width=155, height=180).grid(row=0, column=1, sticky="n")

        self._create_tile(r1_c, self._tile_specs["stirring"], width=360, height=180).grid(row=0, column=0, sticky="n")

        pair_right = tk.Frame(r1_r, bg="#ffffff")
        pair_right.grid(row=0, column=0, sticky="n")
        pair_right.grid_columnconfigure(0, weight=1)
        pair_right.grid_columnconfigure(1, weight=1)
        self._create_tile(pair_right, self._tile_specs["viability"], width=155, height=180).grid(row=0, column=0, padx=(0, 6), sticky="n")
        self._create_tile(pair_right, self._tile_specs["doubling"], width=155, height=180).grid(row=0, column=1, sticky="n")

        # ---- row 2: [pH] | [Подача][Уровень][Отбор] | [Рост][Стресс]
        r2_l = tk.Frame(self._mid, bg="#ffffff")
        r2_c = tk.Frame(self._mid, bg="#ffffff")
        r2_r = tk.Frame(self._mid, bg="#ffffff")
        r2_l.grid(row=2, column=0, sticky="nw", padx=(0, 8), pady=(0, 8))
        r2_c.grid(row=2, column=1, sticky="n", pady=(0, 8))
        r2_r.grid(row=2, column=2, sticky="ne", padx=(8, 0), pady=(0, 8))

        self._create_tile(r2_l, self._tile_specs["ph"], width=200, height=180).grid(row=0, column=0, sticky="n")

        trio = tk.Frame(r2_c, bg="#ffffff")
        trio.grid(row=0, column=0, sticky="n")
        for c in range(3):
            trio.grid_columnconfigure(c, weight=1)
        self._create_tile(trio, self._tile_specs["media_feed"], width=155, height=180).grid(row=0, column=0, padx=(0, 6), sticky="n")
        self._create_tile(trio, self._tile_specs["media_level"], width=155, height=180).grid(row=0, column=1, padx=(0, 6), sticky="n")
        self._create_tile(trio, self._tile_specs["media_take"], width=155, height=180).grid(row=0, column=2, sticky="n")

        pair2 = tk.Frame(r2_r, bg="#ffffff")
        pair2.grid(row=0, column=0, sticky="n")
        pair2.grid_columnconfigure(0, weight=1)
        pair2.grid_columnconfigure(1, weight=1)
        self._create_tile(pair2, self._tile_specs["growth_rate"], width=155, height=180).grid(row=0, column=0, padx=(0, 6), sticky="n")
        self._create_tile(pair2, self._tile_specs["stress"], width=155, height=180).grid(row=0, column=1, sticky="n")

        # ---- row 3: визуализация емкости 300x300 (по центру)
        vis = tk.Frame(self._mid, bg="#ffffff")
        vis.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        self._build_center_visual(vis)

        # ---- row 4: нижняя панель глюкозы
        bottom = tk.Frame(self._mid, bg="#ffffff")
        bottom.grid(row=4, column=0, columnspan=3, sticky="ew")

        sep = ttk.Separator(bottom, orient="horizontal")
        sep.pack(fill="x", pady=(0, 8))

        b_row = tk.Frame(bottom, bg="#ffffff")
        b_row.pack(anchor="w")

        self._create_tile(b_row, self._tile_specs["glucose"], width=200, height=180).grid(row=0, column=0, padx=(0, 8), sticky="w")
        self._create_tile(b_row, self._tile_specs["glucose_add"], width=320, height=180).grid(row=0, column=1, sticky="w")

        # ---------------- details ----------------
        self._details = tk.Frame(card, bg="#f9f9f9", highlightthickness=1, highlightbackground="#e3e3e3")
        self._details.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._details.grid_columnconfigure(0, weight=1)
        self._build_details_panel()

    def _build_tiles_specs(self):
        # Единый набор спецификаций (используется для отрисовки плиток в нужных местах)
        self._tile_specs = {
            # Левая колонка (управление)
            "temperature": TileSpec(
                key="temperature",
                title="Температура",
                unit="°C",
                current_key="temperature_c",
                setpoint_key="temperature_c",
                var_name="temperature_c_var",
                fmt="{:.1f}",
                kind="control",
            ),
            "do": TileSpec(
                key="do",
                title="DO",
                unit="%",
                current_key="do_percent",
                setpoint_key="do_setpoint",
                var_name="do_var",
                fmt="{:.0f}",
                kind="control",
            ),
            "aeration": TileSpec(
                key="aeration",
                title="Аэрация",
                unit="L/min",
                current_key="aeration_lpm",
                setpoint_key="aeration_lpm",
                var_name="aeration_lpm_var",
                fmt="{:.1f}",
                kind="control",
            ),
            "ph": TileSpec(
                key="ph",
                title="pH",
                unit="",
                current_key="ph",
                setpoint_key="ph_setpoint",
                var_name="ph_var",
                fmt="{:.2f}",
                kind="control",
            ),
            # Центр (управление технологией)
            "stirring": TileSpec(
                key="stirring",
                title="Перемешивание",
                unit="rpm",
                current_key="stirring_rpm",
                setpoint_key="stirring_rpm",
                var_name="stirring_rpm_var",
                fmt="{:.0f}",
                kind="control",
            ),
            "media_feed": TileSpec(
                key="media_feed",
                title="Подача среды",
                unit="mL/h",
                current_key="feed_rate",
                setpoint_key="feed_rate",
                var_name="feed_rate_var",
                fmt="{:.1f}",
                kind="control",
            ),
            "media_level": TileSpec(
                key="media_level",
                title="Текущий уровень среды",
                unit="мл",
                current_key="volume_ml",
                setpoint_key=None,
                var_name=None,
                fmt="{:.0f}",
                kind="monitor",
            ),
            "media_take": TileSpec(
                key="media_take",
                title="Отбор среды",
                unit="mL/h",
                current_key="harvest_rate",
                setpoint_key="harvest_rate",
                var_name="harvest_rate_var",
                fmt="{:.1f}",
                kind="control",
            ),
            # Правая колонка (мониторинг)
            "biomass": TileSpec(
                key="biomass",
                title="Биомасса",
                unit="×10⁶",
                current_key="biomass",
                fmt="{:.2f}",
                kind="monitor",
            ),
            "viability": TileSpec(
                key="viability",
                title="Жизнеспособность",
                unit="%",
                current_key="viability_percent",
                fmt="{:.0f}",
                kind="monitor",
            ),
            "doubling": TileSpec(
                key="doubling",
                title="Удвоение",
                unit="ч",
                current_key="doubling_time_h",
                fmt="{:.1f}",
                kind="monitor",
            ),
            "growth_rate": TileSpec(
                key="growth_rate",
                title="Скорость роста",
                unit="/ч",
                current_key="growth_rate",
                fmt="{:.3f}",
                kind="monitor",
            ),
            "stress": TileSpec(
                key="stress",
                title="Стресс",
                unit="",
                current_key="stress",
                fmt="{:.2f}",
                kind="monitor",
            ),
            # Нижняя панель
            "glucose": TileSpec(
                key="glucose",
                title="Глюкоза",
                unit="мг/л",
                current_key="glucose",
                fmt="{:.0f}",
                kind="monitor",
            ),
            "biomass_add": TileSpec(
                key="biomass_add",
                title="Добавить биомассу",
                unit="×10⁶",
                current_key="biomass_added_total_mln",
                fmt="{:.2f}",
                kind="action",
            ),

            "glucose_add": TileSpec(
                key="glucose_add",
                title="Добавить глюкозу",
                unit="мг",
                current_key="glucose_added_mg_total",
                fmt="{:.0f}",
                kind="action",
            ),
        }

    def _build_tiles_column(self, parent: tk.Frame, specs: List[TileSpec]):
        parent.grid_columnconfigure(0, weight=0)
        for i, spec in enumerate(specs):
            w = self._create_tile(parent, spec)
            w.grid(row=i, column=0, sticky='n', pady=6)

    def _rounded_poly_points(self, x0: int, y0: int, x1: int, y1: int, r: int) -> list:
        r = max(0, int(r))
        if r*2 > (x1-x0):
            r = max(0, (x1-x0)//2)
        if r*2 > (y1-y0):
            r = max(0, (y1-y0)//2)
        return [
            x0 + r, y0,
            x1 - r, y0,
            x1, y0,
            x1, y0 + r,
            x1, y1 - r,
            x1, y1,
            x1 - r, y1,
            x0 + r, y1,
            x0, y1,
            x0, y1 - r,
            x0, y0 + r,
            x0, y0,
        ]

    def _make_rounded_card(self, parent: tk.Widget, width: int, height: int, fill: str, outline: str, radius: int = 18):
        bg_parent = '#ffffff'
        try:
            bg_parent = str(parent.cget('bg'))
        except Exception:
            pass
        c = tk.Canvas(parent, width=width, height=height, bg=bg_parent, highlightthickness=0)
        pts = self._rounded_poly_points(1, 1, width - 1, height - 1, radius)
        poly = c.create_polygon(pts, smooth=True, splinesteps=12, fill=fill, outline=outline, width=2)
        inner = tk.Frame(c, bg=fill)
        inner.grid_propagate(False)
        c.create_window(0, 0, anchor='nw', window=inner, width=width, height=height)
        return c, poly, inner



    def _create_placeholder_tile(self, parent: tk.Frame, width: int, height: int) -> tk.Canvas:
        """Пустая плитка-заглушка (для выравнивания компоновки)."""
        fill = '#f7f8ff'
        outline = '#e2e6f5'
        tile, _poly, _inner = self._make_rounded_card(parent, int(width), int(height), fill=fill, outline=outline, radius=14)
        return tile

    def _create_button_tile(
        self,
        parent: tk.Frame,
        title: str,
        button_text: str,
        command: Optional[Callable[[], None]],
        width: int,
        height: int,
    ) -> tk.Canvas:
        """Плитка с одной кнопкой (не участвует в выборе параметров)."""
        fill = '#f5f7ff'
        outline = '#d9def3'
        tile, _poly, inner = self._make_rounded_card(parent, int(width), int(height), fill=fill, outline=outline, radius=14)
        inner.grid_columnconfigure(0, weight=1)

        tk.Label(inner, text=title, bg=fill, fg='#223', font=('Segoe UI', 10, 'bold'),
                 wraplength=int(width) - 22, justify='left').grid(row=0, column=0, sticky='w', padx=10, pady=(10, 8))

        btn = ttk.Button(inner, text=button_text, command=command if callable(command) else None)
        btn.grid(row=1, column=0, sticky='ew', padx=10, pady=(0, 10))
        return tile

    def _create_tile(self, parent: tk.Frame, spec: TileSpec, width: Optional[int] = None, height: Optional[int] = None) -> tk.Canvas:
        # размеры плитки (по умолчанию — базовые прямоугольные)
        tile_w = int(width or self.TILE_WIDTH)
        tile_h = int(height or self.TILE_HEIGHT)

        # стили
        base_bg = '#f5f7ff'
        base_br = '#d9def3'
        sel_bg = '#eaf0ff'
        sel_br = '#5b7cff'

        # Автоматизация - особые цвета
        auto_bg = '#f0f7ff'
        auto_sel_bg = '#d4e5ff'
        auto_br = '#2a7fff'

        selected_now = bool(self._selected_tile_key and self._selected_tile_key == spec.key)

        # Проверяем, включена ли автоматизация для этой плитки
        is_auto = False
        if spec.key == "ph" and getattr(self.app, 'ph_auto_co2_var', tk.BooleanVar(value=False)).get():
            is_auto = True
        elif spec.key == "do" and getattr(self.app, 'do_auto_aeration_var', tk.BooleanVar(value=False)).get():
            is_auto = True

        if is_auto:
            fill = auto_sel_bg if selected_now else auto_bg
            outline = auto_br if selected_now else auto_br
        else:
            fill = sel_bg if selected_now else base_bg
            outline = sel_br if selected_now else base_br

        tile, poly, inner = self._make_rounded_card(parent, tile_w, tile_h, fill=fill, outline=outline, radius=18)

        # Общее: клик/выбор
        def on_click(_e=None):
            self._select_tile(spec.key)

        tile.bind('<Button-1>', on_click)

        # --- ACTION: добавление глюкозы ---
        if spec.kind == 'action' and spec.key == 'glucose_add':
            inner.grid_columnconfigure(0, weight=1)

            title_font = ('Segoe UI', 10, 'bold')
            title = tk.Label(inner, text=spec.title, bg=fill, fg='#223', font=title_font,
                             wraplength=tile_w - 22, justify='left')
            title.grid(row=0, column=0, sticky='w', padx=10, pady=(8, 6))

            # Поле ввода и единицы
            input_frame = tk.Frame(inner, bg=fill)
            input_frame.grid(row=1, column=0, sticky='ew', padx=10)
            input_frame.grid_columnconfigure(0, weight=1)
            input_frame.grid_columnconfigure(1, weight=0)

            entry = ttk.Entry(input_frame, textvariable=getattr(self.app, 'glucose_add_mg_var'), width=12)
            entry.grid(row=0, column=0, sticky='w')
            tk.Label(input_frame, text='мг', bg=fill, fg='#556', font=('Segoe UI', 9)).grid(
                row=0, column=1, sticky='w', padx=(6, 0)
            )

            btn = ttk.Button(inner, text='Внести', command=self._add_glucose_from_tile)
            btn.grid(row=2, column=0, sticky='ew', padx=10, pady=(6, 0))

            # Итого
            total_var = tk.StringVar(value='Итого: 0 мг')
            total = tk.Label(inner, textvariable=total_var, bg=fill, fg='#111', font=('Segoe UI', 10, 'bold'))
            total.grid(row=3, column=0, sticky='w', padx=10, pady=(4, 4))

            # График глюкозы (мини)
            graph_canvas = tk.Canvas(inner, height=40, bg=fill, highlightthickness=0)
            graph_canvas.grid(row=4, column=0, sticky='ew', padx=10, pady=(0, 8))

            # bind clicks
            for w in (inner, title, input_frame, entry, btn, total, graph_canvas):
                try:
                    w.bind('<Button-1>', on_click)
                except Exception:
                    pass

            self._tile_widgets[spec.key] = {
                'spec': spec,
                'frame': tile,
                'poly': poly,
                'inner': inner,
                'title': title,
                'badge': None,
                'value': None,
                'sub': total,
                'sub_var': total_var,
                'graph_canvas': graph_canvas,
                'spark': None,
                'fill_base': base_bg,
                'border_base': base_br,
                'fill_sel': sel_bg,
                'border_sel': sel_br,
                'auto_bg': auto_bg,
                'auto_sel_bg': auto_sel_bg,
                'auto_br': auto_br,
                'child_bgs': [inner, title, input_frame, total, graph_canvas],
            }
            self._tile_history.setdefault(spec.key, [])
            return tile



        # --- ACTION: добавление биомассы ---
        if spec.kind == 'action' and spec.key == 'biomass_add':
            inner.grid_columnconfigure(0, weight=1)

            title_font = ('Segoe UI', 10, 'bold')
            title = tk.Label(inner, text=spec.title, bg=fill, fg='#223', font=title_font,
                             wraplength=tile_w - 22, justify='left')
            title.grid(row=0, column=0, sticky='w', padx=10, pady=(8, 0))

            input_frame = tk.Frame(inner, bg=fill)
            input_frame.grid(row=1, column=0, sticky='w', padx=10, pady=(8, 0))
            input_frame.grid_columnconfigure(0, weight=0)
            input_frame.grid_columnconfigure(1, weight=0)

            entry = ttk.Entry(input_frame, textvariable=getattr(self.app, 'biomass_add_mln_var'), width=12)
            entry.grid(row=0, column=0, sticky='w')
            tk.Label(input_frame, text='×10⁶', bg=fill, fg='#556', font=('Segoe UI', 9)).grid(
                row=0, column=1, sticky='w', padx=(6, 0)
            )

            btn = ttk.Button(inner, text='Внести', command=self._add_biomass_from_tile)
            btn.grid(row=2, column=0, sticky='ew', padx=10, pady=(6, 0))

            # Итого
            total_var = tk.StringVar(value='Итого: 0 ×10⁶')
            total = tk.Label(inner, textvariable=total_var, bg=fill, fg='#111', font=('Segoe UI', 10, 'bold'))
            total.grid(row=3, column=0, sticky='w', padx=10, pady=(4, 8))

            # мета для обновления
            self._tile_action_meta[spec.key] = {
                'total_var': total_var,
                'child_bgs': [inner, title, input_frame, total],
            }
            self._tile_history.setdefault(spec.key, [])
            return tile

        # --- CONTROL/MONITOR tiles ---
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=0)

        t_font_size = 11
        if len(spec.title) >= 14:
            t_font_size = 10

        title = tk.Label(
            inner, text=spec.title, bg=fill, fg='#223',
            font=('Segoe UI', t_font_size, 'bold'),
            wraplength=tile_w - 22, justify='left'
        )
        title.grid(row=0, column=0, sticky='w', padx=10, pady=(8, 0))

        badge = tk.Label(inner, text=spec.unit or '', bg=fill, fg='#556', font=('Segoe UI', 9))
        badge.grid(row=0, column=1, sticky='e', padx=10, pady=(8, 0))

        value = tk.Label(inner, text='—', bg=fill, fg='#111', font=('Segoe UI', 18, 'bold'))
        value.grid(row=1, column=0, sticky='w', padx=10, pady=(2, 0))

        # Чекбокс автоматизации для pH и DO
        if spec.key in ["ph", "do"]:
            auto_frame = tk.Frame(inner, bg=fill)
            auto_frame.grid(row=2, column=0, columnspan=2, sticky='w', padx=10, pady=(4, 0))

            auto_var = getattr(self.app, f"{spec.key}_auto_co2_var" if spec.key == "ph" else f"{spec.key}_auto_aeration_var")
            cb = ttk.Checkbutton(
                auto_frame, text='Авто', variable=auto_var,
                command=lambda k=spec.key: self._update_tile_auto_style(k)
            )
            cb.pack(side='left')

            sub = tk.Label(inner, text='', bg=fill, fg='#556', font=('Segoe UI', 9),
                           wraplength=tile_w - 22, justify='left')
            sub.grid(row=3, column=0, columnspan=2, sticky='w', padx=10, pady=(0, 4))
        else:
            sub = tk.Label(inner, text='', bg=fill, fg='#556', font=('Segoe UI', 9),
                           wraplength=tile_w - 22, justify='left')
            sub.grid(row=2, column=0, columnspan=2, sticky='w', padx=10, pady=(0, 6))

        spark = tk.Canvas(inner, height=30, bg=fill, highlightthickness=0)
        spark.grid(row=4, column=0, columnspan=2, sticky='ew', padx=10, pady=(0, 8))

        for w in (inner, title, badge, value, sub, spark):
            try:
                w.bind('<Button-1>', on_click)
            except Exception:
                pass

        self._tile_widgets[spec.key] = {
            'spec': spec,
            'frame': tile,
            'poly': poly,
            'inner': inner,
            'title': title,
            'badge': badge,
            'value': value,
            'sub': sub,
            'spark': spark,
            'fill_base': base_bg,
            'border_base': base_br,
            'fill_sel': sel_bg,
            'border_sel': sel_br,
            'auto_bg': auto_bg,
            'auto_sel_bg': auto_sel_bg,
            'auto_br': auto_br,
            'child_bgs': [inner, title, badge, value, sub, spark],
        }
        self._tile_history.setdefault(spec.key, [])
        return tile

    def _update_tile_auto_style(self, tile_key: str):
        """Обновление стиля плитки при включении/выключении автоматизации"""
        if tile_key not in self._tile_widgets:
            return
        
        w = self._tile_widgets[tile_key]
        spec = w['spec']
        selected_now = bool(self._selected_tile_key and self._selected_tile_key == tile_key)
        
        # Проверяем, включена ли автоматизация
        is_auto = False
        if tile_key == "ph" and getattr(self.app, 'ph_auto_co2_var', tk.BooleanVar(value=False)).get():
            is_auto = True
        elif tile_key == "do" and getattr(self.app, 'do_auto_aeration_var', tk.BooleanVar(value=False)).get():
            is_auto = True
        
        # Обновляем цвета
        if is_auto:
            fill = w['auto_sel_bg'] if selected_now else w['auto_bg']
            outline = w['auto_br'] if selected_now else w['auto_br']
        else:
            fill = w['fill_sel'] if selected_now else w['fill_base']
            outline = w['border_sel'] if selected_now else w['border_base']
        
        try:
            c = w['frame']
            poly = w['poly']
            if c is not None and poly is not None:
                c.itemconfigure(poly, fill=fill, outline=outline)
        except Exception:
            pass
        
        # Обновление фонов вложенных виджетов
        try:
            for ww in w.get('child_bgs', []) or []:
                try:
                    ww.configure(bg=fill)
                except Exception:
                    pass
        except Exception:
            pass

    def _add_glucose_from_tile(self):
        try:
            mg = float(getattr(self.app, 'glucose_add_mg_var').get())
        except Exception:
            mg = 0.0
        if mg <= 0:
            return
        try:
            fn = getattr(self.app, 'add_glucose_mg', None)
            if callable(fn):
                fn(mg)
        except Exception:
            pass
        try:
            getattr(self.app, 'glucose_add_mg_var').set(0.0)
        except Exception:
            pass


    def _add_biomass_from_tile(self) -> None:
        """Кнопка 'Внести' в плитке 'Добавить биомассу'."""
        if not self.app:
            return
        try:
            mln = float(getattr(self.app, "biomass_add_mln_var").get())
        except Exception:
            mln = 0.0
        if mln <= 0:
            return
        try:
            # В workspace_app реализовано add_biomass_mln (добавление к текущей биомассе)
            if hasattr(self.app, "add_biomass_mln"):
                self.app.add_biomass_mln(mln)
        except Exception:
            pass
        try:
            getattr(self.app, "biomass_add_mln_var").set(0.0)
        except Exception:
            pass

    def _update_biomass_add_tile(self) -> None:
        """Обновление текста 'Итого' в плитке добавления биомассы."""
        meta = self._tile_action_meta.get("biomass_add")
        if not meta:
            return
        try:
            rt = getattr(self.app, "runtime_settings", {}) or {}
        except Exception:
            rt = {}
        # Предпочитаем runtime_settings, но поддерживаем tk.Variable
        total_mln = None
        try:
            total_mln = float(rt.get("biomass_added_total_mln", None))
        except Exception:
            total_mln = None
        if total_mln is None:
            try:
                total_mln = float(getattr(self.app, "biomass_added_total_mln_var").get())
            except Exception:
                total_mln = 0.0
        try:
            meta["total_var"].set(f"Итого: {total_mln:.2f} ×10⁶")
        except Exception:
            pass


    def _update_glucose_tile(self):
        w = self._tile_widgets.get('glucose_add')
        if not w:
            return
        
        # Обновляем итоговую сумму
        try:
            total = float(getattr(self.app, 'glucose_added_total_mg_var').get())
        except Exception:
            try:
                total = float((getattr(self.app, 'runtime_settings', {}) or {}).get('glucose_added_mg_total', 0.0) or 0.0)
            except Exception:
                total = 0.0
        try:
            if 'sub_var' in w and w['sub_var'] is not None:
                w['sub_var'].set(f'Итого: {total:.0f} мг')
        except Exception:
            pass
        
        # Обновляем график глюкозы
        if 'graph_canvas' in w:
            self._draw_glucose_graph(w['graph_canvas'])

    def _draw_glucose_graph(self, canvas: tk.Canvas):
        """Рисует мини-график глюкозы и биомассы"""
        try:
            canvas.delete('all')
            w = int(canvas.winfo_width() or 1)
            h = int(canvas.winfo_height() or 1)
        except Exception:
            return
        
        if len(self._glucose_history) < 2 or len(self._biomass_history) < 2:
            return
        
        # Берем последние 20 точек
        glucose_points = self._glucose_history[-20:]
        biomass_points = self._biomass_history[-20:]
        
        if len(glucose_points) < 2:
            return
        
        # Находим диапазоны
        glucose_vals = [g for _, g in glucose_points]
        biomass_vals = [b for _, b in biomass_points]
        
        g_min, g_max = min(glucose_vals), max(glucose_vals)
        b_min, b_max = min(biomass_vals), max(biomass_vals)
        
        if g_max - g_min < 1e-9:
            g_max = g_min + 1.0
        if b_max - b_min < 1e-9:
            b_max = b_min + 1.0
        
        # Рисуем график глюкозы
        pad = 5
        n = len(glucose_points)
        dx = (w - 2 * pad) / max(1, (n - 1))
        
        pts_glucose = []
        for i, (_, v) in enumerate(glucose_points):
            x = pad + i * dx
            y = h - pad - ((v - g_min) / (g_max - g_min)) * (h - 2 * pad)
            pts_glucose.extend([x, y])
        
        if len(pts_glucose) >= 4:
            canvas.create_line(pts_glucose, width=2, smooth=True, fill='#5b7cff')
        
        # Подписи
        try:
            canvas.create_text(2, 2, text=f"{g_max:.0f}", anchor='nw', fill='#666', font=('Segoe UI', 7))
            canvas.create_text(2, h-2, text=f"{g_min:.0f}", anchor='sw', fill='#666', font=('Segoe UI', 7))
            canvas.create_text(w-2, 2, text=f"глюкоза", anchor='ne', fill='#5b7cff', font=('Segoe UI', 7))
        except Exception:
            pass



    def _build_center_visual(self, parent: tk.Frame):
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        holder = tk.Frame(parent, bg="#ffffff")
        holder.grid(row=0, column=0, sticky="nsew")
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)

        # фиксированный размер визуализации емкости 300x300, по центру
        self._reactor = tk.Canvas(holder, width=300, height=300, bg="#ffffff", highlightthickness=0)
        self._reactor.place(relx=0.5, rely=0.5, anchor="center")

    def _build_gas_tiles(self, parent: tk.Frame):
        """Отдельные плитки O2 / CO2 / N2 в одну линию."""
        parent.grid_columnconfigure(0, weight=1)
        row = tk.Frame(parent, bg="#ffffff")
        row.grid(row=0, column=0, sticky="n", pady=0)
        for c in range(3):
            row.grid_columnconfigure(c, weight=1)

        gases = [
            ("O₂", "o2", "#ff6b6b"),
            ("CO₂", "co2", "#4ecdc4"),
            ("N₂", "n2", "#45b7d1"),
        ]
        for i, (name, key, color) in enumerate(gases):
            self._create_gas_tile(row, name, key, color, col=i, width=112, height=112)


    def _create_gas_tile(self, parent: tk.Frame, name: str, key: str, color: str, col: int, width: int = 112, height: int = 112):
        """Создание плитки для одного газа."""
        base_bg = '#f5f7ff'
        base_br = '#d9def3'

        tile, poly, inner = self._make_rounded_card(parent, int(width), int(height), fill=base_bg, outline=base_br, radius=14)
        tile.grid(row=0, column=col, sticky='n', padx=4)

        inner.grid_columnconfigure(0, weight=1)

        # Название газа
        tk.Label(inner, text=name, bg=base_bg, fg='#223', font=('Segoe UI', 10, 'bold')).grid(
            row=0, column=0, sticky='w', padx=8, pady=(8, 2)
        )

        # Текущее значение
        cur_var = tk.StringVar(value='— %')
        cur_label = tk.Label(inner, textvariable=cur_var, bg=base_bg, fg=color, font=('Segoe UI', 12, 'bold'))
        cur_label.grid(row=1, column=0, sticky='w', padx=8, pady=(0, 2))

        # Поле для уставки
        default_val = 21.0 if key == "o2" else 0.04 if key == "co2" else 78.96
        set_var = tk.DoubleVar(value=default_val)
        entry = ttk.Entry(inner, textvariable=set_var, width=8)
        entry.grid(row=2, column=0, sticky='w', padx=8, pady=(2, 2))

        # Кнопка применения
        btn = ttk.Button(inner, text='OK', command=lambda k=key, v=set_var: self._apply_single_gas(k, v))
        btn.grid(row=3, column=0, sticky='ew', padx=8, pady=(2, 8))

        # Сохраняем ссылки
        setattr(self, f'_gas_{key}_cur', cur_var)
        setattr(self, f'_gas_{key}_set', set_var)

        self._tile_widgets[f'gas_{key}'] = {
            'canvas': tile,
            'poly': poly,
            'inner': inner,
            'cur_var': cur_var,
            'set_var': set_var,
            'color': color,
            'fill': base_bg,
            'outline': base_br
        }

    def _apply_single_gas(self, gas_key: str, set_var: tk.DoubleVar):
        """Применить уставку для одного газа"""
        try:
            value = float(set_var.get())
        except Exception:
            return
        
        # Обновляем общий конфиг
        cfg = getattr(self.app, 'gases_config', {}).copy()
        cfg[gas_key.upper()] = max(0.0, min(100.0, value))
        
        # Нормализуем
        total = sum(cfg.values())
        if total > 100.0:
            for k in cfg:
                cfg[k] = cfg[k] / total * 100.0
        
        self.app.gases_config = cfg
        
        # Если эксперимент идет — применяем runtime
        running = bool(getattr(self.app, '_experiment_running', False))
        if running and hasattr(self.app, 'set_runtime_gases_config_staged'):
            try:
                self.app.set_runtime_gases_config_staged(cfg)
                self.app.apply_runtime_gases()
            except Exception:
                pass
        else:
            self._apply_settings()

    # ---------------------- actions (settings/runtime) ----------------------

    def _apply_settings(self):
        """Применить настройки панели."""
        # Обновляем gases_config из отдельных плиток газа
        cfg = {}
        for key in ['o2', 'co2', 'n2']:
            try:
                var = getattr(self, f'_gas_{key}_set', None)
                if var is not None:
                    cfg[key.upper()] = float(var.get())
            except Exception:
                pass
        
        if cfg:
            # Нормализация
            total = sum(cfg.values())
            if total > 100.0:
                for k in cfg:
                    cfg[k] = cfg[k] / total * 100.0
            self.app.gases_config = cfg
        
        # Применение снимка (applied/runtime) через WorkspaceApp
        try:
            fn = getattr(self.app, 'apply_settings', None)
            if callable(fn):
                fn()
        except Exception:
            pass
        
        try:
            self.app.add_log_entry('Настройки эксперимента применены (дашборд)', 'INFO')
        except Exception:
            pass

    def _reset_runtime_to_applied(self):
        """Сброс runtime к applied (делегируется в WorkspaceApp)."""
        try:
            fn = getattr(self.app, 'reset_runtime_to_applied', None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _start(self):
        try:
            fn = getattr(self.app, 'start_simulation', None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _pause(self):
        try:
            fn = getattr(self.app, 'toggle_pause_simulation', None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _stop(self):
        try:
            fn = getattr(self.app, 'stop_simulation', None)
            if callable(fn):
                fn()
        except Exception:
            pass

    def _update_gas_tiles(self):
        """Обновление плиток газа"""
        running = bool(getattr(self.app, '_experiment_running', False))
        gsrc = getattr(self.app, 'runtime_gases_config', None) if running else getattr(self.app, 'gases_config', None)
        gsrc = gsrc or {}
        
        for key in ['o2', 'co2', 'n2']:
            try:
                cur_var = getattr(self, f'_gas_{key}_cur', None)
                if cur_var is not None:
                    value = gsrc.get(key.upper(), 0.0)
                    cur_var.set(f'{float(value):.1f} %')
            except Exception:
                pass

    def _ph_auto_controller_tick(self):
        if not self.app:
            return
        try:
            rt = getattr(self.app, "runtime_settings", {}) or {}
        except Exception:
            rt = {}

        # Включение автоматизации
        try:
            enabled = bool(getattr(self.app, "ph_auto_var").get())
        except Exception:
            enabled = False
        if not enabled:
            return

        # Текущее и уставка pH
        try:
            ph_cur = float(rt.get("ph", getattr(self.app, "ph_var").get()))
        except Exception:
            ph_cur = 7.0
        try:
            ph_sp = float(rt.get("ph_setpoint", getattr(self.app, "ph_var").get()))
        except Exception:
            ph_sp = ph_cur

        # Текущий состав газа
        try:
            o2 = float(getattr(self.app, "o2_percent_var").get())
        except Exception:
            o2 = float(rt.get("o2_percent", 21.0) or 21.0)
        try:
            co2 = float(getattr(self.app, "co2_percent_var").get())
        except Exception:
            co2 = float(rt.get("co2_percent", 0.04) or 0.04)

        # Ошибка: если pH выше уставки — увеличиваем CO2 (CO2 снижает pH)
        err = ph_cur - ph_sp

        # dt
        now = time.time()
        last = getattr(self, "_ph_last_ts", None)
        dt = 1.0
        if isinstance(last, (int, float)):
            dt = max(0.2, min(5.0, now - last))
        self._ph_last_ts = now

        # PI-регулятор
        Kp = 1.2   # %CO2 на единицу pH
        Ki = 0.25  # %CO2 на единицу pH * сек
        i = float(getattr(self, "_ph_i", 0.0) or 0.0)
        i = i + err * dt
        # анти-виндап: ограничим интегратор
        i = max(-10.0, min(10.0, i))
        self._ph_i = i

        delta = (Kp * err) + (Ki * i)
        # ограничение скорости изменения CO2
        delta = max(-0.3, min(0.3, delta))

        new_co2 = max(0.0, min(15.0, co2 + delta))
        # нормируем N2 так, чтобы сумма была 100
        new_o2 = max(0.0, min(100.0, o2))
        n2 = 100.0 - new_o2 - new_co2
        if n2 < 0.0:
            # если сумма >100 — срежем CO2
            new_co2 = max(0.0, 100.0 - new_o2)
            n2 = 0.0

        try:
            # обновляем UI-переменные
            getattr(self.app, "co2_percent_var").set(float(new_co2))
            getattr(self.app, "n2_percent_var").set(float(n2))
        except Exception:
            pass
        try:
            if hasattr(self.app, "apply_runtime_parameter"):
                self.app.apply_runtime_parameter("co2_percent", float(new_co2))
                self.app.apply_runtime_parameter("n2_percent", float(n2))
        except Exception:
            pass

    def _do_auto_controller_tick(self):
        if not self.app:
            return
        try:
            rt = getattr(self.app, "runtime_settings", {}) or {}
        except Exception:
            rt = {}

        # Включение автоматизации
        try:
            enabled = bool(getattr(self.app, "do_auto_var").get())
        except Exception:
            enabled = False
        if not enabled:
            return

        # Текущее и уставка DO
        try:
            do_cur = float(rt.get("do_percent", 0.0) or 0.0)
        except Exception:
            do_cur = 0.0
        try:
            do_sp = float(rt.get("do_setpoint", getattr(self.app, "do_var").get()))
        except Exception:
            do_sp = float(getattr(self.app, "do_var").get() if hasattr(self.app, "do_var") else 100.0)

        err = do_sp - do_cur

        # dt
        now = time.time()
        last = getattr(self, "_do_last_ts", None)
        dt = 1.0
        if isinstance(last, (int, float)):
            dt = max(0.2, min(5.0, now - last))
        self._do_last_ts = now

        # Текущая аэрация
        try:
            aer = float(getattr(self.app, "aeration_var").get())
        except Exception:
            aer = float(rt.get("aeration_lpm", 0.0) or 0.0)

        # PI-регулятор для аэрации
        Kp = 0.03  # L/min на %DO
        Ki = 0.004 # L/min на %DO*сек
        i = float(getattr(self, "_do_i", 0.0) or 0.0)
        i = i + err * dt
        i = max(-500.0, min(500.0, i))
        self._do_i = i

        delta = (Kp * err) + (Ki * i)
        # ограничение скорости изменения
        delta = max(-0.4, min(0.4, delta))

        new_aer = aer + delta
        new_aer = max(0.0, min(10.0, new_aer))

        try:
            getattr(self.app, "aeration_var").set(float(new_aer))
        except Exception:
            pass
        try:
            if hasattr(self.app, "apply_runtime_parameter"):
                self.app.apply_runtime_parameter("aeration_lpm", float(new_aer))
        except Exception:
            pass

    def _build_details_panel(self):
        self._details.grid_rowconfigure(0, weight=0)
        self._details.grid_rowconfigure(1, weight=1)
        self._details.grid_columnconfigure(0, weight=1)

        hdr = tk.Frame(self._details, bg="#f9f9f9")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        hdr.grid_columnconfigure(0, weight=1)

        self._details_title = tk.Label(hdr, text="Параметр: —", bg="#f9f9f9", fg="#222", font=("Segoe UI", 10, "bold"))
        self._details_title.grid(row=0, column=0, sticky="w")
        self._details_hint = tk.Label(hdr, text="", bg="#f9f9f9", fg="#666", font=("Segoe UI", 9))
        self._details_hint.grid(row=1, column=0, sticky="w")

        body = tk.Frame(self._details, bg="#f9f9f9")
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 10))
        body.grid_columnconfigure(0, weight=1)

        # факт (всегда)
        row0 = tk.Frame(body, bg="#f9f9f9")
        row0.grid(row=0, column=0, sticky="ew")
        tk.Label(row0, text="Факт", bg="#f9f9f9", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self._det_actual = tk.Label(row0, text="—", bg="#f9f9f9", fg="#111", font=("Segoe UI", 11, "bold"))
        self._det_actual.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # режимы: управление / график
        self._det_controls = tk.Frame(body, bg="#f9f9f9")
        self._det_controls.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for c in range(4):
            self._det_controls.grid_columnconfigure(c, weight=1)

        tk.Label(self._det_controls, text="Уставка", bg="#f9f9f9", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self._det_set_var = tk.StringVar(value="")
        self._det_set_entry = ttk.Entry(self._det_controls, textvariable=self._det_set_var, width=10)
        self._det_set_entry.grid(row=1, column=0, sticky="w", pady=(2, 0))

        tk.Label(self._det_controls, text="Нижний предел", bg="#f9f9f9", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w")
        self._det_lo_var = tk.StringVar(value="")
        self._det_lo_entry = ttk.Entry(self._det_controls, textvariable=self._det_lo_var, width=10)
        self._det_lo_entry.grid(row=1, column=1, sticky="w", pady=(2, 0))

        tk.Label(self._det_controls, text="Верхний предел", bg="#f9f9f9", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w")
        self._det_hi_var = tk.StringVar(value="")
        self._det_hi_entry = ttk.Entry(self._det_controls, textvariable=self._det_hi_var, width=10)
        self._det_hi_entry.grid(row=1, column=2, sticky="w", pady=(2, 0))

        self._det_apply_btn = ttk.Button(self._det_controls, text="Применить", command=self._apply_detail)
        self._det_apply_btn.grid(row=1, column=3, sticky="e")

        self._det_graph_frame = tk.Frame(body, bg="#f9f9f9")
        self._det_graph_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self._det_graph_frame.grid_columnconfigure(0, weight=1)
        tk.Label(self._det_graph_frame, text="График", bg="#f9f9f9", fg="#333", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        self._det_graph_canvas = tk.Canvas(self._det_graph_frame, height=110, bg="#ffffff", highlightthickness=1, highlightbackground="#e3e3e3")
        self._det_graph_canvas.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # по умолчанию — режим управления
        self._det_graph_frame.grid_remove()

    # ---------------------- tile selection ----------------------

    def _select_tile(self, key: str):
        key = str(key or "")
        if not key or key not in self._tile_widgets:
            return

        # deselect old
        if self._selected_tile_key and self._selected_tile_key in self._tile_widgets and self._selected_tile_key != key:
            self._apply_tile_selected_style(self._selected_tile_key, selected=False)

        self._selected_tile_key = key
        self._apply_tile_selected_style(key, selected=True)

        spec: TileSpec = self._tile_widgets[key]["spec"]
        self._details_title.configure(text=f"Параметр: {spec.title}")

        if spec.kind == "monitor":
            self._details_hint.configure(text="График строится по истории значений (последние точки).")
        elif spec.kind == "action":
            self._details_hint.configure(text="Действие: ввод и внесение выполняются кнопкой на плитке.")
        else:
            self._details_hint.configure(text="Уставка применяется в runtime во время эксперимента, иначе — в applied.")

        # переключение режимов
        if spec.kind == "monitor":
            try:
                self._det_controls.grid_remove()
            except Exception:
                pass
            try:
                self._det_graph_frame.grid()
            except Exception:
                pass
        elif spec.kind == "control":
            try:
                self._det_graph_frame.grid_remove()
            except Exception:
                pass
            try:
                self._det_controls.grid()
            except Exception:
                pass
        else:
            try:
                self._det_graph_frame.grid_remove()
            except Exception:
                pass
            try:
                self._det_controls.grid_remove()
            except Exception:
                pass

        # заполнение полей (однократно при выборе)
        if spec.kind == "control":
            sp = self._get_setpoint_value(spec)
            self._det_set_var.set("" if sp is None else str(sp))
            lim = self._limits.get(spec.key, {}) or {}
            lo = lim.get("lo", "")
            hi = lim.get("hi", "")
            self._det_lo_var.set("" if lo in (None, "") else str(lo))
            self._det_hi_var.set("" if hi in (None, "") else str(hi))

        # обновить факт и (если нужно) график
        self._refresh_selected_detail(force=True)

        self._emit_state()

    def _refresh_selected_detail(self, force: bool = False):
        if not self._selected_tile_key or self._selected_tile_key not in self._tile_widgets:
            return
        spec: TileSpec = self._tile_widgets[self._selected_tile_key]["spec"]
        actual = self._get_current_value(spec)
        try:
            self._det_actual.configure(text=self._format_value(actual, spec))
        except Exception:
            pass

        if spec.kind == "monitor":
            try:
                hist = list(self._tile_history.get(spec.key, []) or [])
                self._draw_detail_graph(hist)
            except Exception:
                pass

    def _draw_detail_graph(self, values: List[float]):
        c = getattr(self, '_det_graph_canvas', None)
        if c is None:
            return
        try:
            c.delete('all')
        except Exception:
            return
        if not values or len(values) < 2:
            return
        try:
            w = int(c.winfo_width() or 1)
            h = int(c.winfo_height() or 1)
        except Exception:
            w, h = 400, 110
        pad = 10
        xs = values[-60:]
        vmin = min(xs)
        vmax = max(xs)
        if abs(vmax - vmin) < 1e-9:
            vmax = vmin + 1.0
        n = len(xs)
        dx = (w - 2 * pad) / max(1, (n - 1))
        pts = []
        for i, v in enumerate(xs):
            x = pad + i * dx
            y = h - pad - ((v - vmin) / (vmax - vmin)) * (h - 2 * pad)
            pts.extend([x, y])
        try:
            c.create_line(pts, width=2, smooth=True)
        except Exception:
            pass
        try:
            c.create_text(pad, pad, text=f"{vmax:.2f}", anchor='nw', fill='#666', font=('Segoe UI', 8))
            c.create_text(pad, h - pad, text=f"{vmin:.2f}", anchor='sw', fill='#666', font=('Segoe UI', 8))
        except Exception:
            pass

    def _apply_tile_selected_style(self, key: str, selected: bool):
        w = self._tile_widgets.get(key)
        if not w:
            return
        
        # Проверяем, включена ли автоматизация
        is_auto = False
        if key == "ph" and getattr(self.app, 'ph_auto_co2_var', tk.BooleanVar(value=False)).get():
            is_auto = True
        elif key == "do" and getattr(self.app, 'do_auto_aeration_var', tk.BooleanVar(value=False)).get():
            is_auto = True
        
        if is_auto:
            fill = w.get('auto_sel_bg') if selected else w.get('auto_bg')
            outline = w.get('auto_br') if selected else w.get('auto_br')
        else:
            fill = w.get('fill_sel') if selected else w.get('fill_base')
            outline = w.get('border_sel') if selected else w.get('border_base')
        
        try:
            c = w.get('frame')
            poly = w.get('poly')
            if c is not None and poly is not None:
                c.itemconfigure(poly, fill=fill, outline=outline)
        except Exception:
            pass
        
        # обновление фонов вложенных виджетов
        try:
            for ww in w.get('child_bgs', []) or []:
                try:
                    ww.configure(bg=fill)
                except Exception:
                    pass
        except Exception:
            pass

    # ---------------------- details apply ----------------------

    def _apply_detail(self):
        if not self._selected_tile_key or self._selected_tile_key not in self._tile_widgets:
            return
        spec: TileSpec = self._tile_widgets[self._selected_tile_key]['spec']

        # Для мониторинговых и action-плиток уставки/лимиты не применяются
        if spec.kind != 'control':
            return

        # limits
        lo = self._det_lo_var.get().strip()
        hi = self._det_hi_var.get().strip()
        lim: Dict[str, Any] = {}
        if lo != '':
            lim['lo'] = _safe_float(lo, None)
        if hi != '':
            lim['hi'] = _safe_float(hi, None)
        if lim:
            self._limits[spec.key] = lim
        else:
            self._limits.pop(spec.key, None)
        self.state['limits'] = dict(self._limits)

        # setpoint apply
        raw = self._det_set_var.get().strip().replace(',', '.')
        if raw != '':
            v = _safe_float(raw, None)
            if v is not None:
                self._apply_setpoint(spec, v)

        self._emit_state()

    def _reset_limits_for_selected(self):
        if not self._selected_tile_key:
            return
        self._limits.pop(self._selected_tile_key, None)
        self.state['limits'] = dict(self._limits)
        self._det_lo_var.set('')
        self._det_hi_var.set('')
        self._emit_state()

    def _apply_setpoint(self, spec: TileSpec, value: float):
        running = bool(getattr(self.app, "_experiment_running", False))
        # во время эксперимента — runtime
        if running:
            try:
                fn = getattr(self.app, "apply_runtime_parameter", None)
                if callable(fn) and spec.setpoint_key:
                    fn(spec.setpoint_key, value)
                    return
            except Exception:
                pass

        # до старта — обновляем переменную (для apply_settings)
        if spec.var_name:
            try:
                var = getattr(self.app, spec.var_name, None)
                if var is not None and hasattr(var, "set"):
                    if isinstance(var, tk.IntVar):
                        var.set(_safe_int(value))
                    else:
                        var.set(_safe_float(value))
            except Exception:
                pass

        # сразу фиксируем в applied (чтобы валидация и UI синхронизировались)
        try:
            fn2 = getattr(self.app, "apply_settings", None)
            if callable(fn2):
                fn2()
        except Exception:
            pass

    # ---------------------- refresh loop ----------------------

    def _start_refresh_loop(self):
        self._refresh()

    def _refresh(self):
        try:
            self._ph_auto_controller_tick()
            self._do_auto_controller_tick()
            self._update_gas_tiles()
        except Exception:
            pass
        
        self._refresh_header()
        self._refresh_tiles()
        try:
            self._update_glucose_tile()
            self._update_biomass_add_tile()
        except Exception:
            pass
        try:
            self._refresh_selected_detail()
        except Exception:
            pass
        self._draw_reactor()
        self._update_history()
        
        try:
            self._refresh_job = self.parent.after(500, self._refresh)
        except Exception:
            self._refresh_job = None

    def _update_history(self):
        """Обновление истории для графиков"""
        rt = getattr(self.app, 'runtime_settings', {}) or {}
        
        # История глюкозы
        try:
            glucose = float(rt.get('glucose', 0.0))
            now = time.time()
            self._glucose_history.append((now, glucose))
            if len(self._glucose_history) > 100:
                self._glucose_history.pop(0)
        except Exception:
            pass
        
        # История биомассы
        try:
            biomass = float(rt.get('biomass', 0.0))
            now = time.time()
            self._biomass_history.append((now, biomass))
            if len(self._biomass_history) > 100:
                self._biomass_history.pop(0)
        except Exception:
            pass

    def _refresh_header(self):
        running = bool(getattr(self.app, "_experiment_running", False))
        paused = bool(getattr(self.app, "_sim_paused", False))
        if not running:
            txt = "Не запущено"
        else:
            txt = "Пауза" if paused else "Выполняется"
        try:
            exp = str(getattr(self.app, "exp_name_var").get() or "")
        except Exception:
            exp = ""
        if exp:
            txt = f"{txt} • {exp}"
        self._hdr_status.configure(text=txt)

        # состояние кнопок
        try:
            if hasattr(self, "_btn_pause"):
                self._btn_pause.configure(text=("Продолжить" if (running and paused) else "Пауза"))
                self._btn_start.configure(state=("disabled" if running else "normal"))
                self._btn_stop.configure(state=("normal" if running else "disabled"))
                self._btn_pause.configure(state=("normal" if running else "disabled"))
        except Exception:
            pass

    def _refresh_tiles(self):
        for key, w in self._tile_widgets.items():
            if key.startswith('gas_'):
                continue  # Плитки газа обновляются отдельно
            
            spec: TileSpec = w.get("spec")
            if not spec:
                continue

            # action-плитки: обновляем отдельно
            if spec.kind == "action":
                continue

            actual = self._get_current_value(spec)
            sp = self._get_setpoint_value(spec)

            try:
                w["value"].configure(text=self._format_value(actual, spec))
            except Exception:
                pass

            sub = ""
            if spec.kind == "control":
                sub = f"Уставка: {self._format_value(sp, spec)}" if sp is not None else "Уставка: —"
            else:
                sub = "Мониторинг"

            # лимиты/статус (только для управляемых плиток)
            status = ""
            if spec.kind == "control":
                lim = self._limits.get(spec.key, {}) or {}
                lo = lim.get("lo", None)
                hi = lim.get("hi", None)
                if actual is not None and (lo not in (None, "") or hi not in (None, "")):
                    try:
                        a = float(actual)
                        if lo not in (None, "") and a < float(lo):
                            status = " • ниже нижнего предела"
                        if hi not in (None, "") and a > float(hi):
                            status = " • выше верхнего предела"
                    except Exception:
                        pass
            w["sub"].configure(text=sub + status)

            # sparkline
            self._push_history(spec.key, actual)
            self._draw_spark(w["spark"], self._tile_history.get(spec.key, []))

    def _push_history(self, key: str, value: Any):
        if value is None:
            return
        try:
            v = float(value)
        except Exception:
            return
        hist = self._tile_history.setdefault(key, [])
        hist.append(v)
        if len(hist) > 60:
            del hist[: len(hist) - 60]

    def _draw_spark(self, canvas: tk.Canvas, hist: List[float]):
        try:
            canvas.delete("all")
            w = max(1, int(canvas.winfo_width()))
            h = max(1, int(canvas.winfo_height()))
            if len(hist) < 2:
                return
            lo = min(hist)
            hi = max(hist)
            if abs(hi - lo) < 1e-9:
                hi = lo + 1.0
            pts = []
            n = len(hist)
            for i, v in enumerate(hist):
                x = int(i * (w - 2) / max(1, n - 1)) + 1
                y = int((1.0 - (v - lo) / (hi - lo)) * (h - 2)) + 1
                pts.append((x, y))
            for i in range(1, len(pts)):
                canvas.create_line(pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1], fill="#5b7cff", width=2)
        except Exception:
            pass

    def _draw_reactor(self):
        c = self._reactor
        try:
            c.delete("all")
            w = int(c.winfo_width())
            h = int(c.winfo_height())
            if w <= 10 or h <= 10:
                return

            # контур
            margin = 30
            rx0, ry0 = margin, margin
            rx1, ry1 = w - margin, h - margin

            # основной корпус
            c.create_rectangle(rx0, ry0, rx1, ry1, outline="#cfd6e6", width=2, fill="#f7f9ff")

            # уровень жидкости по объёму (условно)
            vol_ml = _safe_float(getattr(self.app, "runtime_settings", {}).get("volume_ml", 0.0), 0.0)
            if vol_ml <= 0:
                # fallback: из applied
                vol_ml = _safe_float(getattr(self.app, "applied_settings", {}).get("volume_ml", 0.0), 0.0)
            vessel_ml = _safe_float(getattr(self.app, "applied_settings", {}).get("vessel_volume", 0.0), 0.0)
            if vessel_ml <= 0:
                try:
                    vessel_ml = _safe_float(getattr(self.app, "vessel_volume_var").get(), 0.0)
                except Exception:
                    vessel_ml = 0.0

            fill_ratio = 0.5
            if vessel_ml > 0 and vol_ml > 0:
                fill_ratio = _clamp(vol_ml / vessel_ml, 0.05, 0.95)

            fill_h = int((ry1 - ry0) * fill_ratio)
            fy0 = ry1 - fill_h
            c.create_rectangle(rx0 + 3, fy0, rx1 - 3, ry1 - 3, outline="", fill="#5b7cff")

            # подписи
            t = self._format_value(self._get_current_value(self._tile_widgets["temperature"]["spec"]), self._tile_widgets["temperature"]["spec"]) if "temperature" in self._tile_widgets else "—"
            ph = self._format_value(self._get_current_value(self._tile_widgets["ph"]["spec"]), self._tile_widgets["ph"]["spec"]) if "ph" in self._tile_widgets else "—"
            do = self._format_value(self._get_current_value(self._tile_widgets["do"]["spec"]), self._tile_widgets["do"]["spec"]) if "do" in self._tile_widgets else "—"

            c.create_text(w // 2, ry0 - 10, text="Биореактор", fill="#223", font=("Segoe UI", 11, "bold"))
            c.create_text(w // 2, ry0 + 12, text=f"T={t} °C   pH={ph}   DO={do} %", fill="#223", font=("Segoe UI", 10))

        except Exception:
            pass

    # ---------------------- value getters ----------------------

    def _get_current_value(self, spec: TileSpec) -> Optional[float]:
        rt = getattr(self.app, "runtime_settings", {}) or {}
        v = rt.get(spec.current_key, None)
        if v is None:
            # иногда до старта/до apply — берем из applied
            ap = getattr(self.app, "applied_settings", {}) or {}
            v = ap.get(spec.current_key, None)
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    def _get_setpoint_value(self, spec: TileSpec) -> Optional[float]:
        if spec.kind != "control":
            return None
        running = bool(getattr(self.app, "_experiment_running", False))
        if running and spec.setpoint_key:
            rt = getattr(self.app, "runtime_settings", {}) or {}
            if spec.setpoint_key in rt:
                return _safe_float(rt.get(spec.setpoint_key), None)

        # до старта: var_name -> app var
        if spec.var_name:
            try:
                var = getattr(self.app, spec.var_name, None)
                if var is not None and hasattr(var, "get"):
                    return _safe_float(var.get(), None)
            except Exception:
                pass

        ap = getattr(self.app, "applied_settings", {}) or {}
        if spec.setpoint_key and spec.setpoint_key in ap:
            return _safe_float(ap.get(spec.setpoint_key), None)
        return None

    def _format_value(self, v: Any, spec: TileSpec) -> str:
        if v is None:
            return "—"
        try:
            return spec.fmt.format(float(v))
        except Exception:
            try:
                return str(v)
            except Exception:
                return "—"

    # ---------------------- state persistence ----------------------

    def _emit_state(self):
        self.state["selected_tile_key"] = self._selected_tile_key
        self.state["limits"] = dict(self._limits)
        self.state["db_path"] = self._db_path or ""
        try:
            if callable(self.on_state_changed):
                self.on_state_changed(dict(self.state))
        except Exception:
            pass