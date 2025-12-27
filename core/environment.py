import numpy as np
from typing import Optional, Tuple, List
import random

class ScientificEnvironment:
    """Научно-достоверная система среды для клеточных симуляций"""
    
    def __init__(self, size: Tuple[int, int]):
        self.width, self.height = size
        self.size = size
        
        # Параметры среды с реальными единицами измерения
        self.temperature = np.full(size, 37.0)  # °C
        self.ph = np.full(size, 7.0)            # pH
        self.oxygen = np.full(size, 0.21)       # атм (концентрация O2)
        self.glucose = np.full(size, 10.0)      # mM
        self.ammonia = np.full(size, 5.0)       # mM (источник азота)
        self.phosphate = np.full(size, 1.0)     # mM
        self.antibiotics = np.zeros(size)       # концентрация антибиотиков
        self.toxins = np.zeros(size)            # токсины
        self.waste_products = np.zeros(size)    # продукты метаболизма
        self.growth_factors = np.zeros(size)    # факторы роста
        
        # Физические параметры
        self.viscosity = np.full(size, 1.0)     # вязкость
        self.quorum_signaling = np.zeros(size)  # уровень quorum sensing
        self.cell_density = np.zeros(size)      # плотность клеток
        
        # Параметры диффузии
        self.diffusion_rates = {
            'glucose': 0.1,
            'oxygen': 0.3,
            'antibiotics': 0.05,
            'toxins': 0.08,
            'waste': 0.02,
            'growth_factors': 0.15
        }
        
    def diffuse_chemicals(self):
        """Диффузия химических веществ в среде с реальными коэффициентами"""
        chemicals = {
            'glucose': self.glucose,
            'oxygen': self.oxygen,
            'antibiotics': self.antibiotics,
            'toxins': self.toxins,
            'waste': self.waste_products,
            'growth_factors': self.growth_factors
        }
        
        for chemical_name, chemical_layer in chemicals.items():
            diffusion_rate = self.diffusion_rates.get(chemical_name, 0.1)
            new_layer = chemical_layer.copy()
            
            # Простая модель диффузии (дискретный лапласиан)
            for x in range(1, self.width - 1):
                for y in range(1, self.height - 1):
                    # 4-связное соседство
                    neighbors_sum = (
                        chemical_layer[x-1, y] + chemical_layer[x+1, y] +
                        chemical_layer[x, y-1] + chemical_layer[x, y+1]
                    )
                    diffusion = diffusion_rate * (neighbors_sum - 4 * chemical_layer[x, y])
                    new_layer[x, y] += diffusion
            
            # Граничные условия - нулевой поток
            new_layer[0, :] = new_layer[1, :]  # левая граница
            new_layer[-1, :] = new_layer[-2, :]  # правая граница
            new_layer[:, 0] = new_layer[:, 1]  # верхняя граница
            new_layer[:, -1] = new_layer[:, -2]  # нижняя граница
            
            # Обновляем слой
            if chemical_name == 'glucose':
                self.glucose = np.maximum(0, new_layer)
            elif chemical_name == 'oxygen':
                self.oxygen = np.maximum(0, new_layer)
            elif chemical_name == 'antibiotics':
                self.antibiotics = np.maximum(0, new_layer)
            elif chemical_name == 'toxins':
                self.toxins = np.maximum(0, new_layer)
            elif chemical_name == 'waste':
                self.waste_products = np.maximum(0, new_layer)
            elif chemical_name == 'growth_factors':
                self.growth_factors = np.maximum(0, new_layer)
    
    def update_temperature_gradient(self, heat_sources: List[Tuple[int, int, float]]):
        """Обновление температурного градиента от источников тепла"""
        if not heat_sources:
            # Медленный возврат к комнатной температуре
            self.temperature += (25.0 - self.temperature) * 0.01
            return
            
        new_temperature = np.full(self.size, 25.0)  # Базовая температура
        
        for source_x, source_y, heat_power in heat_sources:
            for x in range(self.width):
                for y in range(self.height):
                    distance = np.sqrt((x - source_x)**2 + (y - source_y)**2)
                    if distance == 0:
                        temperature_contribution = heat_power
                    else:
                        temperature_contribution = heat_power / (1 + distance**2)
                    new_temperature[x, y] += temperature_contribution
        
        # Плавное изменение температуры
        self.temperature += (new_temperature - self.temperature) * 0.1
    
    def apply_external_factors(self, factor: str, concentration: float, 
                             position: Optional[Tuple[int, int]] = None, 
                             radius: int = 1):
        """Применение внешних факторов к среде"""
        
        if position:
            x, y = position
            # Применяем в области вокруг указанной позиции
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        distance = np.sqrt(dx**2 + dy**2)
                        effective_concentration = concentration / (1 + distance)
                        
                        if factor == "antibiotic":
                            self.antibiotics[nx, ny] += effective_concentration
                        elif factor == "glucose":
                            self.glucose[nx, ny] += effective_concentration
                        elif factor == "oxygen":
                            self.oxygen[nx, ny] += effective_concentration
                        elif factor == "toxin":
                            self.toxins[nx, ny] += effective_concentration
                        elif factor == "growth_factor":
                            self.growth_factors[nx, ny] += effective_concentration
                        elif factor == "temperature_change":
                            self.temperature[nx, ny] += effective_concentration
                        elif factor == "ph_change":
                            self.ph[nx, ny] += effective_concentration
        else:
            # Применяем равномерно ко всей среде
            if factor == "antibiotic":
                self.antibiotics += concentration
            elif factor == "glucose":
                self.glucose += concentration
            elif factor == "oxygen":
                self.oxygen += concentration
            elif factor == "toxin":
                self.toxins += concentration
            elif factor == "growth_factor":
                self.growth_factors += concentration
            elif factor == "temperature_change":
                self.temperature += concentration
            elif factor == "ph_change":
                self.ph += concentration
    
    def update_cell_density(self, cell_positions: List[Tuple[int, int]]):
        """Обновление карты плотности клеток"""
        self.cell_density = np.zeros(self.size)
        
        for x, y in cell_positions:
            if 0 <= x < self.width and 0 <= y < self.height:
                # Распределяем влияние клетки на окружающую область
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            distance = np.sqrt(dx**2 + dy**2)
                            influence = 1.0 / (1 + distance**2)
                            self.cell_density[nx, ny] += influence
        
        # Нормализуем плотность
        if np.max(self.cell_density) > 0:
            self.cell_density = self.cell_density / np.max(self.cell_density)
    
    def calculate_local_conditions(self, x: int, y: int) -> dict:
        """Расчет локальных условий в конкретной позиции"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return {}
            
        return {
            'temperature': self.temperature[x, y],
            'ph': self.ph[x, y],
            'oxygen': self.oxygen[x, y],
            'glucose': self.glucose[x, y],
            'antibiotics': self.antibiotics[x, y],
            'toxins': self.toxins[x, y],
            'waste': self.waste_products[x, y],
            'growth_factors': self.growth_factors[x, y],
            'cell_density': self.cell_density[x, y],
            'viscosity': self.viscosity[x, y]
        }
    
    def get_environmental_stress(self, x: int, y: int) -> float:
        """Расчет общего уровня стресса в позиции (0-1)"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 1.0
            
        stress_factors = []
        
        # Температурный стресс
        temp_stress = abs(self.temperature[x, y] - 37.0) / 20.0
        stress_factors.append(min(temp_stress, 1.0))
        
        # pH стресс
        ph_stress = abs(self.ph[x, y] - 7.0) / 3.0
        stress_factors.append(min(ph_stress, 1.0))
        
        # Токсический стресс
        toxin_stress = min(self.toxins[x, y] / 5.0, 1.0)
        stress_factors.append(toxin_stress)
        
        # Антибиотический стресс
        antibiotic_stress = min(self.antibiotics[x, y] / 2.0, 1.0)
        stress_factors.append(antibiotic_stress)
        
        # Стресс от продуктов метаболизма
        waste_stress = min(self.waste_products[x, y] / 10.0, 1.0)
        stress_factors.append(waste_stress)
        
        # Кислородное голодание
        oxygen_stress = max(0, (0.1 - self.oxygen[x, y]) / 0.1)
        stress_factors.append(oxygen_stress)
        
        # Голодание
        glucose_stress = max(0, (1.0 - self.glucose[x, y]) / 1.0)
        stress_factors.append(glucose_stress)
        
        return min(sum(stress_factors) / len(stress_factors), 1.0)
    
    def get_growth_potential(self, x: int, y: int) -> float:
        """Расчет потенциала роста в позиции (0-1)"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 0.0
            
        growth_factors = []
        
        # Глюкоза - основной лимитирующий фактор
        glucose_factor = min(self.glucose[x, y] / 5.0, 1.0)
        growth_factors.append(glucose_factor)
        
        # Кислород
        oxygen_factor = min(self.oxygen[x, y] / 0.1, 1.0)
        growth_factors.append(oxygen_factor * 0.5)  # Меньший вес
        
        # Факторы роста
        growth_factor_level = min(self.growth_factors[x, y] / 2.0, 1.0)
        growth_factors.append(growth_factor_level * 0.8)
        
        # Оптимальная температура
        temp_optimal = 1.0 - abs(self.temperature[x, y] - 37.0) / 10.0
        growth_factors.append(max(temp_optimal, 0.0))
        
        # Оптимальный pH
        ph_optimal = 1.0 - abs(self.ph[x, y] - 7.0) / 2.0
        growth_factors.append(max(ph_optimal, 0.0))
        
        # Учет негативных факторов
        stress_level = self.get_environmental_stress(x, y)
        positive_potential = sum(growth_factors) / len(growth_factors)
        
        return max(0.0, positive_potential * (1.0 - stress_level))
    
    def degrade_chemicals(self):
        """Естественная деградация химических веществ со временем"""
        # Антибиотики разлагаются
        self.antibiotics *= 0.99
        
        # Токсины разлагаются
        self.toxins *= 0.995
        
        # Факторы роста деградируют
        self.growth_factors *= 0.998
        
        # Продукты метаболизма медленно удаляются
        self.waste_products *= 0.999
        
        # Кислород пополняется из атмосферы
        self.oxygen += (0.21 - self.oxygen) * 0.01
        
        # Температура стремится к комнатной
        self.temperature += (25.0 - self.temperature) * 0.001
        
        # pH буферизуется к нейтральному
        self.ph += (7.0 - self.ph) * 0.005
    
    def add_nutrient_patch(self, center_x: int, center_y: int, radius: int = 3, 
                          nutrient_type: str = "glucose", amount: float = 10.0):
        """Добавление локального источника питательных веществ"""
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                distance = np.sqrt(dx**2 + dy**2)
                if distance <= radius:
                    x, y = center_x + dx, center_y + dy
                    if 0 <= x < self.width and 0 <= y < self.height:
                        # Гауссово распределение
                        effective_amount = amount * np.exp(-distance**2 / (2 * (radius/2)**2))
                        
                        if nutrient_type == "glucose":
                            self.glucose[x, y] += effective_amount
                        elif nutrient_type == "oxygen":
                            self.oxygen[x, y] += effective_amount
                        elif nutrient_type == "ammonia":
                            self.ammonia[x, y] += effective_amount
                        elif nutrient_type == "phosphate":
                            self.phosphate[x, y] += effective_amount
    
    def create_gradient(self, chemical: str, direction: str = "horizontal", 
                       min_val: float = 0.0, max_val: float = 1.0):
        """Создание химического градиента в среде"""
        if direction == "horizontal":
            for x in range(self.width):
                value = min_val + (max_val - min_val) * (x / self.width)
                for y in range(self.height):
                    if chemical == "glucose":
                        self.glucose[x, y] = value
                    elif chemical == "oxygen":
                        self.oxygen[x, y] = value
                    elif chemical == "antibiotics":
                        self.antibiotics[x, y] = value
        elif direction == "vertical":
            for y in range(self.height):
                value = min_val + (max_val - min_val) * (y / self.height)
                for x in range(self.width):
                    if chemical == "glucose":
                        self.glucose[x, y] = value
                    elif chemical == "oxygen":
                        self.oxygen[x, y] = value
                    elif chemical == "antibiotics":
                        self.antibiotics[x, y] = value
    
    def get_statistics(self) -> dict:
        """Получение статистики по всей среде"""
        return {
            'avg_temperature': np.mean(self.temperature),
            'avg_ph': np.mean(self.ph),
            'total_glucose': np.sum(self.glucose),
            'total_oxygen': np.sum(self.oxygen),
            'total_antibiotics': np.sum(self.antibiotics),
            'total_toxins': np.sum(self.toxins),
            'total_waste': np.sum(self.waste_products),
            'max_cell_density': np.max(self.cell_density),
            'environmental_heterogeneity': np.std(self.glucose) + np.std(self.oxygen)
        }
    
    def reset_environment(self, preset: str = "standard"):
        """Сброс среды к предустановленным параметрам"""
        presets = {
            "standard": {
                "temperature": 37.0,
                "ph": 7.0,
                "oxygen": 0.21,
                "glucose": 10.0,
                "antibiotics": 0.0,
                "toxins": 0.0
            },
            "stressful": {
                "temperature": 42.0,
                "ph": 6.0,
                "oxygen": 0.05,
                "glucose": 2.0,
                "antibiotics": 0.5,
                "toxins": 1.0
            },
            "optimal": {
                "temperature": 37.0,
                "ph": 7.2,
                "oxygen": 0.25,
                "glucose": 15.0,
                "antibiotics": 0.0,
                "toxins": 0.0
            }
        }
        
        preset_params = presets.get(preset, presets["standard"])
        
        self.temperature = np.full(self.size, preset_params["temperature"])
        self.ph = np.full(self.size, preset_params["ph"])
        self.oxygen = np.full(self.size, preset_params["oxygen"])
        self.glucose = np.full(self.size, preset_params["glucose"])
        self.antibiotics = np.full(self.size, preset_params["antibiotics"])
        self.toxins = np.full(self.size, preset_params["toxins"])
        self.waste_products = np.zeros(self.size)
        self.growth_factors = np.zeros(self.size)

    def get_empty_neighbors(self, position, moore: bool = True):
        """Поиск пустых соседних клеток (совместимость со старой версией)"""
        # В новой версии Mesa эта функциональность реализована в самой модели
        # Возвращаем пустой список - логика будет в основном классе модели
        return []