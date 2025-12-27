# database/reference_books/__init__.py
"""
Пакет справочников для симуляции роста микроорганизмов
"""

__version__ = "1.0.0"
__author__ = "Microbiology Simulation Team"

# Импорт всех модулей справочников для удобного доступа
from .microorganisms import MicroorganismsWindow
from .culture_media import CultureMediaWindow
from .substances import SubstancesWindow
from .interactions import InteractionsWindow
from .bioreactor_params import BioreactorParamsWindow
from .antimicrobials import AntimicrobialsWindow
from .metabolic_pathways import MetabolicPathwaysWindow
from .experimental_protocols import ExperimentalProtocolsWindow

# Список доступных справочников
ALL_REFERENCE_BOOKS = [
    "MicroorganismsWindow",
    "CultureMediaWindow", 
    "SubstancesWindow",
    "InteractionsWindow",
    "BioreactorParamsWindow",
    "AntimicrobialsWindow",
    "MetabolicPathwaysWindow",
    "ExperimentalProtocolsWindow"
]

def get_reference_book_names():
    """Возвращает список названий справочников"""
    return [
        "Микроорганизмы",
        "Питательные среды",
        "Вещества-компоненты",
        "Типы взаимодействий",
        "Параметры биореактора",
        "Антимикробные агенты",
        "Метаболические пути/продукты",
        "Экспериментальные протоколы"
    ]

def get_window_class_by_name(name):
    """Возвращает класс окна по названию справочника"""
    mapping = {
        "Микроорганизмы": MicroorganismsWindow,
        "Питательные среды": CultureMediaWindow,
        "Вещества-компоненты": SubstancesWindow,
        "Типы взаимодействий": InteractionsWindow,
        "Параметры биореактора": BioreactorParamsWindow,
        "Антимикробные агенты": AntimicrobialsWindow,
        "Метаболические пути/продукты": MetabolicPathwaysWindow,
        "Экспериментальные протоколы": ExperimentalProtocolsWindow
    }
    return mapping.get(name)