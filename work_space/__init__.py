# work_space/__init__.py
"""Пакет рабочего пространства VitaLens.

Содержит рабочую область экспериментов (WorkspaceApp) и вспомогательные UI/утилитные модули.

Примечание:
- Модуль analysis_window является опциональным. Если файла нет в проекте, импорт не упадёт.
"""

__version__ = "1.0.0"
__author__ = "Тынкасов Николай Павлович"
__description__ = "Рабочее пространство для симуляции роста микроорганизмов"

from .workspace_app import WorkspaceApp, run_workspace
from .menu_bar import WorkspaceMenuBar, create_menu_bar

# utils может отсутствовать в некоторых сборках — не валим импорт пакета
try:
    from .utils import DataLogger, ensure_directory, save_experiment_data, load_experiment_data
except Exception:  # noqa: BLE001
    DataLogger = None  # type: ignore
    ensure_directory = None  # type: ignore
    save_experiment_data = None  # type: ignore
    load_experiment_data = None  # type: ignore

# Опциональное окно анализа (если присутствует в проекте)
try:
    from .analysis_window import AnalysisWindow, run_analysis_window
except Exception:  # noqa: BLE001
    AnalysisWindow = None  # type: ignore

    def run_analysis_window(*_args, **_kwargs):  # type: ignore
        raise ImportError("analysis_window.py отсутствует в пакете work_space")


__all__ = [
    "WorkspaceApp",
    "run_workspace",
    "WorkspaceMenuBar",
    "create_menu_bar",
    "DataLogger",
    "ensure_directory",
    "save_experiment_data",
    "load_experiment_data",
    "AnalysisWindow",
    "run_analysis_window",
]
