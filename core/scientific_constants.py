class ScientificConstants:
    """Научные константы и физиологические параметры"""
    
    # Универсальные биологические константы
    AVOGADRO = 6.022e23
    GAS_CONSTANT = 8.314  # Дж/(моль·К)
    FARADAY_CONSTANT = 96485  # Кл/моль
    
    # Температурные пределы (°C)
    TEMP_RANGES = {
        'psychrophilic': (-5, 20),
        'mesophilic': (20, 45),
        'thermophilic': (45, 80),
        'hyperthermophilic': (80, 122)
    }
    
    # pH диапазоны
    PH_RANGES = {
        'acidophilic': (0, 5.5),
        'neutrophilic': (5.5, 8.5),
        'alkaliphilic': (8.5, 12)
    }
    
    # Стандартные концентрации (mM)
    TYPICAL_CONCENTRATIONS = {
        'glucose': 10.0,
        'oxygen': 0.21,
        'ammonia': 5.0,
        'phosphate': 1.0
    }