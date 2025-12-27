# core/bio_sim_engine.py
"""
BIO-SIM ENGINE v2.0 - Полный движок симулятора клеточных культур
Архитектура: Мультимасштабная, модульная, с пополняемой базой знаний
"""

import numpy as np
try:
    import pandas as pd  # optional; engine works without pandas if not installed
except Exception as _e:  # pragma: no cover
    pd = None
import networkx as nx
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
import json
from datetime import datetime
import hashlib
from abc import ABC, abstractmethod
import warnings

# ============================================================================
# 1. БАЗОВЫЕ ТИПЫ И ПЕРЕЧИСЛЕНИЯ
# ============================================================================

class EntityType(Enum):
    """Типы сущностей в системе"""
    CELL_LINE = "cell_line"
    PRIMARY_CULTURE = "primary_culture"
    STEM_CELL = "stem_cell"
    MICROBE = "microbe"
    VIRUS = "virus"
    CHEMICAL = "chemical"
    ANTIBIOTIC = "antibiotic"
    CHEMOTHERAPEUTIC = "chemotherapeutic"
    GROWTH_FACTOR = "growth_factor"
    MEDIUM = "medium"
    EQUIPMENT = "equipment"
    PROTOCOL = "protocol"


class InteractionType(Enum):
    """Типы взаимодействий между сущностями"""
    CONSUMPTION = "consumption"
    SECRETION = "secretion"
    INHIBITION = "inhibition"
    ACTIVATION = "activation"
    INFECTION = "infection"
    COMPETITION = "competition"
    SYMBIOSIS = "symbiosis"
    TOXICITY = "toxicity"
    NEUTRAL = "neutral"


class ConditionType(Enum):
    """Типы условий среды"""
    TEMPERATURE = "temperature"
    PH = "ph"
    OXYGEN = "oxygen"
    CO2 = "co2"
    OSMOLALITY = "osmolality"
    AGITATION = "agitation"


# ============================================================================
# 2. СИСТЕМА ПОПОЛНЯЕМЫХ СПРАВОЧНИКОВ (KNOWLEDGE BASE)
# ============================================================================

class KnowledgeBase:
    """
    Централизованная база знаний с пополняемой структурой
    Сохраняет все сущности, правила и взаимодействия
    """
    
    def __init__(self):
        # Основные хранилища
        self.entities: Dict[str, 'BioEntity'] = {}
        self.interactions: Dict[str, 'InteractionRule'] = {}
        self.protocols: Dict[str, 'Protocol'] = {}
        self.conditions: Dict[str, 'ConditionProfile'] = {}
        
        # Граф отношений между сущностями
        self.relation_graph = nx.MultiDiGraph()
        
        # Версионирование и история
        self.version_history = []
        self.change_log = []
        
        # Система категорий и тегов
        self.categories = {
            'cell_lines': {},
            'chemicals': {},
            'equipment': {},
            'protocols': {},
            'diseases': {}
        }
        
        # Загружаем базовые данные
        self._load_core_data()
    
    def _load_core_data(self):
        """Загрузка базового набора сущностей (ядро системы)"""
        # Базовые клеточные линии
        core_cells = [
            self._create_cho_k1(),
            self._create_e_coli(),
            self._create_hela(),
            self._create_yeast()
        ]
        
        for cell in core_cells:
            self.add_entity(cell, source="system")

    # ---------- ДОБАВЛЕНО: системные сущности ядра ----------

    def _create_cho_k1(self) -> 'CellLine':
        """
        Базовая линия CHO-K1 для ядра базы знаний.

        Это системная линия, которая всегда доступна как стартовый объект
        для симуляций; по сути дублирует профиль из create_standard_cell_lines().
        """
        return CellLine(
            id="cho_k1",
            name="CHO-K1",
            entity_type=EntityType.CELL_LINE,
            categories=["mammalian", "adherent", "bioproduction"],
            properties={
                "doubling_time": 20.0,
                "optimal_temperature": 37.0,
                "optimal_ph": 7.1,
                "max_density": 7e6,
                "glucose_consumption": 0.3,
                "oxygen_consumption": 0.02,
                "lactate_production": 0.18,
                "viability_threshold": 0.8,
                "apoptosis_threshold": 0.3,
                "temperature_range": (36.5, 37.5),
                "ph_range": (6.9, 7.3)
            }
        )

    def _create_e_coli(self) -> 'CellLine':
        """
        Базовая бактериальная культура E. coli для ядра.
        """
        return CellLine(
            id="e_coli",
            name="Escherichia coli DH5α",
            entity_type=EntityType.CELL_LINE,
            categories=["bacterial", "suspension", "cloning_host"],
            properties={
                "doubling_time": 0.5,  # 30 минут
                "optimal_temperature": 37.0,
                "optimal_ph": 7.0,
                "max_density": 2e9,
                "glucose_consumption": 1.0,
                "oxygen_consumption": 0.1,
                "lactate_production": 0.6,
                "antibiotic_resistance": 0.0,
                "temperature_range": (30.0, 42.0),
                "ph_range": (6.5, 7.5)
            }
        )

    def _create_hela(self) -> 'CellLine':
        """
        Базовая линия HeLa для ядра.
        """
        return CellLine(
            id="hela",
            name="HeLa",
            entity_type=EntityType.CELL_LINE,
            categories=["mammalian", "adherent", "cancer", "research"],
            properties={
                "doubling_time": 24.0,
                "optimal_temperature": 37.0,
                "optimal_ph": 7.2,
                "max_density": 5e6,
                "glucose_consumption": 0.4,
                "oxygen_consumption": 0.03,
                "lactate_production": 0.25,  # Эффект Варбурга
                "viability_threshold": 0.7,
                "apoptosis_resistance": 0.5,
                "temperature_range": (36.0, 38.0),
                "ph_range": (6.8, 7.4)
            }
        )

    def _create_yeast(self) -> 'CellLine':
        """
        Базовая дрожжевая культура Saccharomyces cerevisiae для ядра.
        (Её не было в create_standard_cell_lines, поэтому задаём разумный профиль.)
        """
        return CellLine(
            id="yeast",
            name="Saccharomyces cerevisiae",
            entity_type=EntityType.CELL_LINE,
            categories=["yeast", "eukaryote", "suspension", "research"],
            properties={
                "doubling_time": 1.5,  # ~1,5 часа
                "optimal_temperature": 30.0,
                "optimal_ph": 5.5,
                "max_density": 1e8,
                "glucose_consumption": 0.5,
                "oxygen_consumption": 0.05,
                "lactate_production": 0.1,
                "viability_threshold": 0.8,
                "apoptosis_threshold": 0.4,
                "temperature_range": (25.0, 34.0),
                "ph_range": (4.5, 6.0)
            }
        )
    
    # --------------------------------------------------------

    def add_entity(self, entity: 'BioEntity', source: str = "user") -> str:
        """Добавление новой сущности в базу знаний"""
        # Проверка на дубликаты
        if entity.id in self.entities:
            # Версионирование: создаем новую версию
            new_id = f"{entity.id}_v{len(self.version_history) + 1}"
            entity.id = new_id
        
        # Добавляем в хранилище
        self.entities[entity.id] = entity
        
        # Обновляем граф отношений
        self._update_relation_graph(entity)
        
        # Логируем изменение
        self._log_change(
            action="add_entity",
            entity_id=entity.id,
            entity_type=entity.entity_type.value,
            source=source,
            timestamp=datetime.now()
        )
        
        return entity.id
    
    def find_interaction(self, entity_a_id: str, entity_b_id: str) -> Optional['InteractionRule']:
        """Поиск правил взаимодействия между двумя сущностями"""
        # 1. Прямое правило
        direct_key = f"{entity_a_id}__{entity_b_id}"
        if direct_key in self.interactions:
            return self.interactions[direct_key]
        
        # 2. Категориальные правила
        entity_a = self.entities.get(entity_a_id)
        entity_b = self.entities.get(entity_b_id)
        
        if not entity_a or not entity_b:
            return None
        
        # Ищем правила по категориям
        for rule in self.interactions.values():
            if rule.matches_categories(entity_a, entity_b):
                return rule
        
        # 3. Генерируем правило на основе фундаментальных принципов
        return self._generate_fundamental_rule(entity_a, entity_b)
    
    def _generate_fundamental_rule(self, entity_a: 'BioEntity', entity_b: 'BioEntity') -> 'InteractionRule':
        """Генерация правила взаимодействия на основе фундаментальных принципов"""
        interaction_type = self._deduce_interaction_type(entity_a, entity_b)
        rule = InteractionRule(
            rule_id=f"auto_{entity_a.id}_{entity_b.id}",
            entity_a_id=entity_a.id,
            entity_b_id=entity_b.id,
            interaction_type=interaction_type,
            parameters=self._calculate_fundamental_parameters(entity_a, entity_b, interaction_type)
        )
        
        # Помечаем как автоматически сгенерированное
        rule.metadata["auto_generated"] = True
        rule.metadata["confidence"] = 0.7  # Средняя уверенность
        
        return rule
    
    def _deduce_interaction_type(self, a: 'BioEntity', b: 'BioEntity') -> InteractionType:
        """Вывод типа взаимодействия на основе категорий"""
        # Фундаментальные правила
        if "carbon_source" in a.categories and "consumer" in b.categories:
            return InteractionType.CONSUMPTION
        
        if "toxin" in a.categories and "sensitive" in b.categories:
            return InteractionType.TOXICITY
        
        if "virus" in a.categories and "host" in b.categories:
            # Проверка рецепторов
            if hasattr(a, 'required_receptors') and hasattr(b, 'surface_receptors'):
                if any(r in b.surface_receptors for r in a.required_receptors):
                    return InteractionType.INFECTION
        
        # Конкуренция за общие ресурсы
        if hasattr(a, 'required_resources') and hasattr(b, 'required_resources'):
            common_resources = set(a.required_resources) & set(b.required_resources)
            if common_resources:
                return InteractionType.COMPETITION
        
        return InteractionType.NEUTRAL

    # ---------- ДОБАВЛЕНО: параметры для фундаментальных правил ----------

    def _calculate_fundamental_parameters(
        self,
        a: 'BioEntity',
        b: 'BioEntity',
        interaction_type: InteractionType
    ) -> Dict[str, Any]:
        """
        Подбор базовых параметров для авто-сгенерированного InteractionRule.
        Делаем безопасные значения по умолчанию, чтобы не ловить KeyError
        внутри InteractionRule._calculate_basic_effect().
        """
        params: Dict[str, Any] = {}

        if interaction_type == InteractionType.CONSUMPTION:
            # Для CONSUMPTION базовая реализация смотрит на
            # entity_b.properties['consumption_rate'], поэтому
            # здесь можно просто указать "мягкий" эффект.
            params["base_effect"] = -0.1

        elif interaction_type == InteractionType.TOXICITY:
            # Для TOXICITY базовая реализация использует toxicity_potency.
            params["toxicity_potency"] = 0.1
            params["base_effect"] = -0.1

        else:
            # Нейтральные / слабые взаимодействия
            params["base_effect"] = 0.0

        return params

    # ---------------------------------------------------------------------

    def _update_relation_graph(self, entity: 'BioEntity'):
        """Обновление графа отношений при добавлении сущности"""
        self.relation_graph.add_node(entity.id, type=entity.entity_type.value)
        
        # Категории как отдельные узлы
        for cat in entity.categories:
            cat_node = f"category:{cat}"
            self.relation_graph.add_node(cat_node, type="category")
            self.relation_graph.add_edge(entity.id, cat_node, relation="has_category")
    
    def _log_change(self, action: str, entity_id: str, entity_type: str, source: str, timestamp: datetime):
        """Логирование изменения в базе знаний"""
        self.change_log.append({
            "action": action,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "source": source,
            "timestamp": timestamp.isoformat()
        })


# ============================================================================
# 3. МОДЕЛЬ СУЩНОСТЕЙ (БИОЛОГИЧЕСКИЕ ОБЪЕКТЫ)
# ============================================================================

@dataclass
class BioEntity:
    """Базовая модель биологической сущности"""
    id: str
    name: str
    entity_type: EntityType
    categories: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Динамические параметры (могут меняться в ходе симуляции)
    current_state: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Автоматическая генерация ID если не указан
        if not self.id:
            self.id = self._generate_id()
        
        # Инициализация состояния
        self.current_state = {
            "active": True,
            "concentration": 0.0,
            "viability": 1.0,
            "last_updated": datetime.now()
        }
    
    def _generate_id(self) -> str:
        """Генерация уникального ID на основе имени и типа"""
        base = f"{self.entity_type.value}_{self.name}"
        return hashlib.md5(base.encode()).hexdigest()[:8]
    
    def update_state(self, **kwargs):
        """Обновление текущего состояния сущности"""
        self.current_state.update(kwargs)
        self.current_state["last_updated"] = datetime.now()
    
    def to_dict(self) -> Dict:
        """Сериализация в словарь"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.entity_type.value,
            "categories": self.categories,
            "properties": self.properties,
            "metadata": self.metadata,
            "current_state": self.current_state
        }


@dataclass
class CellLine(BioEntity):
    """Модель клеточной линии"""
    
    def __post_init__(self):
        super().__post_init__()
        self.entity_type = EntityType.CELL_LINE
        
        # Устанавливаем свойства по умолчанию для клеточных линий
        default_props = {
            "doubling_time": 24.0,  # часов
            "optimal_temperature": 37.0,
            "optimal_ph": 7.2,
            "max_density": 2e6,  # клеток/мл
            "glucose_consumption": 0.3,  # пмоль/клетка/час
            "oxygen_consumption": 0.02,
            "lactate_production": 0.18,
            "viability_threshold": 0.8,
            "apoptosis_threshold": 0.3
        }
        
        # Объединяем с пользовательскими свойствами
        for key, value in default_props.items():
            if key not in self.properties:
                self.properties[key] = value
        
        # Инициализация популяционных параметров
        self.current_state.update({
            "cell_count": 0,
            "growth_rate": 0.0,
            "stress_level": 0.0,
            "metabolic_activity": 1.0
        })


@dataclass
class Chemical(BioEntity):
    """Модель химического вещества"""
    
    def __post_init__(self):
        super().__post_init__()
        self.entity_type = EntityType.CHEMICAL
        
        # Свойства по умолчанию для химических веществ
        default_props = {
            "molecular_weight": 0.0,
            "solubility": 1.0,
            "diffusion_coefficient": 1e-9,  # m²/s
            "pka": None,
            "toxicity_threshold": 1.0  # мМ
        }
        
        for key, value in default_props.items():
            if key not in self.properties:
                self.properties[key] = value


# ============================================================================
# 4. ПРАВИЛА ВЗАИМОДЕЙСТВИЙ
# ============================================================================

@dataclass
class InteractionRule:
    """Правило взаимодействия между двумя сущностями"""
    rule_id: str
    entity_a_id: str
    entity_b_id: str
    interaction_type: InteractionType
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Динамические параметры для расчета эффектов
    effect_calculator: Optional['EffectCalculator'] = None
    
    def calculate_effect(self, 
                        entity_a: BioEntity, 
                        entity_b: BioEntity,
                        environment: 'Environment',
                        time_step: float = 1.0) -> Dict[str, Any]:
        """Расчет эффекта взаимодействия"""
        if self.effect_calculator:
            return self.effect_calculator.calculate(
                entity_a, entity_b, environment, time_step
            )
        
        # Базовая реализация по умолчанию
        return self._calculate_basic_effect(entity_a, entity_b, time_step)
    
    def _calculate_basic_effect(self, 
                               entity_a: BioEntity, 
                               entity_b: BioEntity,
                               time_step: float) -> Dict[str, Any]:
        """Базовая реализация расчета эффекта"""
        effect = {
            "type": self.interaction_type.value,
            "magnitude": 0.0,
            "entity_a_effect": {},
            "entity_b_effect": {},
            "environment_effect": {}
        }
        
        # Простые правила по типу взаимодействия
        if self.interaction_type == InteractionType.CONSUMPTION:
            if hasattr(entity_b, 'properties') and 'consumption_rate' in entity_b.properties:
                rate = entity_b.properties['consumption_rate']
                amount = rate * entity_b.current_state.get('cell_count', 1) * time_step
                effect['magnitude'] = amount
                effect['entity_a_effect']['concentration_change'] = -amount
                
        elif self.interaction_type == InteractionType.TOXICITY:
            if 'toxicity_potency' in self.parameters:
                potency = self.parameters['toxicity_potency']
                concentration = entity_a.current_state.get('concentration', 0)
                toxicity = potency * concentration * time_step
                effect['magnitude'] = toxicity
                effect['entity_b_effect']['viability_change'] = -toxicity
        
        return effect
    
    def matches_categories(self, entity_a: BioEntity, entity_b: BioEntity) -> bool:
        """Проверка, применимо ли правило на основе категорий"""
        rule_cats_a = self.metadata.get('entity_a_categories', [])
        rule_cats_b = self.metadata.get('entity_b_categories', [])
        
        match_a = not rule_cats_a or any(cat in entity_a.categories for cat in rule_cats_a)
        match_b = not rule_cats_b or any(cat in entity_b.categories for cat in rule_cats_b)
        
        return match_a and match_b


# ============================================================================
# 5. МОДЕЛЬ СРЕДЫ И УСЛОВИЙ
# ============================================================================

@dataclass
class Environment:
    """Модель окружающей среды для культивирования"""
    
    # Основные параметры среды
    temperature: float = 37.0  # °C
    ph: float = 7.2
    ph_base: float = 7.2  # базовая уставка pH
    oxygen: float = 1.0  # доля от насыщения (1.0 = 100% сат.)
    co2: float = 0.05  # %
    osmolality: float = 320.0  # мОсм/кг
    volume: float = 1.0  # мл
    
    # Концентрации веществ
    concentrations: Dict[str, float] = field(default_factory=dict)
    
    # Пространственная модель (2D сетка)
    spatial_grid: Optional[np.ndarray] = None
    grid_size: Tuple[int, int] = (100, 100)
    
    # Градиенты и локальные вариации
    gradients: Dict[str, np.ndarray] = field(default_factory=dict)
    
    def __post_init__(self):
        """Инициализация пространственной модели"""
        if self.spatial_grid is None:
            self.spatial_grid = np.zeros(self.grid_size)
            
        # Инициализация градиентов
        self._initialize_gradients()
    
    def _initialize_gradients(self):
        """Инициализация градиентов параметров"""
        # Градиент температуры (обычно равномерный)
        self.gradients['temperature'] = np.full(self.grid_size, self.temperature)
        
        # Градиент кислорода (может быть неравномерным в глубине)
        self.gradients['oxygen'] = np.full(self.grid_size, self.oxygen)
        
        # Градиент pH (может быть локально изменен метаболизмом)
        self.gradients['ph'] = np.full(self.grid_size, self.ph)
    
    def update_concentration(self, substance_id: str, delta: float):
        """Обновление концентрации вещества в среде"""
        current = self.concentrations.get(substance_id, 0.0)
        new_concentration = max(0.0, current + delta)
        self.concentrations[substance_id] = new_concentration
    
    def get_local_conditions(self, x: int, y: int) -> Dict[str, float]:
        """Получение локальных условий в точке (x, y)"""
        return {
            'temperature': self.gradients['temperature'][x, y],
            'ph': self.gradients['ph'][x, y],
            'oxygen': self.gradients['oxygen'][x, y]
        }
    
    def apply_diffusion(self, substance_id: str, diffusion_coeff: float, dt: float):
        """Применение диффузии вещества в среде"""
        # TODO: Реализовать реальную диффузию на сетке
        # Пока просто равномерное распределение
        if substance_id in self.concentrations:
            # Упрощенная модель: выравнивание концентрации
            pass


# ============================================================================
# 6. МОДЕЛЬ КУЛЬТУРЫ И БИОРЕАКТОРА
# ============================================================================

class CultureVessel:
    """Модель культурального сосуда (чашка Петри, флакон, биореактор)"""
    
    def __init__(self, 
                 vessel_id: str,
                 volume: float = 10.0,
                 environment: Optional[Environment] = None,
                 knowledge_base: Optional[KnowledgeBase] = None):
        
        self.vessel_id = vessel_id
        self.volume = volume
        
        # Среда культивирования
        self.environment = environment or Environment(volume=volume)
        
        # База знаний для поиска правил
        self.knowledge_base = knowledge_base or KnowledgeBase()
        
        # Популяции клеток в сосуде
        self.cell_populations: Dict[str, 'CellPopulation'] = {}
        
        # История изменений
        self.history: List[Dict] = []
        self.time_elapsed: float = 0.0  # часов
        
        # Мониторинг и сенсоры
        self.sensors = {
            'temperature': self.environment.temperature,
            'ph': self.environment.ph,
            'oxygen': self.environment.oxygen,
            'biomass': 0.0
        }

        # Управление газообменом/мешалкой (подаётся из UI через workspace_app)
        self.stirring_rpm: float = 0.0
        self.aeration_lpm: float = 0.0
        # доли газа на входе (0..1). По умолчанию воздух.
        self.inlet_gases: Dict[str, float] = {"O2": 0.21, "CO2": 0.0004, "N2": 0.7896}
        # коэффициенты массопереноса (упрощённо)
        self._kla_o2_base: float = 0.20   # 1/ч
        self._kla_co2_base: float = 0.25  # 1/ч

    

    def set_controls(self,
                     stirring_rpm: Optional[float] = None,
                     aeration_lpm: Optional[float] = None,
                     inlet_gases: Optional[Dict[str, float]] = None):
        """Применить уставки управления во время эксперимента."""
        if stirring_rpm is not None:
            try:
                self.stirring_rpm = max(0.0, float(stirring_rpm))
            except Exception:
                pass
        if aeration_lpm is not None:
            try:
                self.aeration_lpm = max(0.0, float(aeration_lpm))
            except Exception:
                pass
        if inlet_gases is not None and isinstance(inlet_gases, dict):
            # нормализуем в доли 0..1
            norm = {}
            for k, v in inlet_gases.items():
                kk = str(k).strip()
                try:
                    vv = float(v)
                except Exception:
                    continue
                # если пришло в процентах (0..100) — переводим
                if vv > 1.5:
                    vv = vv / 100.0
                norm[kk] = max(0.0, min(1.0, vv))
            if norm:
                # если не задан N2 — досчитаем остаток
                if "N2" not in norm:
                    rest = 1.0 - sum([norm.get("O2", 0.0), norm.get("CO2", 0.0)])
                    norm["N2"] = max(0.0, rest)
                self.inlet_gases = norm
    def add_culture(self, 
                   cell_line: CellLine, 
                   cell_count: float,
                   volume_added: float = 1.0,
                   concentration: Optional[float] = None) -> str:
        """Добавление культуры в сосуд"""
        
        # Расчет начальной концентрации
        if concentration is None:
            concentration = cell_count / volume_added
        
        # Создание популяции
        population_id = f"{cell_line.id}_{len(self.cell_populations)}"
        population = CellPopulation(
            population_id=population_id,
            cell_line=cell_line,
            initial_count=cell_count,
            concentration=concentration
        )
        
        # Добавление в сосуд
        self.cell_populations[population_id] = population
        
        # Обновление объема
        self.volume += volume_added
        self.environment.volume = self.volume
        
        # Логирование
        self._log_event({
            'time': self.time_elapsed,
            'event': 'add_culture',
            'population_id': population_id,
            'cell_line': cell_line.id,
            'cell_count': cell_count,
            'volume_added': volume_added
        })
        
        return population_id
    
    def add_substance(self, 
                     substance: Chemical, 
                     concentration: float,
                     volume_added: float = 0.1):
        """Добавление вещества в сосуд"""
        
        # Расчет количества вещества
        amount = concentration * volume_added
        
        # Обновление концентрации в среде
        self.environment.update_concentration(substance.id, amount)
        
        # Обновление объема
        self.volume += volume_added
        self.environment.volume = self.volume
        
        # Логирование
        self._log_event({
            'time': self.time_elapsed,
            'event': 'add_substance',
            'substance_id': substance.id,
            'concentration': concentration,
            'amount': amount,
            'volume_added': volume_added
        })
    
    def simulate_step(self, time_step: float = 1.0):
        """Выполнение одного шага симуляции"""
        
        # Обновление времени
        self.time_elapsed += time_step
        
        # 1. Обновление среды
        self._update_environment(time_step)
        
        # 2. Обновление всех популяций
        for pop_id, population in self.cell_populations.items():
            self._update_population(population, time_step)
        
        # 3. Взаимодействия между популяциями
        self._calculate_interactions(time_step)
        
        # 4. Обновление сенсоров
        self._update_sensors()
        
        # 5. Логирование состояния
        self._log_state()
    
    def _update_population(self, population: 'CellPopulation', time_step: float):
        """Обновление состояния популяции клеток"""
        
        # Расчет условий для роста
        growth_factor = self._calculate_growth_factor(population)
        
        # Расчет стресса
        stress_factor = self._calculate_stress_factor(population)
        
        # Обновление популяции
        population.update(
            time_step=time_step,
            growth_factor=growth_factor,
            stress_factor=stress_factor,
            environment=self.environment
        )
    
    def _calculate_growth_factor(self, population: 'CellPopulation') -> float:
        """Расчет фактора роста на основе условий среды"""
        
        cell_line = population.cell_line
        growth_factor = 1.0
        
        # Влияние температуры
        opt_temp = cell_line.properties.get('optimal_temperature', 37.0)
        temp_diff = abs(self.environment.temperature - opt_temp)
        temp_factor = max(0, 1.0 - (temp_diff / 5.0) ** 2)
        growth_factor *= temp_factor
        
        # Влияние pH
        opt_ph = cell_line.properties.get('optimal_ph', 7.2)
        ph_diff = abs(self.environment.ph - opt_ph)
        ph_factor = max(0, 1.0 - (ph_diff / 0.5) ** 2)
        growth_factor *= ph_factor
        
        
        # Влияние кислорода (ограничение по DO)
        # environment.oxygen = доля насыщения (0..1). Km ~ 0.2 (20% сат.)
        o2 = max(0.0, float(getattr(self.environment, 'oxygen', 0.0)))
        o2_km = float(cell_line.properties.get('oxygen_km', 0.20))
        o2_factor = o2 / (o2 + max(1e-9, o2_km))
        growth_factor *= o2_factor

        # Влияние CO2 (отклонение от оптимума)
        co2 = max(0.0, float(getattr(self.environment, 'co2', 0.0)))
        opt_co2 = float(cell_line.properties.get('optimal_co2', 0.05))
        co2_diff = abs(co2 - opt_co2)
        co2_factor = max(0.0, 1.0 - (co2_diff / 0.03) ** 2)  # 3% ширина окна
        growth_factor *= co2_factor

        # Влияние питательных веществ
        glucose = self.environment.concentrations.get('glucose', 0.0)
        glucose_km = cell_line.properties.get('glucose_km', 1.0)
        glucose_factor = glucose / (glucose + glucose_km)
        growth_factor *= glucose_factor
        
        # Влияние плотности (контактное ингибирование)
        density = population.concentration
        max_density = cell_line.properties.get('max_density', 2e6)
        density_factor = max(0, 1.0 - (density / max_density) ** 2)
        growth_factor *= density_factor
        
        return max(0, min(1.0, growth_factor))
    
    def _calculate_stress_factor(self, population: 'CellPopulation') -> float:
        """Расчет уровня стресса"""
        
        stress = 0.0
        
        # Стресс от температуры
        opt_temp = population.cell_line.properties.get('optimal_temperature', 37.0)
        temp_stress = abs(self.environment.temperature - opt_temp) / 5.0
        stress += temp_stress
        
        # Стресс от pH
        opt_ph = population.cell_line.properties.get('optimal_ph', 7.2)
        ph_stress = abs(self.environment.ph - opt_ph) / 0.5
        stress += ph_stress
        
        
        # Стресс от кислорода (гипоксия)
        o2 = max(0.0, float(getattr(self.environment, 'oxygen', 0.0)))
        # если ниже 30% сат. — стресс растёт
        if o2 < 0.30:
            stress += (0.30 - o2) / 0.30

        # Стресс от CO2 (отклонение от оптимума)
        co2 = max(0.0, float(getattr(self.environment, 'co2', 0.0)))
        opt_co2 = float(population.cell_line.properties.get('optimal_co2', 0.05))
        stress += abs(co2 - opt_co2) / 0.05

        # Стресс от метаболитов
        lactate = self.environment.concentrations.get('lactate', 0.0)
        lactate_stress = lactate / 20.0  # порог ~20 мМ
        stress += lactate_stress
        
        # Стресс от токсинов
        for substance_id, conc in self.environment.concentrations.items():
            if 'toxin' in substance_id or 'antibiotic' in substance_id:
                # TODO: Учитывать специфическую токсичность
                stress += conc / 10.0
        
        return min(1.0, stress / 4.0)  # Нормализация
    
    def _calculate_interactions(self, time_step: float):
        """Расчет взаимодействий между всеми сущностями"""
        
        all_entities = list(self.cell_populations.values())
        
        # Добавляем химические вещества как сущности
        for substance_id, conc in self.environment.concentrations.items():
            if conc > 0 and substance_id in self.knowledge_base.entities:
                substance = self.knowledge_base.entities[substance_id]
                # Клонируем с текущей концентрацией
                substance.current_state['concentration'] = conc
                all_entities.append(substance)
        
        # Парные взаимодействия
        for i, entity_a in enumerate(all_entities):
            for j, entity_b in enumerate(all_entities[i+1:], i+1):
                
                # Поиск правила взаимодействия
                rule = self.knowledge_base.find_interaction(
                    entity_a.id, 
                    entity_b.id
                )
                
                if rule and rule.interaction_type != InteractionType.NEUTRAL:
                    # Расчет эффекта
                    effect = rule.calculate_effect(
                        entity_a, entity_b, self.environment, time_step
                    )
                    
                    # Применение эффекта
                    self._apply_interaction_effect(effect, entity_a, entity_b)
    
    def _apply_interaction_effect(self, 
                                 effect: Dict, 
                                 entity_a, 
                                 entity_b):
        """Применение эффекта взаимодействия"""
        
        # Эффект на entity_a
        if 'entity_a_effect' in effect:
            for param, change in effect['entity_a_effect'].items():
                if hasattr(entity_a, 'current_state'):
                    current = entity_a.current_state.get(param, 0)
                    entity_a.current_state[param] = current + change
        
        # Эффект на entity_b
        if 'entity_b_effect' in effect:
            for param, change in effect['entity_b_effect'].items():
                if hasattr(entity_b, 'current_state'):
                    current = entity_b.current_state.get(param, 0)
                    entity_b.current_state[param] = current + change
        
        # Эффект на среду
        if 'environment_effect' in effect:
            for substance_id, change in effect['environment_effect'].items():
                self.environment.update_concentration(substance_id, change)
    
    def _update_environment(self, time_step: float):

        """Обновление параметров среды"""

        # Суммарное потребление кислорода (OUR) и продукция CO2 — пропорционально биомассе
        total_o2_consumption = 0.0
        for population in self.cell_populations.values():
            cell_line = population.cell_line
            # условная скорость потребления O2 (доля насыщения/ч на 1 клетку в мл)
            o2_rate = float(cell_line.properties.get('oxygen_consumption', 2.0e-10))
            total_o2_consumption += float(population.cell_count) * o2_rate * float(time_step)

        # Упрощённый массоперенос (OTR) от аэрации/перемешивания
        # kLa растёт с RPM и L/min. Это не физическая модель, но даёт корректное поведение управления.
        kla_o2 = float(getattr(self, "_kla_o2_base", 0.20))
        try:
            kla_o2 = kla_o2 + 0.0006 * float(getattr(self, "stirring_rpm", 0.0)) + 0.18 * float(getattr(self, "aeration_lpm", 0.0))
        except Exception:
            pass
        kla_o2 = max(0.0, kla_o2)

        # Цель насыщения зависит от доли O2 во входном газе (воздух=0.21 -> 100% сат.)
        inlet_o2 = 0.21
        try:
            inlet_o2 = float((getattr(self, "inlet_gases", {}) or {}).get("O2", 0.21))
        except Exception:
            inlet_o2 = 0.21
        if inlet_o2 > 1.5:
            inlet_o2 = inlet_o2 / 100.0
        inlet_o2 = max(0.0, min(1.0, inlet_o2))
        o2_sat = max(0.0, min(1.5, inlet_o2 / 0.21 if 0.21 > 0 else 1.0))

        # Потребление O2 (снижение сат.) — масштабируем на объём
        try:
            o2_change_cons = - total_o2_consumption / max(1e-9, float(self.volume))
        except Exception:
            o2_change_cons = 0.0

        # Массоперенос тянет oxygen к o2_sat
        o2_change_transfer = kla_o2 * (o2_sat - float(self.environment.oxygen)) * float(time_step)

        self.environment.oxygen = max(0.0, min(1.5, float(self.environment.oxygen) + o2_change_cons + o2_change_transfer))

        # CO2: продукция пропорционально OUR (RQ ~0.8)
        co2_prod = max(0.0, total_o2_consumption) * 0.8

        # Газообмен CO2 (стремится к доле CO2 во входном газе)
        kla_co2 = float(getattr(self, "_kla_co2_base", 0.25))
        try:
            kla_co2 = kla_co2 + 0.0004 * float(getattr(self, "stirring_rpm", 0.0)) + 0.22 * float(getattr(self, "aeration_lpm", 0.0))
        except Exception:
            pass
        kla_co2 = max(0.0, kla_co2)

        inlet_co2 = 0.0004
        try:
            inlet_co2 = float((getattr(self, "inlet_gases", {}) or {}).get("CO2", inlet_co2))
        except Exception:
            inlet_co2 = 0.0004
        if inlet_co2 > 1.5:
            inlet_co2 = inlet_co2 / 100.0
        inlet_co2 = max(0.0, min(1.0, inlet_co2))

        try:
            co2_change_prod = co2_prod / max(1e-9, float(self.volume))
        except Exception:
            co2_change_prod = 0.0

        co2_change_transfer = kla_co2 * (inlet_co2 - float(self.environment.co2)) * float(time_step)
        self.environment.co2 = max(0.0, min(1.0, float(self.environment.co2) + co2_change_prod + co2_change_transfer))

        # Продукция лактата
        total_lactate = 0.0
        for population in self.cell_populations.values():
            cell_line = population.cell_line
            lactate_rate = cell_line.properties.get('lactate_production', 0.18)
            total_lactate += population.cell_count * lactate_rate * time_step
        
        # Обновление лактата и pH
        lactate_change = total_lactate / self.volume
        self.environment.update_concentration('lactate', lactate_change)
        
        # pH: базовая уставка + влияние лактата и CO2 (упрощённо, без накопления ошибки по шагам)
        lactate_conc = float(self.environment.concentrations.get('lactate', 0.0) or 0.0)
        ph_base = float(getattr(self.environment, 'ph_base', self.environment.ph))
        # лактат понижает pH
        ph_from_lactate = -0.03 * lactate_conc
        # CO2 понижает pH относительно уставки CO2 (входной газ)
        inlet_co2 = 0.0004
        try:
            inlet_co2 = float((getattr(self, 'inlet_gases', {}) or {}).get('CO2', inlet_co2))
        except Exception:
            inlet_co2 = 0.0004
        if inlet_co2 > 1.5:
            inlet_co2 = inlet_co2 / 100.0
        inlet_co2 = max(0.0, min(1.0, inlet_co2))
        co2_delta = float(self.environment.co2) - inlet_co2
        ph_from_co2 = -2.5 * co2_delta
        self.environment.ph = max(6.3, min(8.0, ph_base + ph_from_lactate + ph_from_co2))
    
    def _update_sensors(self):
        """Обновление показаний сенсоров"""
        self.sensors.update({
            'temperature': self.environment.temperature,
            'ph': self.environment.ph,
            'oxygen': self.environment.oxygen,
            'biomass': sum(p.cell_count for p in self.cell_populations.values())
        })
    
    def _log_event(self, event_data: Dict):
        """Логирование события"""
        self.history.append(event_data)
    
    def _log_state(self):
        """Логирование текущего состояния"""
        state = {
            'time': self.time_elapsed,
            'event': 'state_update',
            'populations': {
                pid: {
                    'cell_count': pop.cell_count,
                    'viability': pop.viability,
                    'growth_rate': pop.growth_rate
                }
                for pid, pop in self.cell_populations.items()
            },
            'environment': {
                'temperature': self.environment.temperature,
                'ph': self.environment.ph,
                'oxygen': self.environment.oxygen,
                'concentrations': self.environment.concentrations.copy()
            },
            'sensors': self.sensors.copy()
        }
        self.history.append(state)


# ============================================================================
# 7. МОДЕЛЬ ПОПУЛЯЦИИ КЛЕТОК
# ============================================================================

@dataclass
class CellPopulation:
    """Модель популяции клеток одного типа"""
    
    population_id: str
    cell_line: CellLine
    initial_count: float
    concentration: float
    
    # Текущее состояние
    cell_count: float = 0.0
    viability: float = 1.0
    growth_rate: float = 0.0
    stress_level: float = 0.0
    metabolic_activity: float = 1.0
    
    # История
    growth_history: List[Tuple[float, float]] = field(default_factory=list)
    
    def __post_init__(self):
        self.cell_count = self.initial_count
    
    def update(self, 
               time_step: float,
               growth_factor: float,
               stress_factor: float,
               environment: Environment):
        """Обновление состояния популяции"""
        
        # Базовый рост
        doubling_time = self.cell_line.properties.get('doubling_time', 24.0)
        base_growth_rate = np.log(2) / doubling_time  # 1/час
        
        # Коррекция роста на основе условий
        effective_growth_rate = base_growth_rate * growth_factor
        
        # Коррекция на стресс
        stress_penalty = 1.0 - stress_factor
        effective_growth_rate *= stress_penalty
        
        # Расчет нового количества клеток
        new_count = self.cell_count * np.exp(effective_growth_rate * time_step)
        
        # Учет гибели клеток от стресса
        death_rate = stress_factor * 0.1  # 10% максимальная смертность
        survival_fraction = np.exp(-death_rate * time_step)
        
        # Итоговое количество
        self.cell_count = new_count * survival_fraction
        self.growth_rate = effective_growth_rate
        self.stress_level = stress_factor
        
        # Обновление жизнеспособности
        viability_threshold = self.cell_line.properties.get('viability_threshold', 0.8)
        apoptosis_threshold = self.cell_line.properties.get('apoptosis_threshold', 0.3)
        
        if stress_factor > apoptosis_threshold:
            # Ускоренная гибель
            self.viability *= (1.0 - stress_factor * 0.1)
        elif stress_factor > viability_threshold:
            # Снижение жизнеспособности
            self.viability *= (1.0 - stress_factor * 0.05)
        else:
            # Восстановление
            self.viability = min(1.0, self.viability * (1.0 + 0.01))
        
        # Потребление ресурсов
        self._consume_resources(time_step, environment)
        
        # Запись в историю
        self.growth_history.append((time_step, self.cell_count))
    
    def _consume_resources(self, time_step: float, environment: Environment):
        """Потребление ресурсов из среды"""
        
        # Потребление глюкозы
        glucose_rate = self.cell_line.properties.get('glucose_consumption', 0.3)
        cells_mln = float(self.cell_count) / 1000000.0
        glucose_needed = cells_mln * glucose_rate * time_step
        
        # Доступная глюкоза
        glucose_available = environment.concentrations.get('glucose', 0.0) * environment.volume
        
        # Фактическое потребление (лимитировано доступностью)
        glucose_consumed = min(glucose_needed, glucose_available)
        
        # Обновление концентрации
        environment.update_concentration('glucose', -glucose_consumed / environment.volume)
        
        # Продукция лактата (метаболизм)
        lactate_yield = self.cell_line.properties.get('lactate_production', 0.18)
        lactate_produced = glucose_consumed * lactate_yield
        
        environment.update_concentration('lactate', lactate_produced / environment.volume)
        
        # Влияние на метаболическую активность
        if glucose_consumed < glucose_needed * 0.5:
            self.metabolic_activity *= 0.9  # Снижение при нехватке глюкозы


# ============================================================================
# 8. СИСТЕМА ЭФФЕКТОВ И РАСЧЕТОВ
# ============================================================================

class EffectCalculator(ABC):
    """Абстрактный класс для расчета эффектов"""
    
    @abstractmethod
    def calculate(self, 
                 entity_a: BioEntity,
                 entity_b: BioEntity,
                 environment: Environment,
                 time_step: float) -> Dict[str, Any]:
        pass


class ToxicityEffectCalculator(EffectCalculator):
    """Калькулятор токсических эффектов"""
    
    def calculate(self, entity_a, entity_b, environment, time_step):
        # entity_a - токсин, entity_b - клетка
        
        concentration = entity_a.current_state.get('concentration', 0)
        potency = entity_a.properties.get('toxicity_potency', 1.0)
        
        # IC50 модели
        ic50 = entity_a.properties.get('ic50', 1.0)
        
        # Расчет эффекта по формуле Хилла
        hill_coeff = entity_a.properties.get('hill_coefficient', 1.0)
        effect = (concentration ** hill_coeff) / (ic50 ** hill_coeff + concentration ** hill_coeff)
        
        return {
            'type': 'toxicity',
            'magnitude': effect * potency,
            'entity_b_effect': {
                'viability_change': -effect * potency * time_step
            }
        }


class AntibioticEffectCalculator(EffectCalculator):
    """Калькулятор эффектов антибиотиков"""
    
    def calculate(self, entity_a, entity_b, environment, time_step):
        # entity_a - антибиотик, entity_b - бактерия
        
        concentration = entity_a.current_state.get('concentration', 0)
        
        # Проверка резистентности
        resistance = entity_b.properties.get('antibiotic_resistance', 0.0)
        effective_concentration = concentration * (1.0 - resistance)
        
        # MIC модели
        mic = entity_a.properties.get('mic', 1.0)
        
        if effective_concentration < mic:
            # Суб-ингибирующая концентрация
            effect = 0.1 * (effective_concentration / mic)
        else:
            # Бактерицидный эффект
            effect = 1.0 - np.exp(-effective_concentration / mic * time_step)
        
        return {
            'type': 'antibiotic',
            'magnitude': effect,
            'entity_b_effect': {
                'growth_rate_change': -effect,
                'viability_change': -effect * 0.5 * time_step
            }
        }


# ============================================================================
# 9. МЕНЕДЖЕР ЭКСПЕРИМЕНТОВ И ПРОТОКОЛОВ
# ============================================================================

class ExperimentManager:
    """Управление экспериментами и протоколами"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        self.knowledge_base = knowledge_base
        self.active_experiments: Dict[str, 'Experiment'] = {}
        self.experiment_templates: Dict[str, Dict] = {}
        
        # Загрузка стандартных протоколов
        self._load_standard_protocols()
    
    def create_experiment(self, 
                         template_name: str,
                         experiment_id: str = None) -> 'Experiment':
        """Создание эксперимента из шаблона"""
        
        if template_name not in self.experiment_templates:
            raise ValueError(f"Шаблон {template_name} не найден")
        
        template = self.experiment_templates[template_name]
        
        # Создание эксперимента
        if experiment_id is None:
            experiment_id = f"exp_{len(self.active_experiments)}"
        
        experiment = Experiment(
            experiment_id=experiment_id,
            name=template['name'],
            description=template['description'],
            protocol_steps=template['steps'].copy()
        )
        
        self.active_experiments[experiment_id] = experiment
        return experiment
    
    def add_custom_protocol(self, 
                           name: str,
                           steps: List[Dict],
                           description: str = ""):
        """Добавление пользовательского протокола"""
        
        self.experiment_templates[name] = {
            'name': name,
            'description': description,
            'steps': steps
        }
    
    def _load_standard_protocols(self):
        """Загрузка стандартных протоколов"""
        
        # Протокол тестирования антибиотиков
        self.experiment_templates['antibiotic_test'] = {
            'name': 'Тестирование антибиотиков',
            'description': 'Оценка эффективности антибиотиков против бактериальной культуры',
            'steps': [
                {
                    'action': 'add_culture',
                    'parameters': {
                        'cell_line': 'e_coli',
                        'cell_count': 1e6,
                        'volume': 1.0
                    },
                    'duration': 2.0
                },
                {
                    'action': 'add_substance',
                    'parameters': {
                        'substance': 'ampicillin',
                        'concentration': 10.0,  # мкг/мл
                        'volume': 0.1
                    },
                    'duration': 0.1
                },
                {
                    'action': 'monitor',
                    'parameters': {
                        'duration': 24.0,
                        'measurements': ['cell_count', 'viability'],
                        'interval': 1.0
                    }
                }
            ]
        }
        
        # Протокол кривых роста
        self.experiment_templates['growth_curve'] = {
            'name': 'Кривая роста клеток',
            'description': 'Определение времени удвоения и максимальной плотности',
            'steps': [
                {
                    'action': 'add_culture',
                    'parameters': {
                        'cell_line': 'cho_k1',
                        'cell_count': 1e5,
                        'volume': 10.0
                    },
                    'duration': 1.0
                },
                {
                    'action': 'monitor',
                    'parameters': {
                        'duration': 120.0,
                        'measurements': ['cell_count', 'ph', 'glucose'],
                        'interval': 2.0
                    }
                }
            ]
        }


@dataclass
class Experiment:
    """Модель эксперимента"""
    
    experiment_id: str
    name: str
    description: str
    protocol_steps: List[Dict]
    
    current_step: int = 0
    is_running: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    results: Dict[str, Any] = field(default_factory=dict)
    vessels: Dict[str, CultureVessel] = field(default_factory=dict)
    
    def start(self):
        """Запуск эксперимента"""
        self.is_running = True
        self.start_time = datetime.now()
        self.current_step = 0
    
    def execute_step(self, knowledge_base: KnowledgeBase):
        """Выполнение текущего шага протокола"""
        
        if not self.is_running or self.current_step >= len(self.protocol_steps):
            self.is_running = False
            self.end_time = datetime.now()
            return
        
        step = self.protocol_steps[self.current_step]
        action = step['action']
        
        if action == 'add_culture':
            self._execute_add_culture(step['parameters'], knowledge_base)
        
        elif action == 'add_substance':
            self._execute_add_substance(step['parameters'], knowledge_base)
        
        elif action == 'monitor':
            self._execute_monitor(step['parameters'])
        
        elif action == 'change_conditions':
            self._execute_change_conditions(step['parameters'])
        
        self.current_step += 1
    
    def _execute_add_culture(self, params: Dict, kb: KnowledgeBase):
        """Добавление культуры в эксперимент"""
        
        # Получение клеточной линии из базы знаний
        cell_line_id = params.get('cell_line')
        if cell_line_id not in kb.entities:
            raise ValueError(f"Клеточная линия {cell_line_id} не найдена")
        
        cell_line = kb.entities[cell_line_id]
        
        # Создание или выбор сосуда
        vessel_id = params.get('vessel_id', 'vessel_0')
        if vessel_id not in self.vessels:
            self.vessels[vessel_id] = CultureVessel(
                vessel_id=vessel_id,
                volume=params.get('volume', 10.0),
                knowledge_base=kb
            )
        
        vessel = self.vessels[vessel_id]
        
        # Добавление культуры
        vessel.add_culture(
            cell_line=cell_line,
            cell_count=params.get('cell_count', 1e5),
            volume_added=params.get('volume_added', 1.0)
        )
    
    def _execute_add_substance(self, params: Dict, kb: KnowledgeBase):
        """Добавление вещества в эксперимент"""
        
        substance_id = params.get('substance')
        if substance_id not in kb.entities:
            raise ValueError(f"Вещество {substance_id} не найдено")
        
        substance = kb.entities[substance_id]
        
        # Добавление во все сосуды или указанный
        vessel_id = params.get('vessel_id')
        if vessel_id:
            vessels = [self.vessels[vessel_id]]
        else:
            vessels = self.vessels.values()
        
        for vessel in vessels:
            vessel.add_substance(
                substance=substance,
                concentration=params.get('concentration', 1.0),
                volume_added=params.get('volume_added', 0.1)
            )
    
    def _execute_monitor(self, params: Dict):
        """Мониторинг состояния сосудов"""
        
        duration = params.get('duration', 24.0)
        interval = params.get('interval', 1.0)
        measurements = params.get('measurements', ['cell_count'])
        
        time_passed = 0
        while time_passed < duration:
            for vessel in self.vessels.values():
                vessel.simulate_step(time_step=interval)
            
            # Сбор данных
            for vessel in self.vessels.values():
                self._collect_measurements(vessel, measurements)
            
            time_passed += interval
    
    def _execute_change_conditions(self, params: Dict):
        """Изменение условий (пока заглушка)"""
        # В дальнейшем сюда можно добавить шаги изменения среды
        pass
    
    def _collect_measurements(self, vessel: CultureVessel, measurements: List[str]):
        """Сбор измерений из сосуда"""
        
        vessel_id = vessel.vessel_id
        if vessel_id not in self.results:
            self.results[vessel_id] = {}
        
        for measurement in measurements:
            if measurement == 'cell_count':
                data = {pid: pop.cell_count for pid, pop in vessel.cell_populations.items()}
            elif measurement == 'viability':
                data = {pid: pop.viability for pid, pop in vessel.cell_populations.items()}
            elif measurement == 'ph':
                data = vessel.environment.ph
            elif measurement == 'temperature':
                data = vessel.environment.temperature
            elif measurement == 'glucose':
                data = vessel.environment.concentrations.get('glucose', 0.0)
            else:
                data = None
            
            if measurement not in self.results[vessel_id]:
                self.results[vessel_id][measurement] = []
            
            self.results[vessel_id][measurement].append({
                'time': vessel.time_elapsed,
                'value': data
            })


# ============================================================================
# 10. ИНТЕРФЕЙС И СИСТЕМА УПРАВЛЕНИЯ
# ============================================================================

class BioSimApp:
    """
    Главный класс приложения - точка входа для всего симулятора
    """
    
    def __init__(self):
        # Инициализация компонентов
        self.knowledge_base = KnowledgeBase()
        self.experiment_manager = ExperimentManager(self.knowledge_base)
        
        # Активные эксперименты
        self.active_experiments: Dict[str, Experiment] = {}
        
        # Пользовательские данные
        self.user_profiles: Dict[str, Dict] = {}
        self.user_settings: Dict[str, Any] = {
            'auto_save': True,
            'default_time_step': 1.0,
            'visualization_quality': 'high',
            'data_retention_days': 30
        }
        
        # Система уведомлений
        self.notifications: List[Dict] = []
        
        # История действий
        self.activity_log: List[Dict] = []
    
    def create_experiment(self, 
                         template_name: str,
                         custom_name: str = None) -> str:
        """Создание нового эксперимента"""
        
        experiment = self.experiment_manager.create_experiment(template_name)
        
        if custom_name:
            experiment.name = custom_name
        
        self.active_experiments[experiment.experiment_id] = experiment
        
        # Логирование
        self._log_activity(
            action='create_experiment',
            experiment_id=experiment.experiment_id,
            template=template_name
        )
        
        return experiment.experiment_id
    
    def run_experiment(self, experiment_id: str):
        """Запуск эксперимента"""
        
        if experiment_id not in self.active_experiments:
            raise ValueError(f"Эксперимент {experiment_id} не найден")
        
        experiment = self.active_experiments[experiment_id]
        experiment.start()
        
        # Выполнение шагов протокола
        while experiment.is_running:
            experiment.execute_step(self.knowledge_base)
        
        # Анализ результатов
        self._analyze_experiment_results(experiment)
        
        # Уведомление о завершении
        self._add_notification(
            title='Эксперимент завершен',
            message=f'Эксперимент "{experiment.name}" завершен',
            level='info'
        )
    
    def add_entity_to_kb(self, 
                        entity_type: EntityType,
                        name: str,
                        properties: Dict,
                        categories: List[str] = None) -> str:
        """Добавление новой сущности в базу знаний"""
        
        # Создание сущности
        if entity_type == EntityType.CELL_LINE:
            entity = CellLine(
                id=f"custom_{name.lower()}",
                name=name,
                entity_type=entity_type,
                categories=categories or [],
                properties=properties
            )
        elif entity_type == EntityType.CHEMICAL:
            entity = Chemical(
                id=f"custom_{name.lower()}",
                name=name,
                entity_type=entity_type,
                categories=categories or [],
                properties=properties
            )
        else:
            entity = BioEntity(
                id=f"custom_{name.lower()}",
                name=name,
                entity_type=entity_type,
                categories=categories or [],
                properties=properties
            )
        
        # Добавление в базу знаний
        entity_id = self.knowledge_base.add_entity(entity, source="user")
        
        # Логирование
        self._log_activity(
            action='add_entity',
            entity_id=entity_id,
            entity_type=entity_type.value,
            name=name
        )
        
        return entity_id
    
    def get_experiment_results(self, experiment_id: str) -> Dict:
        """Получение результатов эксперимента"""
        
        if experiment_id not in self.active_experiments:
            raise ValueError(f"Эксперимент {experiment_id} не найден")
        
        experiment = self.active_experiments[experiment_id]
        
        # Форматирование результатов для отображения
        formatted_results = {
            'experiment_id': experiment_id,
            'name': experiment.name,
            'duration': experiment.end_time - experiment.start_time if experiment.end_time else None,
            'results': experiment.results,
            'summary': self._generate_summary(experiment)
        }
        
        return formatted_results
    
    def _generate_summary(self, experiment: Experiment) -> Dict:
        """Генерация сводки по эксперименту"""
        
        summary = {
            'total_cells': 0,
            'max_growth_rate': 0,
            'min_viability': 1.0,
            'ph_range': (7.4, 7.4),
            'events': []
        }
        
        for vessel_id, vessel_results in experiment.results.items():
            if 'cell_count' in vessel_results:
                counts = [point['value'] for point in vessel_results['cell_count']]
                if counts:
                    summary['total_cells'] = max(summary['total_cells'], max(counts))
        
        return summary
    
    def _analyze_experiment_results(self, experiment: Experiment):
        """Анализ результатов эксперимента"""
        
        # TODO: Реализовать расширенный анализ
        # - Расчет времени удвоения
        # - Определение IC50
        # - Статистический анализ
        pass
    
    def _log_activity(self, **kwargs):
        """Логирование активности пользователя"""
        
        log_entry = {
            'timestamp': datetime.now(),
            **kwargs
        }
        self.activity_log.append(log_entry)
    
    def _add_notification(self, title: str, message: str, level: str = 'info'):
        """Добавление уведомления"""
        
        self.notifications.append({
            'id': len(self.notifications),
            'title': title,
            'message': message,
            'level': level,
            'timestamp': datetime.now(),
            'read': False
        })


# ============================================================================
# 11. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И УТИЛИТЫ
# ============================================================================

def create_standard_cell_lines() -> Dict[str, CellLine]:
    """Создание стандартных клеточных линий"""
    
    cell_lines = {}
    
    # CHO-K1
    cho_k1 = CellLine(
        id="cho_k1",
        name="CHO-K1",
        entity_type=EntityType.CELL_LINE,
        categories=["mammalian", "adherent", "bioproduction"],
        properties={
            "doubling_time": 20.0,
            "optimal_temperature": 37.0,
            "optimal_ph": 7.1,
            "max_density": 7e6,
            "glucose_consumption": 0.3,
            "oxygen_consumption": 0.02,
            "lactate_production": 0.18,
            "viability_threshold": 0.8,
            "apoptosis_threshold": 0.3,
            "temperature_range": (36.5, 37.5),
            "ph_range": (6.9, 7.3)
        }
    )
    cell_lines["cho_k1"] = cho_k1
    
    # E. coli DH5α
    e_coli = CellLine(
        id="e_coli",
        name="Escherichia coli DH5α",
        entity_type=EntityType.CELL_LINE,
        categories=["bacterial", "suspension", "cloning_host"],
        properties={
            "doubling_time": 0.5,  # 30 минут
            "optimal_temperature": 37.0,
            "optimal_ph": 7.0,
            "max_density": 2e9,
            "glucose_consumption": 1.0,
            "oxygen_consumption": 0.1,
            "lactate_production": 0.6,
            "antibiotic_resistance": 0.0,
            "temperature_range": (30.0, 42.0),
            "ph_range": (6.5, 7.5)
        }
    )
    cell_lines["e_coli"] = e_coli
    
    # HeLa
    hela = CellLine(
        id="hela",
        name="HeLa",
        entity_type=EntityType.CELL_LINE,
        categories=["mammalian", "adherent", "cancer", "research"],
        properties={
            "doubling_time": 24.0,
            "optimal_temperature": 37.0,
            "optimal_ph": 7.2,
            "max_density": 5e6,
            "glucose_consumption": 0.4,
            "oxygen_consumption": 0.03,
            "lactate_production": 0.25,  # Эффект Варбурга
            "viability_threshold": 0.7,
            "apoptosis_resistance": 0.5,
            "temperature_range": (36.0, 38.0),
            "ph_range": (6.8, 7.4)
        }
    )
    cell_lines["hela"] = hela
    
    return cell_lines


def create_standard_chemicals() -> Dict[str, Chemical]:
    """Создание стандартных химических веществ"""
    
    chemicals = {}
    
    # Глюкоза
    glucose = Chemical(
        id="glucose",
        name="D-Глюкоза",
        entity_type=EntityType.CHEMICAL,
        categories=["nutrient", "carbon_source", "energy_source"],
        properties={
            "molecular_weight": 180.16,
            "solubility": 91.0,  # г/100мл при 25°C
            "diffusion_coefficient": 6.7e-10,
            "energy_yield": 2870,  # кДж/моль
            "typical_concentration": 5.0  # мМ в среде
        }
    )
    chemicals["glucose"] = glucose
    
    # Ампициллин
    ampicillin = Chemical(
        id="ampicillin",
        name="Ампициллин",
        entity_type=EntityType.ANTIBIOTIC,
        categories=["antibiotic", "beta_lactam", "bacterial_inhibitor"],
        properties={
            "molecular_weight": 349.41,
            "solubility": 10.0,  # мг/мл
            "mic": 0.5,  # мкг/мл для E. coli
            "mechanism": "cell_wall_inhibition",
            "toxicity_mammalian": 0.1,  # низкая
            "stability": 24.0  # часов в растворе при 4°C
        }
    )
    chemicals["ampicillin"] = ampicillin
    
    # Цисплатин
    cisplatin = Chemical(
        id="cisplatin",
        name="Цисплатин",
        entity_type=EntityType.CHEMOTHERAPEUTIC,
        categories=["chemotherapeutic", "dna_crosslinker", "anticancer"],
        properties={
            "molecular_weight": 300.05,
            "solubility": 1.0,  # мг/мл
            "ic50_hela": 2.5,  # мкМ
            "mechanism": "dna_crosslinking",
            "cell_cycle_specificity": "g1_s",
            "typical_concentration": 1.0  # мкМ в экспериментах
        }
    )
    chemicals["cisplatin"] = cisplatin
    
    return chemicals


# ============================================================================
# 12. ИНИЦИАЛИЗАЦИЯ И ТЕСТОВЫЙ ПРИМЕР
# ============================================================================

def initialize_system() -> BioSimApp:
    """Инициализация всей системы"""
    
    print("Инициализация Bio-Sim Engine v2.0...")
    
    # Создание приложения
    app = BioSimApp()
    
    # Добавление стандартных сущностей в базу знаний
    print("Загрузка стандартных клеточных линий...")
    cell_lines = create_standard_cell_lines()
    for cell_line in cell_lines.values():
        app.knowledge_base.add_entity(cell_line, source="system")
    
    print("Загрузка стандартных химических веществ...")
    chemicals = create_standard_chemicals()
    for chemical in chemicals.values():
        app.knowledge_base.add_entity(chemical, source="system")
    
    print("Создание стандартных протоколов...")
    # Автоматически загружены в ExperimentManager
    
    print(f"Система инициализирована. Загружено {len(app.knowledge_base.entities)} сущностей.")
    
    return app


def run_demo_experiment():
    """Запуск демонстрационного эксперимента"""
    
    print("\n" + "="*50)
    print("ДЕМОНСТРАЦИОННЫЙ ЭКСПЕРИМЕНТ")
    print("="*50)
    
    # Инициализация
    app = initialize_system()
    
    # Создание эксперимента
    exp_id = app.create_experiment(
        template_name="antibiotic_test",
        custom_name="Тестирование ампициллина на E. coli"
    )
    
    print(f"\nСоздан эксперимент: {exp_id}")
    
    # Запуск эксперимента
    print("Запуск эксперимента...")
    app.run_experiment(exp_id)
    
    # Получение результатов
    results = app.get_experiment_results(exp_id)
    
    print(f"\nЭксперимент завершен за {results['duration']}")
    print(f"Максимальная плотность клеток: {results['summary']['total_cells']:.2e}")
    
    # Вывод уведомлений
    print(f"\nУведомления ({len(app.notifications)}):")
    for note in app.notifications[-3:]:  # Последние 3
        print(f"  [{note['level'].upper()}] {note['title']}: {note['message']}")
    
    return app, results


# ============================================================================
# ГЛАВНАЯ ТОЧКА ВХОДА
# ============================================================================

if __name__ == "__main__":
    """
    Пример использования системы:
    
    1. Инициализация всей системы
    2. Создание и запуск эксперимента
    3. Анализ результатов
    4. Добавление пользовательских данных
    """
    
    try:
        # Запуск демо
        app, results = run_demo_experiment()
        
        # Пример добавления пользовательской клеточной линии
        print("\n" + "="*50)
        print("ДОБАВЛЕНИЕ ПОЛЬЗОВАТЕЛЬСКОЙ КЛЕТОЧНОЙ ЛИНИИ")
        print("="*50)
        
        new_cell_id = app.add_entity_to_kb(
            entity_type=EntityType.CELL_LINE,
            name="Мои гибридомы",
            categories=["mammalian", "hybridoma", "antibody_producer"],
            properties={
                "doubling_time": 30.0,
                "optimal_temperature": 37.0,
                "optimal_ph": 7.3,
                "max_density": 2e6,
                "glucose_consumption": 0.25,
                "requires_il6": True
            }
        )
        
        print(f"Добавлена новая клеточная линия: {new_cell_id}")
        
        # Проверка доступных экспериментов
        print(f"\nДоступные шаблоны экспериментов:")
        for template_name in app.experiment_manager.experiment_templates.keys():
            print(f"  - {template_name}")
        
        print("\nСистема готова к работе!")
        
    except Exception as e:
        print(f"Ошибка при запуске системы: {e}")
        import traceback
        traceback.print_exc()