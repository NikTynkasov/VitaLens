# work_space/experiment_settings_panel.py
# Панель настройки эксперимента (полоса справа от кнопок Пуск/Пауза/Стоп)
# Версия: выбор из справочников (SQLite) + корректная группировка + газовые концентрации + кнопки управления
# Правки: +15px высоты, проверка суммы концентраций газов

import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable, Dict, Any, List, Tuple

try:
    from PIL import Image, ImageTk  # type: ignore
    _PIL_OK = True
except Exception:
    Image = None
    ImageTk = None
    _PIL_OK = False


class ExperimentSettingsPanel:
    """Панель настройки эксперимента.

    Реализовано:
    1) Выбор посуды из справочника (таблица bioreactor_params)
    2) Выбор среды (culture_media) и изначальной культуры (microorganisms)
    3) Условия: T°C, влажность (отключается для реакторов), газы (с концентрациями)
    4) Кнопки управления внизу: Сохранить / Загрузить / Применить / Сбросить
    """

    # Было 192. Увеличили на 15px согласно требованию.
    BAR_HEIGHT = 207
    COLLAPSED_HEIGHT = 46  # высота панели в свернутом виде (одна строка)

    # Цвета панели
    CONTENT_BG = "#f3efe6"
    CONTENT_FG = "#111111"
    BORDER = "#b8b3aa"
    FIELD_BG = "#ffffff"

    DEFAULT_GASES = ["Air", "O2", "CO2", "N2", "Ar", "H2", "CH4"]

    # Стандартная смесь (в %), если пользователь не задавал
    DEFAULT_GAS_MIX = {"O2": 21.0, "CO2": 5.0, "N2": 74.0}

    # Допуск на сумму концентраций
    GAS_SUM_TARGET = 100.0
    GAS_SUM_TOL = 0.5  # ±0.5%

    def __init__(self, root: tk.Misc, app, x_offset: int = 60):
        self.root = root
        self.app = app
        self.x_offset = int(x_offset)

        self._bg_imgtk: Optional[tk.PhotoImage] = None
        self._window_bg_pil = None

        # Debounce обновления фонового снимка (иначе при изменении размера/прокрутке может тормозить)
        self._bg_update_job_fast = None
        self._bg_update_job_quality = None
        self._bg_last_bbox = None
        self._bg_last_window_size = None

        # DB helpers (ленивый импорт)
        self._db_ok = False
        self._ensure_db_helpers()

        # Vars создаём в app при отсутствии (не трогаем workspace_app.py)
        self._ensure_vars()

        # Состояние свернутости панели (храним в app)
        try:
            self._collapsed = bool(self.app.settings_panel_collapsed_var.get())
        except Exception:
            self._collapsed = False

        # Табло времени эксперимента (День:Часы:Минуты:Секунды)
        self._elapsed_var = tk.StringVar(value="00:00:00:00")
        self._elapsed_job = None
        self._elapsed_last_sec = None

        # Внешний контейнер панели
        self.frame = tk.Frame(root, bd=0, relief=tk.FLAT, highlightthickness=0)

        self._bg_label = tk.Label(self.frame, bd=0, highlightthickness=0)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg_label.lower()

        # Контент поверх фонового снимка
        self._content = tk.Frame(
            self.frame,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            bg=self.CONTENT_BG
        )
        self._content.place(x=0, y=0, relwidth=1, relheight=1)

        self._build_widgets()
        self.reposition()

    # -------------------------
    # DB helpers import
    # -------------------------

    def _ensure_db_helpers(self):
        """Пытаемся найти database/database.py без жёсткой привязки к способу запуска."""
        self._ensure_database_fn = None
        self._get_connection_fn = None

        candidates = [
            ("database.database", "ensure_database", "get_connection"),
            ("database", "ensure_database", "get_connection"),
        ]

        for mod_name, ens, conn in candidates:
            try:
                import importlib
                mod = importlib.import_module(mod_name)
                self._ensure_database_fn = getattr(mod, ens, None)
                self._get_connection_fn = getattr(mod, conn, None)
                if callable(self._ensure_database_fn) and callable(self._get_connection_fn):
                    self._db_ok = True
                    return
            except Exception:
                continue

        self._db_ok = False

    def _db_ensure(self):
        if callable(self._ensure_database_fn):
            try:
                self._ensure_database_fn()
            except Exception:
                pass

    def _db_conn(self):
        if callable(self._get_connection_fn):
            return self._get_connection_fn()
        return None

    # -------------------------
    # Vars / state
    # -------------------------

    def _ensure_vars(self):
        if getattr(self.app, "exp_name_var", None) is None:
            self.app.exp_name_var = tk.StringVar(value="Эксперимент")
        if getattr(self.app, "duration_var", None) is None:
            self.app.duration_var = tk.IntVar(value=1)


        # Свернутость панели настроек (заголовок-строка)
        if getattr(self.app, "settings_panel_collapsed_var", None) is None:
            self.app.settings_panel_collapsed_var = tk.BooleanVar(value=False)

        # Посуда
        if getattr(self.app, "vessel_id_var", None) is None:
            self.app.vessel_id_var = tk.StringVar(value="")
        if getattr(self.app, "vessel_name_var", None) is None:
            self.app.vessel_name_var = tk.StringVar(value="Не выбрано")
        if getattr(self.app, "vessel_type_var", None) is None:
            self.app.vessel_type_var = tk.StringVar(value="")

        if getattr(self.app, "vessel_volume_var", None) is None:
            self.app.vessel_volume_var = tk.DoubleVar(value=0.0)

        # Среда
        if getattr(self.app, "medium_id_var", None) is None:
            self.app.medium_id_var = tk.StringVar(value="")
        if getattr(self.app, "medium_name_var", None) is None:
            self.app.medium_name_var = tk.StringVar(value="Не выбрано")

        # Изначальная культура
        if getattr(self.app, "culture_id_var", None) is None:
            self.app.culture_id_var = tk.StringVar(value="")
        if getattr(self.app, "culture_name_var", None) is None:
            self.app.culture_name_var = tk.StringVar(value="Не выбрано")

        # Условия
        if getattr(self.app, "temperature_c_var", None) is None:
            self.app.temperature_c_var = tk.DoubleVar(value=37.0)
        if getattr(self.app, "humidity_var", None) is None:
            self.app.humidity_var = tk.IntVar(value=60)

        # Текстовое представление газов для UI
        if getattr(self.app, "gases_var", None) is None:
            self.app.gases_var = tk.StringVar(value="")

        # Конфигурация газов (python dict): {gas: concentration}
        if getattr(self.app, "gases_config", None) is None:
            cfg = self._parse_gases_string_to_config(getattr(self.app, "gases_var", tk.StringVar(value="")).get())
            if not cfg:
                cfg = dict(self.DEFAULT_GAS_MIX)
            self.app.gases_config = cfg


        # Дополнительные условия (используются в панели управления экспериментом и сохраняются в настройках)
        if getattr(self.app, "ph_var", None) is None:
            self.app.ph_var = tk.DoubleVar(value=7.4)
        if getattr(self.app, "do_var", None) is None:
            self.app.do_var = tk.DoubleVar(value=100.0)
        if getattr(self.app, "osmolality_var", None) is None:
            self.app.osmolality_var = tk.DoubleVar(value=300.0)
        if getattr(self.app, "glucose_var", None) is None:
            self.app.glucose_var = tk.DoubleVar(value=0.0)

        # Механика / реактор
        if getattr(self.app, "stirring_rpm_var", None) is None:
            self.app.stirring_rpm_var = tk.IntVar(value=0)
        if getattr(self.app, "aeration_lpm_var", None) is None:
            self.app.aeration_lpm_var = tk.DoubleVar(value=0.0)
        if getattr(self.app, "feed_rate_var", None) is None:
            self.app.feed_rate_var = tk.DoubleVar(value=0.0)
        if getattr(self.app, "harvest_rate_var", None) is None:
            self.app.harvest_rate_var = tk.DoubleVar(value=0.0)

        # Свет
        if getattr(self.app, "light_lux_var", None) is None:
            self.app.light_lux_var = tk.DoubleVar(value=0.0)
        if getattr(self.app, "light_cycle_var", None) is None:
            self.app.light_cycle_var = tk.StringVar(value="")


        # Приведём gases_var к форматированному виду (всегда)
        self.app.gases_var.set(self._format_gases_config(self.app.gases_config))

        # Доступность влажности
        if getattr(self.app, "humidity_enabled_var", None) is None:
            self.app.humidity_enabled_var = tk.BooleanVar(value=True)

        # Совместимость со старым кодом
        if getattr(self.app, "visualization_mode", None) is None:
            self.app.visualization_mode = tk.StringVar(value="")

    def _parse_gases_string_to_config(self, s: str) -> Dict[str, float]:
        s = (s or "").strip()
        if not s:
            return {}
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if not parts:
            return {}

        cfg: Dict[str, float] = {}
        for p in parts:
            p2 = p.replace("%", "").replace("=", " ").strip()
            tokens = [t for t in p2.split() if t]
            if not tokens:
                continue
            gas = tokens[0]
            val = None
            if len(tokens) >= 2:
                try:
                    val = float(tokens[1])
                except Exception:
                    val = None
            cfg[gas] = float(val) if val is not None else 0.0

        if cfg and all(abs(v) < 1e-9 for v in cfg.values()):
            each = 100.0 / max(1, len(cfg))
            for k in list(cfg.keys()):
                cfg[k] = round(each, 2)
        return cfg

    def _format_gases_config(self, cfg: Dict[str, float]) -> str:
        if not isinstance(cfg, dict) or not cfg:
            return ""
        order = ["O2", "CO2", "N2", "Air", "Ar", "H2", "CH4"]
        keys = list(cfg.keys())
        keys.sort(key=lambda k: (order.index(k) if k in order else 999, k))
        parts = []
        for k in keys:
            try:
                v = float(cfg.get(k, 0.0))
            except Exception:
                v = 0.0
            parts.append(f"{k} {v:g}%")
        return ", ".join(parts)

    # -------------------------
    # UI
    # -------------------------

    def _build_widgets(self):
        self._content.grid_rowconfigure(0, weight=0)
        self._content.grid_rowconfigure(1, weight=1)
        self._content.grid_rowconfigure(2, weight=0)
        self._content.grid_columnconfigure(0, weight=1)

        self._build_header_row()
        self._build_groups_row()
        self._build_bottom_buttons()


        # Применяем состояние свернутости (если задано)
        self._apply_collapsed_state()

    
    def _build_header_row(self):
        self._header_row = tk.Frame(self._content, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        self._header_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
        self._header_row.grid_columnconfigure(0, weight=0)
        self._header_row.grid_columnconfigure(1, weight=1)
        self._header_row.grid_columnconfigure(2, weight=0)
        self._header_row.grid_columnconfigure(3, weight=0)
        self._header_row.grid_columnconfigure(4, weight=0)

        lbl = tk.Label(self._header_row, text="Эксперимент:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        lbl.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.name_entry = tk.Entry(
            self._header_row,
            textvariable=self.app.exp_name_var,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            insertbackground=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        self._elapsed_lbl = tk.Label(self._header_row, text="Время эксперимента:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        self._elapsed_lbl.grid(row=0, column=2, sticky="w", padx=(0, 6))

        self._elapsed_value = tk.Label(
            self._header_row,
            textvariable=self._elapsed_var,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            font=("Consolas", 10),
            padx=10,
            pady=4,
            anchor="w",
        )
        self._elapsed_value.grid(row=0, column=3, sticky="w", padx=(0, 10))


        # Кнопка свернуть/развернуть
        self._collapse_btn = tk.Button(
            self._header_row,
            text="▾" if not getattr(self, "_collapsed", False) else "▸",
            command=self.toggle_collapsed,
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            padx=10,
            pady=2
        )
        self._collapse_btn.grid(row=0, column=4, sticky="e")

        try:
            self.name_entry.bind("<FocusOut>", lambda _e: self._log_change("Название эксперимента"), add="+")
        except Exception:
            pass

        # запуск обновления табло времени
        self._start_elapsed_timer()

    def _build_groups_row(self):
        self._groups_row = tk.Frame(self._content, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        self._groups_row.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))

        self._groups_row.grid_columnconfigure(0, weight=1, uniform="grp")
        self._groups_row.grid_columnconfigure(1, weight=1, uniform="grp")
        self._groups_row.grid_columnconfigure(2, weight=1, uniform="grp")
        self._groups_row.grid_rowconfigure(0, weight=1)

        self._grp_object = self._make_group(self._groups_row, "Объект", 0)
        self._grp_bio = self._make_group(self._groups_row, "Биология", 1)
        self._grp_env = self._make_group(self._groups_row, "Условия", 2)

        self._build_object_group(self._grp_object)
        self._build_bio_group(self._grp_bio)
        self._build_env_group(self._grp_env)

    def _build_bottom_buttons(self):
        self._bottom_row = tk.Frame(self._content, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        self._bottom_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self._bottom_row.grid_columnconfigure(0, weight=1)

        btns = tk.Frame(self._bottom_row, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        btns.grid(row=0, column=0, sticky="e")

        def mk(text: str, cmd):
            return tk.Button(
                btns,
                text=text,
                command=cmd,
                bd=0,
                relief=tk.FLAT,
                bg=self.FIELD_BG,
                fg=self.CONTENT_FG,
                activebackground=self.FIELD_BG,
                padx=12,
                pady=5
            )

        self.btn_save = mk("Сохранить", self._on_save_clicked)
        self.btn_load = mk("Загрузить", self._on_load_clicked)
        self.btn_apply = mk("Применить", self._on_apply_clicked)
        self.btn_reset = mk("Сбросить", self._on_reset_clicked)

        self.btn_reset.pack(side="right", padx=(8, 0))
        self.btn_apply.pack(side="right", padx=(8, 0))
        self.btn_load.pack(side="right", padx=(8, 0))
        self.btn_save.pack(side="right", padx=(0, 0))


    # -------------------------
    # Collapse / expand
    # -------------------------

    def _panel_height(self) -> int:
        return int(self.COLLAPSED_HEIGHT if getattr(self, "_collapsed", False) else self.BAR_HEIGHT)

    def toggle_collapsed(self):
        try:
            self._collapsed = not bool(getattr(self, "_collapsed", False))
        except Exception:
            self._collapsed = False

        try:
            self.app.settings_panel_collapsed_var.set(bool(self._collapsed))
        except Exception:
            pass

        self._apply_collapsed_state()
        self.reposition()

        # Обновим фон (если есть)
        try:
            if getattr(self, "_window_bg_pil", None) is not None:
                self.update_background_snapshot(self._window_bg_pil)
        except Exception:
            pass

        # Поднимаем панель наверх (чтобы кнопка всегда была кликабельной)
        try:
            self.frame.lift()
        except Exception:
            pass

    def _apply_collapsed_state(self):
        collapsed = bool(getattr(self, "_collapsed", False))

        # Кнопка
        try:
            if getattr(self, "_collapse_btn", None) is not None:
                self._collapse_btn.configure(text="▸" if collapsed else "▾")
        except Exception:
            pass

        # В свернутом виде оставляем только строку заголовка (название эксперимента + кнопка)
        try:
            if getattr(self, "_elapsed_lbl", None) is not None:
                # показываем время и в свернутом виде
                try:
                    self._elapsed_lbl.configure(text=("Время:" if collapsed else "Время эксперимента:"))
                except Exception:
                    pass
                self._elapsed_lbl.grid()
        except Exception:
            pass
        try:
            if getattr(self, "_elapsed_value", None) is not None:
                # показываем значение времени и в свернутом виде
                self._elapsed_value.grid()
        except Exception:
            pass

        try:
            if getattr(self, "_groups_row", None) is not None:
                (self._groups_row.grid_remove() if collapsed else self._groups_row.grid())
        except Exception:
            pass

        try:
            if getattr(self, "_bottom_row", None) is not None:
                (self._bottom_row.grid_remove() if collapsed else self._bottom_row.grid())
        except Exception:
            pass

        # Уплотняем вертикальные отступы заголовка в свернутом виде
        try:
            if getattr(self, "_header_row", None) is not None:
                self._header_row.grid_configure(pady=(6, 6) if collapsed else (8, 6))
        except Exception:
            pass

    def _make_group(self, parent: tk.Misc, title: str, col: int) -> tk.Frame:
        wrap = tk.Frame(
            parent,
            bg=self.CONTENT_BG,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER
        )
        wrap.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0), pady=0)
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        title_lbl = tk.Label(wrap, text=title, bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9, "bold"))
        title_lbl.grid(row=0, column=0, sticky="w", padx=8, pady=(6, 4))

        inner = tk.Frame(wrap, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        inner.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        inner.grid_columnconfigure(1, weight=1)
        return inner

    def _build_object_group(self, g: tk.Frame):
        lbl = tk.Label(g, text="Посуда:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        lbl.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6))

        self.vessel_entry = tk.Entry(
            g,
            textvariable=self.app.vessel_name_var,
            state="readonly",
            readonlybackground=self.FIELD_BG,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            fg=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        self.vessel_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        btn = tk.Button(
            g,
            text="…",
            width=3,
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            command=self._select_vessel_from_db
        )
        btn.grid(row=0, column=2, sticky="e", padx=(6, 0), pady=(0, 6))

        t_lbl = tk.Label(g, text="Тип:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        t_lbl.grid(row=1, column=0, sticky="w", padx=(0, 6))

        self.vessel_type_value = tk.Label(g, textvariable=self.app.vessel_type_var, bg=self.CONTENT_BG,
                                          fg=self.CONTENT_FG, font=("Segoe UI", 9))
        self.vessel_type_value.grid(row=1, column=1, columnspan=2, sticky="w")

    def _build_bio_group(self, g: tk.Frame):
        m_lbl = tk.Label(g, text="Среда:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        m_lbl.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6))

        self.medium_entry = tk.Entry(
            g,
            textvariable=self.app.medium_name_var,
            state="readonly",
            readonlybackground=self.FIELD_BG,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            fg=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        self.medium_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        m_btn = tk.Button(
            g,
            text="…",
            width=3,
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            command=self._select_medium_from_db
        )
        m_btn.grid(row=0, column=2, sticky="e", padx=(6, 0), pady=(0, 6))

        c_lbl = tk.Label(g, text="Культура:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        c_lbl.grid(row=1, column=0, sticky="w", padx=(0, 6))

        self.culture_entry = tk.Entry(
            g,
            textvariable=self.app.culture_name_var,
            state="readonly",
            readonlybackground=self.FIELD_BG,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            fg=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        self.culture_entry.grid(row=1, column=1, sticky="ew")

        c_btn = tk.Button(
            g,
            text="…",
            width=3,
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            command=self._select_culture_from_db
        )
        c_btn.grid(row=1, column=2, sticky="e", padx=(6, 0))

    def _build_env_group(self, g: tk.Frame):
        t_lbl = tk.Label(g, text="T°C:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        t_lbl.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 6))

        self.temp_spin = tk.Spinbox(
            g,
            from_=-20.0,
            to=120.0,
            increment=0.5,
            textvariable=self.app.temperature_c_var,
            width=7,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            insertbackground=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        self.temp_spin.grid(row=0, column=1, sticky="w", pady=(0, 6))


        extra_btn = tk.Button(
            g,
            text="Доп. условия…",
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            command=self._open_extra_conditions_popup
        )
        extra_btn.grid(row=0, column=2, sticky="e", padx=(10, 0), pady=(0, 6))

        h_lbl = tk.Label(g, text="Влажн.%:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        h_lbl.grid(row=1, column=0, sticky="w", padx=(0, 6))

        self.hum_spin = tk.Spinbox(
            g,
            from_=0,
            to=100,
            textvariable=self.app.humidity_var,
            width=7,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            insertbackground=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        self.hum_spin.grid(row=1, column=1, sticky="w")

        gas_lbl = tk.Label(g, text="Газы:", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9))
        gas_lbl.grid(row=2, column=0, sticky="w", padx=(0, 6), pady=(6, 0))

        self.gases_value = tk.Label(
            g,
            textvariable=self.app.gases_var,
            bg=self.CONTENT_BG,
            fg=self.CONTENT_FG,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=240
        )
        self.gases_value.grid(row=2, column=1, sticky="w", pady=(6, 0))

        gas_btn = tk.Button(
            g,
            text="Настроить…",
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            command=self._open_gases_popup
        )
        gas_btn.grid(row=2, column=2, sticky="e", padx=(6, 0), pady=(6, 0))

        try:
            self.temp_spin.bind("<FocusOut>", lambda _e: self._log_change("Температура"), add="+")
            self.hum_spin.bind("<FocusOut>", lambda _e: self._log_change("Влажность"), add="+")
        except Exception:
            pass

        self._apply_humidity_enabled(bool(self.app.humidity_enabled_var.get()))

    # -------------------------
    # DB selection logic
    # -------------------------

    
    def _open_extra_conditions_popup(self):
        """Дополнительные условия (pH, DO, осмолярность, глюкоза, механика, свет).

        Окно используется для заполнения базовых условий (до старта эксперимента).
        """
        win = tk.Toplevel(self.root)
        win.title("Дополнительные условия")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=self.CONTENT_BG)

        outer = tk.Frame(win, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)

        # --- tab: chemistry
        tab1 = tk.Frame(nb, bg=self.CONTENT_BG)
        nb.add(tab1, text="Среда и химия")

        def mk_row(parent, r, label, var, frm=None, to=None, inc=None, width=10):
            tk.Label(parent, text=label, bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9)).grid(
                row=r, column=0, sticky="w", padx=(0, 10), pady=6
            )
            if frm is not None and to is not None:
                sb = tk.Spinbox(
                    parent,
                    from_=frm,
                    to=to,
                    increment=(inc if inc is not None else 1),
                    textvariable=var,
                    width=width,
                    bd=0,
                    relief=tk.FLAT,
                    highlightthickness=1,
                    highlightbackground=self.BORDER,
                    highlightcolor=self.BORDER,
                    bg=self.FIELD_BG,
                    fg=self.CONTENT_FG,
                    insertbackground=self.CONTENT_FG,
                    font=("Segoe UI", 9)
                )
                sb.grid(row=r, column=1, sticky="w", pady=6)
            else:
                ent = tk.Entry(
                    parent,
                    textvariable=var,
                    width=width,
                    bd=0,
                    relief=tk.FLAT,
                    highlightthickness=1,
                    highlightbackground=self.BORDER,
                    highlightcolor=self.BORDER,
                    bg=self.FIELD_BG,
                    fg=self.CONTENT_FG,
                    insertbackground=self.CONTENT_FG,
                    font=("Segoe UI", 9)
                )
                ent.grid(row=r, column=1, sticky="w", pady=6)

        tab1.grid_columnconfigure(1, weight=1)
        mk_row(tab1, 0, "pH:", self.app.ph_var, frm=0.0, to=14.0, inc=0.1, width=8)
        mk_row(tab1, 1, "DO (%):", self.app.do_var, frm=0.0, to=100.0, inc=1.0, width=8)
        mk_row(tab1, 2, "Осмолярность (mOsm/kg):", self.app.osmolality_var, frm=0.0, to=2000.0, inc=10.0, width=10)
        mk_row(tab1, 3, "Глюкоза (g/L):", self.app.glucose_var, frm=0.0, to=1000.0, inc=0.1, width=10)

        # --- tab: reactor
        tab2 = tk.Frame(nb, bg=self.CONTENT_BG)
        nb.add(tab2, text="Реактор / механика")
        tab2.grid_columnconfigure(1, weight=1)

        mk_row(tab2, 0, "Перемешивание (RPM):", self.app.stirring_rpm_var, frm=0, to=3000, inc=10, width=8)
        mk_row(tab2, 1, "Аэрация (L/min):", self.app.aeration_lpm_var, frm=0.0, to=100.0, inc=0.1, width=8)
        mk_row(tab2, 2, "Подача (mL/h):", self.app.feed_rate_var, frm=0.0, to=10000.0, inc=1.0, width=10)
        mk_row(tab2, 3, "Отбор (mL/h):", self.app.harvest_rate_var, frm=0.0, to=10000.0, inc=1.0, width=10)

        # --- tab: light
        tab3 = tk.Frame(nb, bg=self.CONTENT_BG)
        nb.add(tab3, text="Свет")
        tab3.grid_columnconfigure(1, weight=1)

        mk_row(tab3, 0, "Освещённость (lux):", self.app.light_lux_var, frm=0.0, to=200000.0, inc=10.0, width=10)

        tk.Label(tab3, text="Цикл (день/ночь):", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=6
        )
        cyc = tk.Entry(
            tab3,
            textvariable=self.app.light_cycle_var,
            width=20,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            insertbackground=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        cyc.grid(row=1, column=1, sticky="w", pady=6)

        # buttons
        btns = tk.Frame(outer, bg=self.CONTENT_BG)
        btns.pack(fill="x", pady=(12, 0))

        def _ok(_e=None):
            # просто закрываем — переменные уже связаны
            try:
                self._log_change("Доп. условия")
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        def _cancel():
            try:
                win.destroy()
            except Exception:
                pass

        ok_btn = tk.Button(
            btns,
            text="ОК",
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            command=_ok
        )
        ok_btn.pack(side="right")

        cancel_btn = tk.Button(
            btns,
            text="Отмена",
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            command=_cancel
        )
        cancel_btn.pack(side="right", padx=(0, 8))

        win.bind("<Return>", _ok, add="+")
        win.bind("<KP_Enter>", _ok, add="+")

    def _select_vessel_from_db(self):
        cols = [("name", "Конфигурация"), ("type", "Тип"), ("volume", "Объём")]
        rows = self._db_load_vessels()
        self._open_selector_dialog(
            title="Выбор посуды/системы",
            columns=cols,
            rows=rows,
            search_hint="Поиск (конфигурация/тип)...",
            on_selected=self._apply_vessel_selection
        )

    def _select_medium_from_db(self):
        cols = [("name", "Название"), ("type", "Тип"), ("ph", "pH")]
        rows = self._db_load_media()
        self._open_selector_dialog(
            title="Выбор питательной среды",
            columns=cols,
            rows=rows,
            search_hint="Поиск (название/тип)...",
            on_selected=self._apply_medium_selection
        )

    def _select_culture_from_db(self):
        cols = [("name", "Культура"), ("type", "Род/вид"), ("opt", "T°opt")]
        rows = self._db_load_cultures()
        self._open_selector_dialog(
            title="Выбор изначальной культуры",
            columns=cols,
            rows=rows,
            search_hint="Поиск (род/вид/штамм)...",
            on_selected=self._apply_culture_selection
        )

    def _db_load_vessels(self) -> List[Dict[str, Any]]:
        if not self._db_ok:
            self._log_error("База данных недоступна: не удалось импортировать database/database.py")
            return []

        self._db_ensure()
        conn = self._db_conn()
        if conn is None:
            return []

        out: List[Dict[str, Any]] = []
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, system_type, configuration, volume
                FROM bioreactor_params
                ORDER BY system_type, configuration
            """)
            for (rid, system_type, configuration, volume) in cur.fetchall():
                name = str(configuration or "").strip()
                typ = str(system_type or "").strip()
                vol_str = "" if volume is None else str(volume)
                out.append({
                    "id": str(rid),
                    "name": name if name else "(без названия)",
                    "type": typ,
                    "volume": vol_str,
                })
        except Exception as e:
            self._log_error(f"Ошибка чтения bioreactor_params: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return out

    def _db_load_media(self) -> List[Dict[str, Any]]:
        if not self._db_ok:
            self._log_error("База данных недоступна: не удалось импортировать database/database.py")
            return []

        self._db_ensure()
        conn = self._db_conn()
        if conn is None:
            return []

        out: List[Dict[str, Any]] = []
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, name, media_type, ph
                FROM culture_media
                ORDER BY media_type, name
            """)
            for (rid, name, media_type, ph) in cur.fetchall():
                ph_str = "" if ph is None else str(ph)
                out.append({
                    "id": str(rid),
                    "name": str(name or "").strip() or "(без названия)",
                    "type": str(media_type or "").strip(),
                    "ph": ph_str
                })
        except Exception as e:
            self._log_error(f"Ошибка чтения culture_media: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return out

    def _db_load_cultures(self) -> List[Dict[str, Any]]:
        if not self._db_ok:
            self._log_error("База данных недоступна: не удалось импортировать database/database.py")
            return []

        self._db_ensure()
        conn = self._db_conn()
        if conn is None:
            return []

        out: List[Dict[str, Any]] = []
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, genus, species, strain, temperature_optimum
                FROM microorganisms
                ORDER BY genus, species, strain
            """)
            for (rid, genus, species, strain, t_opt) in cur.fetchall():
                genus = str(genus or "").strip()
                species = str(species or "").strip()
                strain = str(strain or "").strip()

                full = f"{genus} {species}".strip()
                if strain:
                    full = f"{full} ({strain})"

                t_str = "" if t_opt is None else str(t_opt)
                out.append({
                    "id": str(rid),
                    "name": full if full else "(без названия)",
                    "type": f"{genus} {species}".strip(),
                    "opt": t_str
                })
        except Exception as e:
            self._log_error(f"Ошибка чтения microorganisms: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

        return out

    # -------------------------
    # Selector dialog (Treeview + search)
    # -------------------------

    def _open_selector_dialog(
        self,
        title: str,
        columns: List[Tuple[str, str]],
        rows: List[Dict[str, Any]],
        search_hint: str,
        on_selected: Callable[[Dict[str, Any]], None]
    ):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=self.CONTENT_BG)

        outer = tk.Frame(win, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        search_var = tk.StringVar(value="")
        search_entry = tk.Entry(
            outer,
            textvariable=search_var,
            bd=0,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            insertbackground=self.CONTENT_FG,
            font=("Segoe UI", 9)
        )
        search_entry.pack(fill="x")
        hint = tk.Label(outer, text=search_hint, bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 8))
        hint.pack(anchor="w", pady=(4, 8))

        table_frame = tk.Frame(outer, bg=self.CONTENT_BG)
        table_frame.pack(fill="both", expand=True)

        tv_cols = [c[0] for c in columns]
        tree = ttk.Treeview(table_frame, columns=tv_cols, show="headings", height=10)
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)

        for key, hdr in columns:
            tree.heading(key, text=hdr)
            tree.column(key, width=120, anchor="w")

        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        iid_to_row: Dict[str, Dict[str, Any]] = {}

        def _fill(data: List[Dict[str, Any]]):
            tree.delete(*tree.get_children())
            iid_to_row.clear()
            for i, r in enumerate(data):
                values = [r.get(k, "") for k, _ in columns]
                iid = f"r{i}"
                iid_to_row[iid] = r
                tree.insert("", "end", iid=iid, values=values)
            ch = tree.get_children()
            if ch:
                tree.selection_set(ch[0])
                tree.focus(ch[0])

        def _filter(*_):
            q = search_var.get().strip().lower()
            if not q:
                _fill(rows)
                return
            filtered = []
            for r in rows:
                blob = " ".join(str(v) for v in r.values()).lower()
                if q in blob:
                    filtered.append(r)
            _fill(filtered)

        _fill(rows)
        search_var.trace_add("write", _filter)

        btns = tk.Frame(outer, bg=self.CONTENT_BG)
        btns.pack(fill="x", pady=(10, 0))

        def _ok():
            sel = tree.selection()
            if not sel:
                win.destroy()
                return
            iid = sel[0]
            item = iid_to_row.get(iid)
            if item:
                on_selected(item)
            win.destroy()

        def _cancel():
            win.destroy()

        tree.bind("<Double-1>", lambda _e: _ok(), add="+")
        win.bind("<Return>", lambda _e: _ok(), add="+")
        win.bind("<Escape>", lambda _e: _cancel(), add="+")
        search_entry.focus_set()

        ok_btn = tk.Button(btns, text="Выбрать", command=_ok, bd=0, relief=tk.FLAT, bg=self.FIELD_BG, fg=self.CONTENT_FG)
        ok_btn.pack(side="right", padx=(8, 0))
        cancel_btn = tk.Button(btns, text="Отмена", command=_cancel, bd=0, relief=tk.FLAT, bg=self.FIELD_BG, fg=self.CONTENT_FG)
        cancel_btn.pack(side="right")

        win.geometry("640x420")

    # -------------------------
    # Apply selections
    # -------------------------

    def _apply_vessel_selection(self, item: Dict[str, Any]):
        self._mark_settings_dirty()
        vid = str(item.get("id", ""))
        name = str(item.get("name", "Не выбрано"))
        vtype = str(item.get("type", ""))

        self.app.vessel_id_var.set(vid)
        self.app.vessel_name_var.set(name)
        self.app.vessel_type_var.set(vtype)

        # Объём (мл) — нужен для мониторинга и движка
        try:
            vol = item.get("volume", "")
            if vol in (None, ""):
                vol_f = 0.0
            else:
                vol_f = float(str(vol).replace(",", "."))
            if hasattr(self.app, "vessel_volume_var"):
                self.app.vessel_volume_var.set(vol_f)
        except Exception:
            try:
                if hasattr(self.app, "vessel_volume_var"):
                    self.app.vessel_volume_var.set(0.0)
            except Exception:
                pass

        # Доп. параметры могут приходить из item (на будущее). Сейчас по умолчанию пусто,
        # чтобы не ломать выбор посуды из справочника.
        cond = item.get("conditions", {})
        if not isinstance(cond, dict):
            cond = {}
        # Дополнительные условия (если присутствуют в файле)
        try:
            if "ph" in cond and hasattr(self.app, "ph_var"):
                self.app.ph_var.set(float(cond.get("ph", self.app.ph_var.get())))
        except Exception:
            pass
        try:
            if "do_percent" in cond and hasattr(self.app, "do_var"):
                self.app.do_var.set(float(cond.get("do_percent", self.app.do_var.get())))
        except Exception:
            pass
        try:
            if "osmolality" in cond and hasattr(self.app, "osmolality_var"):
                self.app.osmolality_var.set(float(cond.get("osmolality", self.app.osmolality_var.get())))
        except Exception:
            pass
        try:
            if "glucose" in cond and hasattr(self.app, "glucose_var"):
                self.app.glucose_var.set(float(cond.get("glucose", self.app.glucose_var.get())))
        except Exception:
            pass

        try:
            if "stirring_rpm" in cond and hasattr(self.app, "stirring_rpm_var"):
                self.app.stirring_rpm_var.set(int(cond.get("stirring_rpm", self.app.stirring_rpm_var.get())))
        except Exception:
            pass
        try:
            if "aeration_lpm" in cond and hasattr(self.app, "aeration_lpm_var"):
                self.app.aeration_lpm_var.set(float(cond.get("aeration_lpm", self.app.aeration_lpm_var.get())))
        except Exception:
            pass
        try:
            if "feed_rate" in cond and hasattr(self.app, "feed_rate_var"):
                self.app.feed_rate_var.set(float(cond.get("feed_rate", self.app.feed_rate_var.get())))
        except Exception:
            pass
        try:
            if "harvest_rate" in cond and hasattr(self.app, "harvest_rate_var"):
                self.app.harvest_rate_var.set(float(cond.get("harvest_rate", self.app.harvest_rate_var.get())))
        except Exception:
            pass

        try:
            if "light_lux" in cond and hasattr(self.app, "light_lux_var"):
                self.app.light_lux_var.set(float(cond.get("light_lux", self.app.light_lux_var.get())))
        except Exception:
            pass
        try:
            if "light_cycle" in cond and hasattr(self.app, "light_cycle_var"):
                self.app.light_cycle_var.set(str(cond.get("light_cycle", self.app.light_cycle_var.get())))
        except Exception:
            pass



        try:
            self.app.visualization_mode.set(name)
        except Exception:
            pass

        is_reactor = self._is_reactor_like(vtype, name)
        self.app.humidity_enabled_var.set(not is_reactor)
        self._apply_humidity_enabled(not is_reactor)

        self._log_change("Посуда")

    def _apply_medium_selection(self, item: Dict[str, Any]):
        self._mark_settings_dirty()
        mid = str(item.get("id", ""))
        name = str(item.get("name", "Не выбрано"))
        self.app.medium_id_var.set(mid)
        self.app.medium_name_var.set(name)
        self._log_change("Среда")

    def _apply_culture_selection(self, item: Dict[str, Any]):
        self._mark_settings_dirty()
        cid = str(item.get("id", ""))
        name = str(item.get("name", "Не выбрано"))
        self.app.culture_id_var.set(cid)
        self.app.culture_name_var.set(name)
        self._log_change("Изначальная культура")

    def _is_reactor_like(self, system_type: str, configuration: str) -> bool:
        s = f"{system_type} {configuration}".lower()
        keys = ["реактор", "bioreactor", "хемостат", "fed", "мини-биореактор", "ферментер"]
        return any(k in s for k in keys)

    def _apply_humidity_enabled(self, enabled: bool):
        try:
            self.hum_spin.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass

    # -------------------------
    # Gas popup (concentrations)
    # -------------------------

    def _open_gases_popup(self):
        win = tk.Toplevel(self.root)
        win.title("Газы — первоначальная концентрация")
        win.transient(self.root)
        win.grab_set()
        win.configure(bg=self.CONTENT_BG)

        outer = tk.Frame(win, bg=self.CONTENT_BG, bd=0, highlightthickness=0)
        outer.pack(fill="both", expand=True, padx=12, pady=12)

        lbl = tk.Label(
            outer,
            text="Отметьте газы и задайте первоначальную концентрацию (%):",
            bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9)
        )
        lbl.pack(anchor="w", pady=(0, 10))

        table = tk.Frame(outer, bg=self.CONTENT_BG)
        table.pack(fill="both", expand=True)

        hdr1 = tk.Label(table, text="Газ", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9, "bold"))
        hdr2 = tk.Label(table, text="Концентрация (%)", bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 9, "bold"))
        hdr1.grid(row=0, column=0, sticky="w", padx=(0, 10))
        hdr2.grid(row=0, column=1, sticky="w")

        current_cfg: Dict[str, float] = {}
        try:
            if isinstance(getattr(self.app, "gases_config", None), dict):
                current_cfg = dict(self.app.gases_config)
        except Exception:
            current_cfg = {}

        rows_vars: Dict[str, Dict[str, Any]] = {}

        def _set_entry_state(gas: str):
            rec = rows_vars.get(gas)
            if not rec:
                return
            enabled = bool(rec["enabled"].get())
            try:
                rec["entry"].configure(state=("normal" if enabled else "disabled"))
            except Exception:
                pass

        for i, gas in enumerate(self.DEFAULT_GASES, start=1):
            enabled_var = tk.BooleanVar(value=(gas in current_cfg))
            val_var = tk.StringVar(value=str(current_cfg.get(gas, 0.0)) if gas in current_cfg else "0")

            cb = tk.Checkbutton(
                table,
                text=gas,
                variable=enabled_var,
                bg=self.CONTENT_BG,
                fg=self.CONTENT_FG,
                activebackground=self.CONTENT_BG,
                activeforeground=self.CONTENT_FG,
                selectcolor=self.CONTENT_BG,
                command=lambda g=gas: _set_entry_state(g)
            )
            cb.grid(row=i, column=0, sticky="w", pady=2)

            ent = tk.Entry(
                table,
                textvariable=val_var,
                bd=0,
                relief=tk.FLAT,
                highlightthickness=1,
                highlightbackground=self.BORDER,
                highlightcolor=self.BORDER,
                bg=self.FIELD_BG,
                fg=self.CONTENT_FG,
                insertbackground=self.CONTENT_FG,
                font=("Segoe UI", 9),
                width=12
            )
            ent.grid(row=i, column=1, sticky="w", pady=2)

            rows_vars[gas] = {"enabled": enabled_var, "value": val_var, "entry": ent}
            _set_entry_state(gas)

        info = tk.Label(
            outer,
            text=f"Проверка: сумма концентраций должна быть {self.GAS_SUM_TARGET:g}% (допуск ±{self.GAS_SUM_TOL:g}%).",
            bg=self.CONTENT_BG, fg=self.CONTENT_FG, font=("Segoe UI", 8)
        )
        info.pack(anchor="w", pady=(10, 0))

        btns = tk.Frame(outer, bg=self.CONTENT_BG)
        btns.pack(fill="x", pady=(12, 0))

        def _apply_default_mix():
            for gas in self.DEFAULT_GASES:
                rec = rows_vars.get(gas)
                if not rec:
                    continue
                if gas in self.DEFAULT_GAS_MIX:
                    rec["enabled"].set(True)
                    rec["value"].set(str(self.DEFAULT_GAS_MIX[gas]))
                else:
                    rec["enabled"].set(False)
                    rec["value"].set("0")
                _set_entry_state(gas)

        def _ok():
            cfg: Dict[str, float] = {}
            total = 0.0

            for gas, rec in rows_vars.items():
                if not bool(rec["enabled"].get()):
                    continue

                raw = str(rec["value"].get()).strip().replace(",", ".")
                try:
                    v = float(raw)
                except Exception:
                    messagebox.showwarning("Газы", f"Некорректное значение концентрации для {gas}")
                    return

                # диапазон
                if v < 0.0 or v > 100.0:
                    messagebox.showwarning("Газы", f"Концентрация {gas} должна быть в диапазоне 0–100%")
                    return

                cfg[gas] = v
                total += v

            if not cfg:
                cfg = dict(self.DEFAULT_GAS_MIX)
                total = sum(float(x) for x in cfg.values())

            # проверка суммы
            if abs(total - self.GAS_SUM_TARGET) > self.GAS_SUM_TOL:
                messagebox.showwarning(
                    "Газы",
                    f"Суммарная концентрация = {total:g}%.\n"
                    f"Должно быть {self.GAS_SUM_TARGET:g}% (допуск ±{self.GAS_SUM_TOL:g}%)."
                )
                return

            self.app.gases_config = cfg
            self.app.gases_var.set(self._format_gases_config(cfg))
            self._log_change("Газы (концентрации)")
            win.destroy()

        def _cancel():
            win.destroy()

        def _defaults():
            _apply_default_mix()

        btn_defaults = tk.Button(
            btns,
            text="Стандартная смесь",
            command=_defaults,
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG
        )
        btn_defaults.pack(side="left")

        btn_ok = tk.Button(
            btns,
            text="Применить",
            command=_ok,
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            padx=12
        )
        btn_ok.pack(side="right", padx=(8, 0))

        btn_cancel = tk.Button(
            btns,
            text="Отмена",
            command=_cancel,
            bd=0,
            relief=tk.FLAT,
            bg=self.FIELD_BG,
            fg=self.CONTENT_FG,
            activebackground=self.FIELD_BG,
            padx=12
        )
        btn_cancel.pack(side="right")

        win.geometry("430x420")

    # -------------------------
    # Bottom buttons actions
    # -------------------------

    def _default_settings_path(self) -> str:
        base_dir = getattr(self.app, "module_dir", os.getcwd())
        return os.path.join(base_dir, "experiment_settings.json")

    def _collect_settings(self) -> Dict[str, Any]:
        gases_cfg = {}
        try:
            if isinstance(getattr(self.app, "gases_config", None), dict):
                gases_cfg = dict(self.app.gases_config)
        except Exception:
            gases_cfg = {}

        data = {
            "exp_name": self.app.exp_name_var.get() if hasattr(self.app, "exp_name_var") else "Эксперимент",
            "duration": int(self.app.duration_var.get()) if hasattr(self.app, "duration_var") else 1,

            "vessel": {
                "id": self.app.vessel_id_var.get() if hasattr(self.app, "vessel_id_var") else "",
                "name": self.app.vessel_name_var.get() if hasattr(self.app, "vessel_name_var") else "",
                "type": self.app.vessel_type_var.get() if hasattr(self.app, "vessel_type_var") else "",
                "volume": float(self.app.vessel_volume_var.get()) if hasattr(self.app, "vessel_volume_var") else 0.0,
            },
            "medium": {
                "id": self.app.medium_id_var.get() if hasattr(self.app, "medium_id_var") else "",
                "name": self.app.medium_name_var.get() if hasattr(self.app, "medium_name_var") else "",
            },
            "culture": {
                "id": self.app.culture_id_var.get() if hasattr(self.app, "culture_id_var") else "",
                "name": self.app.culture_name_var.get() if hasattr(self.app, "culture_name_var") else "",
            },

            "conditions": {
                "temperature_c": float(self.app.temperature_c_var.get()) if hasattr(self.app, "temperature_c_var") else 37.0,
                "humidity": int(self.app.humidity_var.get()) if hasattr(self.app, "humidity_var") else 60,
                "humidity_enabled": bool(self.app.humidity_enabled_var.get()) if hasattr(self.app, "humidity_enabled_var") else True,
                "gases": gases_cfg,
                "ph": float(self.app.ph_var.get()) if hasattr(self.app, "ph_var") else 7.4,
                "do_percent": float(self.app.do_var.get()) if hasattr(self.app, "do_var") else 100.0,
                "osmolality": float(self.app.osmolality_var.get()) if hasattr(self.app, "osmolality_var") else 300.0,
                "glucose": float(self.app.glucose_var.get()) if hasattr(self.app, "glucose_var") else 0.0,
                "stirring_rpm": int(self.app.stirring_rpm_var.get()) if hasattr(self.app, "stirring_rpm_var") else 0,
                "aeration_lpm": float(self.app.aeration_lpm_var.get()) if hasattr(self.app, "aeration_lpm_var") else 0.0,
                "feed_rate": float(self.app.feed_rate_var.get()) if hasattr(self.app, "feed_rate_var") else 0.0,
                "harvest_rate": float(self.app.harvest_rate_var.get()) if hasattr(self.app, "harvest_rate_var") else 0.0,
                "light_lux": float(self.app.light_lux_var.get()) if hasattr(self.app, "light_lux_var") else 0.0,
                "light_cycle": str(self.app.light_cycle_var.get()) if hasattr(self.app, "light_cycle_var") else "",
            }
        }
        return data

    def _apply_settings_dict(self, data: Dict[str, Any]):
        if not isinstance(data, dict):
            return

        try:
            self.app.exp_name_var.set(str(data.get("exp_name", "Эксперимент")))
        except Exception:
            pass
        try:
            self.app.duration_var.set(int(data.get("duration", 1)))
        except Exception:
            pass

        v = data.get("vessel", {}) if isinstance(data.get("vessel", {}), dict) else {}
        m = data.get("medium", {}) if isinstance(data.get("medium", {}), dict) else {}
        c = data.get("culture", {}) if isinstance(data.get("culture", {}), dict) else {}
        cond = data.get("conditions", {}) if isinstance(data.get("conditions", {}), dict) else {}

        try:
            self.app.vessel_id_var.set(str(v.get("id", "")))
            self.app.vessel_name_var.set(str(v.get("name", "Не выбрано")) or "Не выбрано")
            self.app.vessel_type_var.set(str(v.get("type", "")))
            try:
                if hasattr(self.app, "vessel_volume_var"):
                    self.app.vessel_volume_var.set(float(v.get("volume", 0.0) or 0.0))
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.app.medium_id_var.set(str(m.get("id", "")))
            self.app.medium_name_var.set(str(m.get("name", "Не выбрано")) or "Не выбрано")
        except Exception:
            pass

        try:
            self.app.culture_id_var.set(str(c.get("id", "")))
            self.app.culture_name_var.set(str(c.get("name", "Не выбрано")) or "Не выбрано")
        except Exception:
            pass

        try:
            self.app.temperature_c_var.set(float(cond.get("temperature_c", 37.0)))
        except Exception:
            pass

        try:
            he = bool(cond.get("humidity_enabled", True))
            self.app.humidity_enabled_var.set(he)
            self._apply_humidity_enabled(he)
        except Exception:
            pass

        try:
            self.app.humidity_var.set(int(cond.get("humidity", 60)))
        except Exception:
            pass

        gases = cond.get("gases", {})
        if isinstance(gases, dict) and gases:
            try:
                cfg: Dict[str, float] = {}
                for k, v in gases.items():
                    try:
                        cfg[str(k)] = float(v)
                    except Exception:
                        cfg[str(k)] = 0.0
                self.app.gases_config = cfg
                self.app.gases_var.set(self._format_gases_config(cfg))
            except Exception:
                pass

        try:
            self.app.visualization_mode.set(self.app.vessel_name_var.get())
        except Exception:
            pass

    def _on_save_clicked(self):
        data = self._collect_settings()
        default_path = self._default_settings_path()

        path = filedialog.asksaveasfilename(
            title="Сохранить настройки эксперимента",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialdir=os.path.dirname(default_path),
            initialfile=os.path.basename(default_path),
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log_change("Сохранение настроек")
        except Exception as e:
            self._log_error(f"Ошибка сохранения: {e}")
            messagebox.showerror("Сохранение", f"Не удалось сохранить файл:\n{e}")

    def _on_load_clicked(self):
        self._mark_settings_dirty()
        default_path = self._default_settings_path()

        path = filedialog.askopenfilename(
            title="Загрузить настройки эксперимента",
            filetypes=[("JSON", "*.json")],
            initialdir=os.path.dirname(default_path),
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_settings_dict(data)
            self._log_change("Загрузка настроек")
        except Exception as e:
            self._log_error(f"Ошибка загрузки: {e}")
            messagebox.showerror("Загрузка", f"Не удалось загрузить файл:\n{e}")

    def _on_apply_clicked(self):
        self._log_change("Применить настройки")
        fn = getattr(self.app, "apply_settings", None)
        if callable(fn):
            try:
                fn()
            except Exception:
                pass

    def _on_reset_clicked(self):
        self._mark_settings_dirty()
        try:
            self.app.exp_name_var.set("Эксперимент")
        except Exception:
            pass
        try:
            self.app.duration_var.set(1)
        except Exception:
            pass

        try:
            self.app.vessel_id_var.set("")
            self.app.vessel_name_var.set("Не выбрано")
            self.app.vessel_type_var.set("")
            try:
                if hasattr(self.app, "vessel_volume_var"):
                    self.app.vessel_volume_var.set(0.0)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self.app.medium_id_var.set("")
            self.app.medium_name_var.set("Не выбрано")
        except Exception:
            pass

        try:
            self.app.culture_id_var.set("")
            self.app.culture_name_var.set("Не выбрано")
        except Exception:
            pass

        try:
            self.app.temperature_c_var.set(37.0)
        except Exception:
            pass

        try:
            self.app.humidity_enabled_var.set(True)
            self._apply_humidity_enabled(True)
            self.app.humidity_var.set(60)
        except Exception:
            pass

        try:
            self.app.gases_config = dict(self.DEFAULT_GAS_MIX)
            self.app.gases_var.set(self._format_gases_config(self.app.gases_config))
        except Exception:
            pass


        try:
            if hasattr(self.app, "ph_var"):
                self.app.ph_var.set(7.4)
            if hasattr(self.app, "do_var"):
                self.app.do_var.set(100.0)
            if hasattr(self.app, "osmolality_var"):
                self.app.osmolality_var.set(300.0)
            if hasattr(self.app, "glucose_var"):
                self.app.glucose_var.set(0.0)

            if hasattr(self.app, "stirring_rpm_var"):
                self.app.stirring_rpm_var.set(0)
            if hasattr(self.app, "aeration_lpm_var"):
                self.app.aeration_lpm_var.set(0.0)
            if hasattr(self.app, "feed_rate_var"):
                self.app.feed_rate_var.set(0.0)
            if hasattr(self.app, "harvest_rate_var"):
                self.app.harvest_rate_var.set(0.0)

            if hasattr(self.app, "light_lux_var"):
                self.app.light_lux_var.set(0.0)
            if hasattr(self.app, "light_cycle_var"):
                self.app.light_cycle_var.set("")
        except Exception:
            pass

        try:
            self.app.visualization_mode.set(self.app.vessel_name_var.get())
        except Exception:
            pass

        self._log_change("Сброс настроек")

    # -------------------------
    # Logging helpers
    # -------------------------

    
    def _mark_settings_dirty(self):
        # Любое изменение настроек требует повторного применения перед запуском.
        try:
            if hasattr(self.app, "set_experiment_settings_applied"):
                self.app.set_experiment_settings_applied(False)
            else:
                setattr(self.app, "experiment_settings_applied", False)
        except Exception:
            pass

    def _log_change(self, what: str):
        fn = getattr(self.app, "add_log_entry", None)
        if callable(fn):
            try:
                fn(f"Изменены настройки: {what}", "INFO")
            except Exception:
                pass

    def _log_error(self, text: str):
        fn = getattr(self.app, "add_log_entry", None)
        if callable(fn):
            try:
                fn(text, "ERROR")
            except Exception:
                pass

    # -------------------------
    # Layout / background
    # -------------------------

    def show(self):
        self.reposition()

    def hide(self):
        try:
            self.frame.place_forget()
        except Exception:
            pass


    # -------------------------
    # Табло времени эксперимента
    # -------------------------

    @staticmethod
    def _format_elapsed(sec: int) -> str:
        try:
            s = max(0, int(sec))
        except Exception:
            s = 0
        days = s // 86400
        s = s % 86400
        hours = s // 3600
        s = s % 3600
        minutes = s // 60
        seconds = s % 60
        # День:Часы:Минуты:Секунды
        if days < 100:
            return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{days}:{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _get_elapsed_seconds(self) -> int:
        # Предпочтительно — через метод WorkspaceApp
        fn = getattr(self.app, "get_experiment_elapsed_seconds", None)
        if callable(fn):
            try:
                return int(fn())
            except Exception:
                pass

        # Фолбэк — через _plot_t0 (используется как точка отсчёта графиков)
        try:
            if not bool(getattr(self.app, "_experiment_running", False)):
                return 0
            t0 = getattr(self.app, "_plot_t0", None)
            if t0 is None:
                return 0
            import time as _time
            return int(max(0.0, float(_time.monotonic()) - float(t0)))
        except Exception:
            return 0

    def _start_elapsed_timer(self):
        # Защита от множественных таймеров
        try:
            if self._elapsed_job is not None:
                self.root.after_cancel(self._elapsed_job)
        except Exception:
            pass
        self._elapsed_job = None

        def _tick():
            self._elapsed_job = None
            try:
                sec = self._get_elapsed_seconds()
                if self._elapsed_last_sec != sec:
                    self._elapsed_last_sec = sec
                    self._elapsed_var.set(self._format_elapsed(sec))
            except Exception:
                pass
            try:
                self._elapsed_job = self.root.after(500, _tick)
            except Exception:
                self._elapsed_job = None

        try:
            self._elapsed_job = self.root.after(200, _tick)
        except Exception:
            self._elapsed_job = None



    def _get_reserved_margins(self) -> Dict[str, int]:
        """Запрашивает отступы у WorkspaceApp, чтобы панель не заходила под оверлеи (тулбар/лог)."""
        fn = getattr(self.app, "get_reserved_margins", None)
        if callable(fn):
            try:
                m = fn()
                if isinstance(m, dict):
                    return {
                        "left": int(m.get("left", 0) or 0),
                        "top": int(m.get("top", 0) or 0),
                        "right": int(m.get("right", 0) or 0),
                        "bottom": int(m.get("bottom", 0) or 0),
                    }
            except Exception:
                pass

        # Fallback: старое поведение — смещение вправо на x_offset
        return {"left": int(self.x_offset), "top": 0, "right": 0, "bottom": 0}

    def _calc_placement(self) -> Tuple[int, int, int, int]:
        """Возвращает (x, y, width, height) для размещения панели с учётом зарезервированных отступов."""
        try:
            rw = max(1, int(self.root.winfo_width()))
            rh = max(1, int(self.root.winfo_height()))
        except Exception:
            rw, rh = 1, 1

        m = self._get_reserved_margins()
        left = max(0, int(m.get("left", self.x_offset) or 0))
        top = max(0, int(m.get("top", 0) or 0))
        right = max(0, int(m.get("right", 0) or 0))
        bottom = max(0, int(m.get("bottom", 0) or 0))

        width = max(1, rw - left - right)
        avail_h = max(1, rh - top - bottom)
        height = min(int(self._panel_height()), avail_h)

        return left, top, width, height

    def reposition(self):
        x, y, width, height = self._calc_placement()
        self.frame.place(x=x, y=y, width=width, height=height)
        self.frame.lift()

        try:
            self._apply_humidity_enabled(bool(self.app.humidity_enabled_var.get()))
        except Exception:
            pass

    def update_background_snapshot(self, window_bg_pil):
        """Обновить фоновую 'картинку' панели (glass-эффект) по фону окна.

        Важно: обновление дебаунсится (быстрое + качественное), чтобы не тормозить при изменении размера и прокрутке.
        """
        if not (_PIL_OK and Image is not None and ImageTk is not None):
            return
        if window_bg_pil is None:
            return

        self._window_bg_pil = window_bg_pil
        self._schedule_bg_update()

    def _schedule_bg_update(self):
        # Быстрое обновление (низкая стоимость) + качественное обновление после паузы
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
            self._bg_update_job_fast = self.root.after(60, lambda: self._do_bg_update(quality=False))
            self._bg_update_job_quality = self.root.after(350, lambda: self._do_bg_update(quality=True))
        except Exception:
            # если root уже закрыт/уничтожен
            self._bg_update_job_fast = None
            self._bg_update_job_quality = None

    def _do_bg_update(self, quality: bool):
        if not (_PIL_OK and Image is not None and ImageTk is not None):
            return
        window_bg_pil = getattr(self, "_window_bg_pil", None)
        if window_bg_pil is None:
            return

        try:
            x, y, width, height = self._calc_placement()
            width = max(1, int(width))
            height = max(1, int(height))

            bbox = (int(x), int(y), width, height)
            wsize = getattr(window_bg_pil, "size", None)

            # Если геометрия панели не менялась — не делаем повторный пересчёт в "быстром" проходе.
            if (not quality) and self._bg_last_bbox == bbox and self._bg_last_window_size == wsize:
                return

            self._bg_last_bbox = bbox
            self._bg_last_window_size = wsize

            left = max(0, int(x))
            top = max(0, int(y))
            right = min(int(window_bg_pil.size[0]), left + width)
            bottom = min(int(window_bg_pil.size[1]), top + height)

            if right <= left or bottom <= top:
                return

            crop = window_bg_pil.crop((left, top, right, bottom))

            # Если размер crop не совпадает с требуемым — ресайзим.
            if crop.size[0] != width or crop.size[1] != height:
                resample = Image.LANCZOS if quality else Image.BILINEAR
                crop = crop.resize((width, height), resample)

            self._bg_imgtk = ImageTk.PhotoImage(crop)
            self._bg_label.configure(image=self._bg_imgtk)
            self._bg_label.lower()
        except Exception:
            pass


    def destroy(self):
        try:
            self.frame.destroy()
        except Exception:
            pass
