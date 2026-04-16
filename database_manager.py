"""
ENKOMOS - Database Manager
Energy & Keystone Operating Management Operating System

Handles all JSON database operations with full user edit capability.
Add, delete, modify any field. Extensible for future unknown parameters.
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional

# ==================== DATABASE PATHS ====================
# These should match config.py
DB_PATHS = {
    "crop_reference": "databases/crop_reference.json",
    "nutrition_db": "databases/nutrition_db.json",
    "regional_presets": "databases/regional_presets.json",
    "water_types": "databases/water_types.json",
    "growth_log": "logs/growth_log.json",
}

# ==================== DEFAULT DATABASES ====================
# Created automatically if files don't exist

DEFAULT_CROP_DB = {
    "tomato": {
        "temp_min_c": 18,
        "temp_max_c": 28,
        "temp_ideal_c": 24,
        "humidity_min": 60,
        "humidity_max": 80,
        "light_hours": 12,
        "co2_ppm": 800,
        "water_ml_per_day": 500,
        "ph_min": 6.0,
        "ph_max": 6.8,
        "ec_min": 1.5,
        "ec_max": 2.5,
        "growth_days_to_harvest": 75,
        "notes": "Indeterminate variety, needs staking"
    },
    "wheat": {
        "temp_min_c": 12,
        "temp_max_c": 25,
        "temp_ideal_c": 18,
        "humidity_min": 40,
        "humidity_max": 60,
        "light_hours": 14,
        "co2_ppm": 450,
        "water_ml_per_day": 200,
        "ph_min": 6.0,
        "ph_max": 7.5,
        "ec_min": 1.0,
        "ec_max": 2.0,
        "growth_days_to_harvest": 120,
        "notes": "Spring wheat variety"
    },
    "basil": {
        "temp_min_c": 18,
        "temp_max_c": 30,
        "temp_ideal_c": 24,
        "humidity_min": 50,
        "humidity_max": 70,
        "light_hours": 14,
        "co2_ppm": 600,
        "water_ml_per_day": 100,
        "ph_min": 5.5,
        "ph_max": 6.5,
        "ec_min": 1.0,
        "ec_max": 1.6,
        "growth_days_to_harvest": 30,
        "notes": "Harvest leaves continuously"
    },
    "tilapia": {
        "type": "fish",
        "water_temp_min_c": 24,
        "water_temp_max_c": 30,
        "water_temp_ideal_c": 27,
        "ph_min": 6.5,
        "ph_max": 8.0,
        "ammonia_max_ppm": 0.5,
        "dissolved_oxygen_min_mgl": 4.0,
        "feeding_percent_body_weight": 3.0,
        "growth_days_to_harvest": 240,
        "stocking_density_per_m3": 50,
        "notes": "Tilapia nilotica"
    }
}

DEFAULT_NUTRITION_DB = {
    "tomato_vegetative": {
        "N_ppm": 150,
        "P_ppm": 50,
        "K_ppm": 200,
        "Ca_ppm": 120,
        "Mg_ppm": 40,
        "Fe_ppm": 2.5,
        "Zn_ppm": 0.5,
        "Cu_ppm": 0.1,
        "Mn_ppm": 0.5,
        "B_ppm": 0.3,
        "Mo_ppm": 0.05,
        "ph_target": 6.2,
        "ec_target": 2.0
    },
    "tomato_fruiting": {
        "N_ppm": 120,
        "P_ppm": 60,
        "K_ppm": 250,
        "Ca_ppm": 150,
        "Mg_ppm": 45,
        "Fe_ppm": 2.5,
        "Zn_ppm": 0.5,
        "Cu_ppm": 0.1,
        "Mn_ppm": 0.5,
        "B_ppm": 0.3,
        "Mo_ppm": 0.05,
        "ph_target": 6.3,
        "ec_target": 2.2
    },
    "lettuce_leafy": {
        "N_ppm": 100,
        "P_ppm": 30,
        "K_ppm": 150,
        "Ca_ppm": 80,
        "Mg_ppm": 30,
        "Fe_ppm": 2.0,
        "Zn_ppm": 0.3,
        "Cu_ppm": 0.05,
        "Mn_ppm": 0.3,
        "B_ppm": 0.2,
        "Mo_ppm": 0.03,
        "ph_target": 6.0,
        "ec_target": 1.2
    }
}

DEFAULT_REGIONAL_PRESETS = {
    "temperate_coastal": {
        "base_temp_c": 15,
        "seasonal_variation": "moderate",
        "humidity_baseline": 70,
        "light_hours_winter": 9,
        "light_hours_summer": 15,
        "frost_risk": "low",
        "notes": "Example: Portugal coast, Estela region"
    },
    "tropical": {
        "base_temp_c": 26,
        "seasonal_variation": "low",
        "humidity_baseline": 80,
        "light_hours_winter": 12,
        "light_hours_summer": 13,
        "frost_risk": "none",
        "notes": "High humidity, consistent temps"
    },
    "arid": {
        "base_temp_c": 28,
        "seasonal_variation": "high",
        "humidity_baseline": 30,
        "light_hours_winter": 10,
        "light_hours_summer": 14,
        "frost_risk": "low",
        "notes": "Dry, high evaporation"
    }
}

DEFAULT_WATER_TYPES = {
    "normal_tap": {
        "orp_mv": 200,
        "ph": 7.0,
        "do_mgl": 6.0,
        "surface_tension_mNm": 72,
        "notes": "Untreated municipal water"
    },
    "structured_vortex": {
        "orp_mv": 300,
        "ph": 6.8,
        "do_mgl": 8.0,
        "surface_tension_mNm": 65,
        "notes": "Vortexed 3 passes, reduced surface tension"
    },
    "charged_electrolytic": {
        "orp_mv": 400,
        "ph": 6.5,
        "do_mgl": 9.0,
        "surface_tension_mNm": 68,
        "notes": "Electrolytically activated, higher ORP"
    }
}


# ==================== DATABASE MANAGER CLASS ====================

class DatabaseManager:
    """Handles all ENKOMOS database operations with full user edit capability"""
    
    def __init__(self, custom_paths: Optional[Dict] = None):
        self.paths = custom_paths if custom_paths else DB_PATHS
        self._ensure_directories()
        self._initialize_databases()
    
    def _ensure_directories(self):
        """Create database and log directories if they don't exist"""
        for path in self.paths.values():
            directory = os.path.dirname(path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
    
    def _initialize_databases(self):
        """Create default database files if they don't exist"""
        defaults = {
            "crop_reference": DEFAULT_CROP_DB,
            "nutrition_db": DEFAULT_NUTRITION_DB,
            "regional_presets": DEFAULT_REGIONAL_PRESETS,
            "water_types": DEFAULT_WATER_TYPES,
            "growth_log": {}
        }
        
        for db_name, db_path in self.paths.items():
            if not os.path.exists(db_path):
                with open(db_path, 'w') as f:
                    json.dump(defaults.get(db_name, {}), f, indent=4)
                print(f"[INFO] Created default database: {db_name}")
    
    # ==================== LOAD DATABASES ====================
    
    def load_crop_db(self) -> Dict:
        """Load crop reference database"""
        with open(self.paths["crop_reference"], 'r') as f:
            return json.load(f)
    
    def load_nutrition_db(self) -> Dict:
        """Load nutrition database"""
        with open(self.paths["nutrition_db"], 'r') as f:
            return json.load(f)
    
    def load_regional_presets(self) -> Dict:
        """Load regional presets"""
        with open(self.paths["regional_presets"], 'r') as f:
            return json.load(f)
    
    def load_water_types(self) -> Dict:
        """Load water types database"""
        with open(self.paths["water_types"], 'r') as f:
            return json.load(f)
    
    def load_growth_log(self) -> Dict:
        """Load growth log (historical data)"""
        with open(self.paths["growth_log"], 'r') as f:
            return json.load(f)
    
    # ==================== SAVE DATABASES ====================
    
    def save_crop_db(self, data: Dict) -> bool:
        """Save crop reference database"""
        return self._save_db("crop_reference", data)
    
    def save_nutrition_db(self, data: Dict) -> bool:
        """Save nutrition database"""
        return self._save_db("nutrition_db", data)
    
    def save_regional_presets(self, data: Dict) -> bool:
        """Save regional presets"""
        return self._save_db("regional_presets", data)
    
    def save_water_types(self, data: Dict) -> bool:
        """Save water types database"""
        return self._save_db("water_types", data)
    
    def save_growth_log(self, data: Dict) -> bool:
        """Save growth log"""
        return self._save_db("growth_log", data)
    
    def _save_db(self, db_name: str, data: Dict) -> bool:
        """Internal save method with backup"""
        try:
            path = self.paths[db_name]
            # Create backup
            backup_path = path + ".backup"
            if os.path.exists(path):
                shutil.copy(path, backup_path)
            # Write new data
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"[INFO] Saved {db_name}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save {db_name}: {e}")
            return False
    
    # ==================== USER EDIT OPERATIONS ====================
    
    def add_crop(self, crop_name: str, crop_data: Dict) -> bool:
        """Add a new crop to the database"""
        db = self.load_crop_db()
        if crop_name in db:
            print(f"[WARN] Crop '{crop_name}' already exists. Use modify_crop to change.")
            return False
        db[crop_name] = crop_data
        return self.save_crop_db(db)
    
    def delete_crop(self, crop_name: str) -> bool:
        """Delete a crop from the database"""
        db = self.load_crop_db()
        if crop_name not in db:
            print(f"[WARN] Crop '{crop_name}' not found.")
            return False
        del db[crop_name]
        return self.save_crop_db(db)
    
    def modify_crop(self, crop_name: str, field: str, new_value: Any) -> bool:
        """Modify a single field of a crop"""
        db = self.load_crop_db()
        if crop_name not in db:
            print(f"[WARN] Crop '{crop_name}' not found.")
            return False
        db[crop_name][field] = new_value
        return self.save_crop_db(db)
    
    def add_custom_field_to_crop(self, crop_name: str, field_name: str, default_value: Any) -> bool:
        """Add a new custom field to a crop (extensible schema)"""
        db = self.load_crop_db()
        if crop_name not in db:
            print(f"[WARN] Crop '{crop_name}' not found.")
            return False
        db[crop_name][field_name] = default_value
        return self.save_crop_db(db)
    
    # Nutrition operations
    def add_nutrition_profile(self, profile_name: str, profile_data: Dict) -> bool:
        """Add a new nutrition profile"""
        db = self.load_nutrition_db()
        if profile_name in db:
            print(f"[WARN] Profile '{profile_name}' already exists.")
            return False
        db[profile_name] = profile_data
        return self.save_nutrition_db(db)
    
    def delete_nutrition_profile(self, profile_name: str) -> bool:
        """Delete a nutrition profile"""
        db = self.load_nutrition_db()
        if profile_name not in db:
            print(f"[WARN] Profile '{profile_name}' not found.")
            return False
        del db[profile_name]
        return self.save_nutrition_db(db)
    
    # Regional preset operations
    def add_region(self, region_name: str, region_data: Dict) -> bool:
        """Add a new regional preset"""
        db = self.load_regional_presets()
        if region_name in db:
            print(f"[WARN] Region '{region_name}' already exists.")
            return False
        db[region_name] = region_data
        return self.save_regional_presets(db)
    
    # Water type operations
    def add_water_type(self, water_name: str, water_data: Dict) -> bool:
        """Add a new water type (structured, charged, etc.)"""
        db = self.load_water_types()
        if water_name in db:
            print(f"[WARN] Water type '{water_name}' already exists.")
            return False
        db[water_name] = water_data
        return self.save_water_types(db)
    
    # ==================== QUERY OPERATIONS ====================
    
    def get_crop_parameters(self, crop_name: str) -> Optional[Dict]:
        """Get all parameters for a specific crop"""
        db = self.load_crop_db()
        return db.get(crop_name)
    
    def get_nutrition_profile(self, profile_name: str) -> Optional[Dict]:
        """Get a specific nutrition profile"""
        db = self.load_nutrition_db()
        return db.get(profile_name)
    
    def get_region_preset(self, region_name: str) -> Optional[Dict]:
        """Get a specific regional preset"""
        db = self.load_regional_presets()
        return db.get(region_name)
    
    def get_water_type(self, water_name: str) -> Optional[Dict]:
        """Get a specific water type"""
        db = self.load_water_types()
        return db.get(water_name)
    
    # ==================== LOGGING GROWTH DATA ====================
    
    def log_growth_entry(self, zone: int, crop: str, measurements: Dict) -> bool:
        """Log daily or periodic growth measurements"""
        log = self.load_growth_log()
        timestamp = datetime.now().isoformat()
        
        if str(zone) not in log:
            log[str(zone)] = {}
        if crop not in log[str(zone)]:
            log[str(zone)][crop] = []
        
        entry = {
            "timestamp": timestamp,
            **measurements
        }
        log[str(zone)][crop].append(entry)
        return self.save_growth_log(log)
    
    # ==================== UTILITY ====================
    
    def export_all_databases(self, export_dir: str) -> bool:
        """Export all databases to a directory (for backup or transfer)"""
        try:
            os.makedirs(export_dir, exist_ok=True)
            for db_name, db_path in self.paths.items():
                if os.path.exists(db_path):
                    dest = os.path.join(export_dir, f"{db_name}.json")
                    shutil.copy(db_path, dest)
            print(f"[INFO] Exported all databases to {export_dir}")
            return True
        except Exception as e:
            print(f"[ERROR] Export failed: {e}")
            return False
    
    def list_all_crops(self) -> List[str]:
        """Return list of all crop names"""
        db = self.load_crop_db()
        return list(db.keys())
    
    def list_all_regions(self) -> List[str]:
        """Return list of all regional presets"""
        db = self.load_regional_presets()
        return list(db.keys())


# ==================== COMMAND LINE INTERFACE FOR TESTING ====================
if __name__ == "__main__":
    # Quick test
    dbm = DatabaseManager()
    
    print("=== ENKOMOS Database Manager Test ===")
    print(f"Crops available: {dbm.list_all_crops()}")
    print(f"Regions available: {dbm.list_all_regions()}")
    
    # Example: Add a custom field to tomato
    dbm.add_custom_field_to_crop("tomato", "my_custom_field", "test_value")
    print("Added custom field to tomato")
    
    # Example: Add a new water type
    new_water = {
        "orp_mv": 350,
        "ph": 6.4,
        "do_mgl": 8.5,
        "surface_tension_mNm": 62,
        "notes": "Magnetic structured water, 3 passes"
    }
    dbm.add_water_type("magnetic_3x", new_water)
    print("Added magnetic_3x water type")
    
    print("Database Manager ready.")
