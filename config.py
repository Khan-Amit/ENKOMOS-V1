"""
ENKOMOS - Master Configuration File
Energy & Keystone Operating Management Operating System

Edit this file to match your hardware, zones, sensors, and thresholds.
"""

# ==================== SYSTEM SETTINGS ====================
SYSTEM = {
    "name": "ENKOMOS",
    "version": "1.0.0",
    "mode": "autonomous",  # autonomous, manual, hybrid
    "log_level": "INFO",   # DEBUG, INFO, WARNING, ERROR
    "timezone": "Europe/Lisbon",
    "ai_interval_seconds": 30,  # How often AI makes decisions
}

# ==================== ZONE CONFIGURATION ====================
# Six zones as per sacred number 6
ZONES = {
    1: {"name": "Normal Produce", "active": True, "crop_type": "vegetables"},
    2: {"name": "Mushrooms", "active": True, "crop_type": "mushroom"},
    3: {"name": "Herbs", "active": True, "crop_type": "herbs"},
    4: {"name": "Vegetables", "active": True, "crop_type": "vegetables"},
    5: {"name": "Other Produce", "active": True, "crop_type": "other"},
    6: {"name": "Reserve", "active": False, "crop_type": "none"},
}

# ==================== SPATIAL LAYERS ====================
LAYERS = {
    "indoor_greenhouse": True,
    "covered_shaded": True,
    "outdoor_open": True,
}

# ==================== CLIMATE THRESHOLDS (per zone) ====================
# Example for Zone 1 - Normal Produce
CLIMATE_THRESHOLDS = {
    1: {  # Zone 1
        "temp_min_c": 18,
        "temp_max_c": 28,
        "temp_ideal_c": 24,
        "humidity_min_percent": 50,
        "humidity_max_percent": 80,
        "humidity_ideal_percent": 65,
        "co2_ppm_min": 400,
        "co2_ppm_max": 1200,
        "co2_ppm_ideal": 800,
        "vpd_ideal_kpa": 0.8,  # Vapor Pressure Deficit
    },
    # Add zones 2-6 similarly
}

# ==================== STRUCTURED WATER PARAMETERS ====================
STRUCTURED_WATER = {
    "enabled": True,
    "monitor_orp": True,      # Oxidation Reduction Potential
    "orp_target_mv": 300,
    "orp_min_mv": 200,
    "orp_max_mv": 400,
    "monitor_ph": True,
    "ph_target": 6.5,
    "ph_min": 6.0,
    "ph_max": 7.0,
    "monitor_do": True,       # Dissolved Oxygen
    "do_target_mgl": 7.0,
    "do_min_mgl": 5.0,
    "bypass_valve_pin": 23,   # GPIO pin for structured water bypass
}

# ==================== ENERGY SETTINGS (AC, Sodium-Ion) ====================
ENERGY = {
    "primary_source": "solar",  # solar, wind, biogas, hybrid
    "battery_type": "sodium_ion",
    "battery_capacity_kwh": 100,
    "battery_min_soc_percent": 30,  # State of Charge - never go below
    "grid_independent": True,
    "ac_frequency_hz": 50,  # Portugal standard
    "frequency_logging": True,  # Log frequency for growth research
    "solar_pv_power_kw": 50,
    "wind_turbine_power_kw": 10,
    "biogas_power_kw": 20,
}

# ==================== HEAT SOURCES ====================
HEAT_SOURCES = {
    "ir_heaters": True,
    "compost_heat_exchanger": True,
    "biogas_boiler": True,
    "geothermal": False,  # Optional add-on
}

# ==================== ACTUATOR PINS (GPIO / Modbus) ====================
# Example using GPIO pin numbers (Raspberry Pi)
ACTUATORS = {
    "mist_controller": 17,
    "ir_heater_zone1": 18,
    "ir_heater_zone2": 19,
    "humidity_fogger": 20,
    "exhaust_fan": 21,
    "co2_injector": 22,
    "led_lights": 24,
    "airflow_fan_array": 25,
    "structured_water_valve": 23,
    "water_pump_fish_tub": 26,
    "water_pump_irrigation": 27,
}

# ==================== SENSOR PINS / ADDRESSES ====================
SENSORS = {
    "temp_humidity_indoor": "i2c:0x40",  # Example: SHT30 address
    "temp_humidity_outdoor": "i2c:0x41",
    "soil_ph_zone1": "adc:0",
    "soil_npk_zone1": "modbus:1",
    "water_orp": "modbus:2",
    "water_ph": "modbus:3",
    "water_do": "modbus:4",
    "water_ec": "modbus:5",
    "weather_station": "serial:/dev/ttyUSB0",
    "ac_frequency_sensor": "modbus:6",
}

# ==================== DATABASE FILES (JSON) ====================
DATABASES = {
    "crop_reference": "databases/crop_reference.json",
    "nutrition_db": "databases/nutrition_db.json",
    "regional_presets": "databases/regional_presets.json",
    "water_types": "databases/water_types.json",
    "growth_log": "logs/growth_log.json",
}

# ==================== MANUAL OVERRIDE ====================
MANUAL_OVERRIDE = {
    "digital_sliders_enabled": True,
    "physical_panel_enabled": True,
    "auto_reset_override_minutes": 240,  # 4 hours
    "require_confirmation_for_critical": True,
}

# ==================== REGIONAL PRESET (current) ====================
REGION = "temperate_coastal"  # Options: tropical, temperate_coastal, arid, cold, custom

# ==================== FISH TUB / AQUACULTURE ====================
FISH_TUB = {
    "enabled": True,
    "species": "tilapia",
    "water_temp_min_c": 24,
    "water_temp_max_c": 30,
    "water_temp_ideal_c": 27,
    "ph_min": 6.5,
    "ph_max": 8.0,
    "ammonia_max_ppm": 0.5,
    "feeding_interval_hours": 4,
    "auto_feeder_pin": 28,
}

# ==================== FREQUENCY EXPERIMENT (Optional) ====================
FREQUENCY_EXPERIMENT = {
    "enabled": False,  # Set True to enable VFD experiments
    "vfd_controlled_device": "airflow_fan",
    "frequency_range_hz": [45, 50, 55, 60],
    "duration_days_per_freq": 7,
    "log_correlation_with_yield": True,
}

# ==================== SAFETY ====================
SAFETY = {
    "emergency_stop_pin": 5,  # Physical red button
    "max_temp_before_shutdown_c": 45,
    "max_humidity_before_alert": 95,
    "min_battery_soc_before_alert": 20,
    "alert_email": "your-email@example.com",  # Optional, if internet available
}

# ==================== END OF CONFIG ====================
