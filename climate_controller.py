"""
ENKOMOS - Climate Controller
Energy & Keystone Operating Management Operating System

Manages temperature, humidity, CO2, and VPD across all zones.
Autonomous mode with manual override support.
"""

import time
import math
import threading
from datetime import datetime
from typing import Dict, Optional, Tuple

# Import configuration and database
try:
    import config
except ImportError:
    print("[ERROR] config.py not found. Using fallback values.")
    # Fallback configuration
    class config:
        ZONES = {1: {"name": "Zone1"}, 2: {"name": "Zone2"}, 3: {"name": "Zone3"},
                 4: {"name": "Zone4"}, 5: {"name": "Zone5"}, 6: {"name": "Zone6"}}
        CLIMATE_THRESHOLDS = {}
        ACTUATORS = {}
        MANUAL_OVERRIDE = {"auto_reset_override_minutes": 240}

try:
    from database_manager import DatabaseManager
except ImportError:
    print("[WARN] database_manager.py not found. Running without database.")
    DatabaseManager = None


# ==================== VPD CALCULATION ====================

def calculate_vpd(temp_c: float, humidity_percent: float) -> float:
    """
    Calculate Vapor Pressure Deficit (kPa)
    VPD = saturation_vapor_pressure - actual_vapor_pressure
    """
    # Saturation vapor pressure (Tetens formula)
    svp = 0.6108 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    # Actual vapor pressure
    avp = svp * (humidity_percent / 100.0)
    # VPD in kPa
    vpd = svp - avp
    return round(vpd, 2)


def calculate_dew_point(temp_c: float, humidity_percent: float) -> float:
    """Calculate dew point temperature (°C)"""
    a = 17.27
    b = 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity_percent / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    return round(dew_point, 1)


# ==================== ZONE CLIMATE STATE ====================

class ZoneClimate:
    """Represents climate state for a single zone"""
    
    def __init__(self, zone_id: int, thresholds: Dict):
        self.zone_id = zone_id
        self.thresholds = thresholds
        self.current_temp = 20.0
        self.current_humidity = 60.0
        self.current_co2 = 450
        self.current_vpd = 0.0
        self.manual_override = False
        self.override_until = 0  # timestamp
        self.manual_temp_target = None
        self.manual_humidity_target = None
        
    def update_sensors(self, temp: float, humidity: float, co2: int):
        """Update current readings from sensors"""
        self.current_temp = temp
        self.current_humidity = humidity
        self.current_co2 = co2
        self.current_vpd = calculate_vpd(temp, humidity)
        
    def needs_heating(self) -> bool:
        """Check if zone needs heating"""
        if self.manual_override and time.time() < self.override_until:
            return False  # Manual mode overrides AI
        return self.current_temp < self.thresholds.get("temp_min_c", 18)
    
    def needs_cooling(self) -> bool:
        """Check if zone needs cooling"""
        if self.manual_override and time.time() < self.override_until:
            return False
        return self.current_temp > self.thresholds.get("temp_max_c", 28)
    
    def needs_humidifying(self) -> bool:
        """Check if zone needs more humidity"""
        if self.manual_override and time.time() < self.override_until:
            return False
        return self.current_humidity < self.thresholds.get("humidity_min_percent", 50)
    
    def needs_dehumidifying(self) -> bool:
        """Check if zone needs less humidity"""
        if self.manual_override and time.time() < self.override_until:
            return False
        return self.current_humidity > self.thresholds.get("humidity_max_percent", 80)
    
    def needs_co2(self) -> bool:
        """Check if zone needs CO₂ injection"""
        if self.manual_override and time.time() < self.override_until:
            return False
        return self.current_co2 < self.thresholds.get("co2_ppm_min", 400)
    
    def is_vpd_optimal(self) -> bool:
        """Check if VPD is within ideal range"""
        vpd_ideal = self.thresholds.get("vpd_ideal_kpa", 0.8)
        return abs(self.current_vpd - vpd_ideal) < 0.2
    
    def set_manual_override(self, duration_minutes: int = 240):
        """Activate manual override for specified duration"""
        self.manual_override = True
        self.override_until = time.time() + (duration_minutes * 60)
        
    def clear_manual_override(self):
        """Clear manual override and return to AI control"""
        self.manual_override = False
        self.override_until = 0
        self.manual_temp_target = None
        self.manual_humidity_target = None
        
    def get_status(self) -> Dict:
        """Return current status for UI"""
        return {
            "zone": self.zone_id,
            "temp_c": self.current_temp,
            "humidity": self.current_humidity,
            "co2_ppm": self.current_co2,
            "vpd_kpa": self.current_vpd,
            "needs_heating": self.needs_heating(),
            "needs_cooling": self.needs_cooling(),
            "needs_humidifying": self.needs_humidifying(),
            "needs_dehumidifying": self.needs_dehumidifying(),
            "manual_override": self.manual_override,
            "override_remaining_min": max(0, int((self.override_until - time.time()) / 60))
        }


# ==================== MAIN CLIMATE CONTROLLER ====================

class ClimateController:
    """Main controller for all zones"""
    
    def __init__(self):
        self.zones: Dict[int, ZoneClimate] = {}
        self._init_zones()
        self.running = False
        self.control_thread = None
        self.db = DatabaseManager() if DatabaseManager else None
        
        # Actuator states (simulated - replace with GPIO)
        self.actuator_states = {
            "heater": False,
            "cooler": False,
            "humidifier": False,
            "dehumidifier": False,
            "co2_injector": False,
            "exhaust_fan": False,
        }
        
    def _init_zones(self):
        """Initialize all zones from config"""
        for zone_id, zone_info in config.ZONES.items():
            if not zone_info.get("active", True):
                continue
            thresholds = config.CLIMATE_THRESHOLDS.get(zone_id, {})
            self.zones[zone_id] = ZoneClimate(zone_id, thresholds)
        print(f"[INFO] Initialized {len(self.zones)} climate zones")
    
    def update_zone_sensors(self, zone_id: int, temp: float, humidity: float, co2: int):
        """Call this with real sensor data periodically"""
        if zone_id in self.zones:
            self.zones[zone_id].update_sensors(temp, humidity, co2)
            
    def get_zone_status(self, zone_id: int) -> Optional[Dict]:
        """Get status for a specific zone"""
        if zone_id in self.zones:
            return self.zones[zone_id].get_status()
        return None
    
    def get_all_zones_status(self) -> Dict[int, Dict]:
        """Get status for all zones"""
        return {zid: zone.get_status() for zid, zone in self.zones.items()}
    
    def set_manual_override(self, zone_id: int, duration_minutes: int = 240):
        """Set manual override for a zone"""
        if zone_id in self.zones:
            self.zones[zone_id].set_manual_override(duration_minutes)
            print(f"[INFO] Zone {zone_id} manual override for {duration_minutes} min")
            
    def clear_manual_override(self, zone_id: int):
        """Clear manual override for a zone"""
        if zone_id in self.zones:
            self.zones[zone_id].clear_manual_override()
            print(f"[INFO] Zone {zone_id} manual override cleared")
    
    def _control_actuator(self, actuator_name: str, state: bool):
        """Send command to physical actuator (override with actual GPIO)"""
        if state != self.actuator_states.get(actuator_name):
            self.actuator_states[actuator_name] = state
            # TODO: Replace with actual GPIO write
            # GPIO.output(config.ACTUATORS[actuator_name], state)
            print(f"[ACTUATOR] {actuator_name} -> {'ON' if state else 'OFF'}")
    
    def _control_zone(self, zone: ZoneClimate):
        """Make control decisions for a single zone"""
        
        # Temperature control
        if zone.needs_heating():
            self._control_actuator(f"heater_zone{zone.zone_id}", True)
        elif zone.needs_cooling():
            self._control_actuator(f"cooler_zone{zone.zone_id}", True)
            self._control_actuator(f"exhaust_fan", True)
        else:
            self._control_actuator(f"heater_zone{zone.zone_id}", False)
            self._control_actuator(f"cooler_zone{zone.zone_id}", False)
            self._control_actuator(f"exhaust_fan", False)
        
        # Humidity control
        if zone.needs_humidifying():
            self._control_actuator(f"humidifier_zone{zone.zone_id}", True)
        elif zone.needs_dehumidifying():
            self._control_actuator(f"dehumidifier_zone{zone.zone_id}", True)
            self._control_actuator(f"exhaust_fan", True)
        else:
            self._control_actuator(f"humidifier_zone{zone.zone_id}", False)
            self._control_actuator(f"dehumidifier_zone{zone.zone_id}", False)
        
        # CO₂ control
        if zone.needs_co2():
            self._control_actuator(f"co2_injector_zone{zone.zone_id}", True)
        else:
            self._control_actuator(f"co2_injector_zone{zone.zone_id}", False)
    
    def _control_loop(self):
        """Main control loop running in separate thread"""
        while self.running:
            for zone in self.zones.values():
                self._control_zone(zone)
            
            # Log to database if available
            if self.db:
                status = self.get_all_zones_status()
                for zone_id, data in status.items():
                    self.db.log_growth_entry(
                        zone=zone_id,
                        crop="unknown",  # Should come from zone config
                        measurements={
                            "temp": data["temp_c"],
                            "humidity": data["humidity"],
                            "co2": data["co2_ppm"],
                            "vpd": data["vpd_kpa"]
                        }
                    )
            
            time.sleep(config.SYSTEM.get("ai_interval_seconds", 30))
    
    def start(self):
        """Start the climate controller"""
        if self.running:
            print("[WARN] Climate controller already running")
            return
        self.running = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        print("[INFO] Climate controller started")
    
    def stop(self):
        """Stop the climate controller"""
        self.running = False
        if self.control_thread:
            self.control_thread.join(timeout=5)
        print("[INFO] Climate controller stopped")
    
    def emergency_shutdown(self):
        """Emergency stop - turn off all actuators"""
        for actuator in self.actuator_states:
            self._control_actuator(actuator, False)
        print("[ALERT] EMERGENCY SHUTDOWN - all actuators OFF")


# ==================== COMMAND LINE TEST ====================

if __name__ == "__main__":
    print("=== ENKOMOS Climate Controller Test ===")
    
    controller = ClimateController()
    
    # Simulate sensor readings
    print("\n[TEST] Simulating Zone 1 at 30°C, 40% humidity")
    controller.update_zone_sensors(1, 30.0, 40.0, 400)
    
    status = controller.get_zone_status(1)
    print(f"Zone 1 status: {status}")
    
    print(f"\nVPD calculation test: 25°C, 60% -> {calculate_vpd(25, 60)} kPa")
    print(f"Dew point test: 25°C, 60% -> {calculate_dew_point(25, 60)}°C")
    
    print("\n[TEST] Starting controller (will run 3 cycles then stop)")
    controller.start()
    time.sleep(10)  # Let it run a few cycles
    controller.stop()
    
    print("\nClimate Controller ready.")
