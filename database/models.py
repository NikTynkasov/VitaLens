# [file database/models.py]
# Модели данных
from datetime import datetime

class Microorganism:
    def __init__(self, id=None, genus="", species="", strain="", gram_staining="", morphology="", 
                 metabolism="", ph_optimum=0.0, temperature_optimum=0.0, growth_rate=0.0, 
                 model_type="", k_constant=0.0, y_constant=0.0):
        self.id = id
        self.genus = genus
        self.species = species
        self.strain = strain
        self.gram_staining = gram_staining
        self.morphology = morphology
        self.metabolism = metabolism
        self.ph_optimum = ph_optimum
        self.temperature_optimum = temperature_optimum
        self.growth_rate = growth_rate
        self.model_type = model_type
        self.k_constant = k_constant
        self.y_constant = y_constant
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class CultureMedia:
    def __init__(self, id=None, media_type="", name="", composition="", ph=0.0, color="", 
                 consistency="", preparation_method=""):
        self.id = id
        self.media_type = media_type
        self.name = name
        self.composition = composition
        self.ph = ph
        self.color = color
        self.consistency = consistency
        self.preparation_method = preparation_method
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class Substance:
    def __init__(self, id=None, substance_class="", name="", formula="", molecular_weight=0.0, 
                 solubility="", energy_value=0.0, toxic_concentration=0.0, description=""):
        self.id = id
        self.substance_class = substance_class
        self.name = name
        self.formula = formula
        self.molecular_weight = molecular_weight
        self.solubility = solubility
        self.energy_value = energy_value
        self.toxic_concentration = toxic_concentration
        self.description = description
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class Interaction:
    def __init__(self, id=None, base_type="", mechanism="", description="", mathematical_model="", 
                 alpha_coefficient=0.0, beta_coefficient=0.0, distance_effect=0.0):
        self.id = id
        self.base_type = base_type
        self.mechanism = mechanism
        self.description = description
        self.mathematical_model = mathematical_model
        self.alpha_coefficient = alpha_coefficient
        self.beta_coefficient = beta_coefficient
        self.distance_effect = distance_effect
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class BioreactorParam:
    def __init__(self, id=None, system_type="", configuration="", volume=0.0, area=0.0, 
                 stirring_speed=0.0, mass_transfer_coefficient=0.0, material="", 
                 oxygen_transfer_rate=0.0, description=""):
        self.id = id
        self.system_type = system_type
        self.configuration = configuration
        self.volume = volume
        self.area = area
        self.stirring_speed = stirring_speed
        self.mass_transfer_coefficient = mass_transfer_coefficient
        self.material = material
        self.oxygen_transfer_rate = oxygen_transfer_rate
        self.description = description
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class Antimicrobial:
    def __init__(self, id=None, agent_class="", name="", target="", typical_mic="", 
                 resistance_mechanism="", concentration_unit="", spectrum=""):
        self.id = id
        self.agent_class = agent_class
        self.name = name
        self.target = target
        self.typical_mic = typical_mic
        self.resistance_mechanism = resistance_mechanism
        self.concentration_unit = concentration_unit
        self.spectrum = spectrum
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class MetabolicPathway:
    def __init__(self, id=None, product_type="", product_name="", producing_strains="", 
                 biosynthesis_pathway="", optimal_ph=0.0, optimal_temperature=0.0, 
                 growth_phase="", yield_value=0.0, description=""):
        self.id = id
        self.product_type = product_type
        self.product_name = product_name
        self.producing_strains = producing_strains
        self.biosynthesis_pathway = biosynthesis_pathway
        self.optimal_ph = optimal_ph
        self.optimal_temperature = optimal_temperature
        self.growth_phase = growth_phase
        self.yield_value = yield_value
        self.description = description
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

class ExperimentalProtocol:
    def __init__(self, id=None, experiment_purpose="", protocol_name="", step_by_step="", 
                 materials="", calculation_formulas="", references="", duration_minutes=0, 
                 difficulty_level=""):
        self.id = id
        self.experiment_purpose = experiment_purpose
        self.protocol_name = protocol_name
        self.step_by_step = step_by_step
        self.materials = materials
        self.calculation_formulas = calculation_formulas
        self.references = references
        self.duration_minutes = duration_minutes
        self.difficulty_level = difficulty_level
        self.created_at = datetime.now()
        self.updated_at = datetime.now()