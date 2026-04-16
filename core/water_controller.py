"""
ENKOMOS - Water Controller
Energy & Keystone Operating Management Operating System

Manages structured/charged water, mist system, fish tub, and irrigation.
"""

import time
import threading
from typing import Dict, Optional, List
from datetime import datetime

try:
    import config
except ImportError:
    print("[ERROR] config.py not found. Using fallback.")
    class config:
        STRUCTURED_WATER = {"enabled": True, "orp_target_mv": 300, "orp_min_mv": 200, "orp_max_mv": 400}
        FISH_TUB = {"enabled": True, "water_temp_min_c": 24, "water_temp_max_c": 30}
        ACTUATORS = {"structured_water_valve": 23, "water_pump_fish_tub": 26, "water_pump_irrigation": 27}
        SYSTEM = {"ai_interval_seconds": 30}

try:
    from database_manager import DatabaseManager
except ImportError:
    DatabaseManager = None


# ==================== WATER QUALITY READING ====================

class WaterQuality:
    """Stores water quality measurements"""
    
    def __init__(self):
        self.orp_mv = 250      # Oxidation Reduction Potential
        self.ph = 7.0
        self.do_mgl = 6.0      # Dissolved Oxygen
        self.ec_us_cm = 1200   # Electrical Conductivity
        self.temperature_c = 25.0
        self.ammonia_ppm = 0.0
        self.nitrite_ppm = 0.0
        self.nitrate_ppm = 0.0
        
    def update(self, orp=None, ph=None, do=None, ec=None, temp=None, ammonia=None, nitrite=None, nitrate=None):
        """Update readings from sensors"""
        if orp is not None:
            self.orp_mv = orp
        if ph is not None:
            self.ph = ph
        if do is not None:
            self.do_mgl = do
        if ec is not None:
            self.ec_us_cm = ec
        if temp is not None:
            self.temperature_c = temp
        if ammonia is not None:
            self.ammonia_ppm = ammonia
        if nitrite is not None:
            self.nitrite_ppm = nitrite
        if nitrate is not None:
            self.nitrate_ppm = nitrate
            
    def is_orp_optimal(self) -> bool:
        """Check if ORP is in target range for structured water"""
        target = config.STRUCTURED_WATER.get("orp_target_mv", 300)
        margin = 50
        return abs(self.orp_mv - target) <= margin
    
    def is_ph_optimal(self, crop_ph_min=6.0, crop_ph_max=7.0) -> bool:
        """Check if pH is in range"""
        return crop_ph_min <= self.ph <= crop_ph_max
    
    def is_do_safe(self, min_do=4.0) -> bool:
        """Check if dissolved oxygen is safe for fish"""
        return self.do_mgl >= min_do
    
    def get_status(self) -> Dict:
        """Return all readings as dict"""
        return {
            "orp_mv": self.orp_mv,
            "ph": self.ph,
            "do_mgl": self.do_mgl,
            "ec_us_cm": self.ec_us_cm,
            "temperature_c": self.temperature_c,
            "ammonia_ppm": self.ammonia_ppm,
            "nitrite_ppm": self.nitrite_ppm,
            "nitrate_ppm": self.nitrate_ppm,
            "orp_optimal": self.is_orp_optimal(),
        }


# ==================== STRUCTURED WATER CONTROLLER ====================

class StructuredWaterController:
    """Manages structured/charged water production and monitoring"""
    
    def __init__(self):
        self.enabled = config.STRUCTURED_WATER.get("enabled", True)
        self.quality = WaterQuality()
        self.bypass_active = False
        self.structuring_active = False
        
    def update_sensors(self, quality: WaterQuality):
        """Update from physical sensors"""
        self.quality = quality
        
    def should_activate_structuring(self) -> bool:
        """Determine if water needs structuring"""
        if not self.enabled:
            return False
        # Activate if ORP is too low
        if self.quality.orp_mv < config.STRUCTURED_WATER.get("orp_min_mv", 200):
            return True
        return False
    
    def should_bypass(self) -> bool:
        """Determine if structured water should be bypassed"""
        if self.quality.orp_mv > config.STRUCTURED_WATER.get("orp_max_mv", 400):
            return True
        return False
    
    def control(self):
        """Control structured water system"""
        if self.should_activate_structuring() and not self.structuring_active:
            self._activate_structuring()
        elif not self.should_activate_structuring() and self.structuring_active:
            self._deactivate_structuring()
            
        if self.should_bypass() and not self.bypass_active:
            self._open_bypass()
        elif not self.should_bypass() and self.bypass_active:
            self._close_bypass()
    
    def _activate_structuring(self):
        """Turn on structured water unit (vortex/magnetic/electrolytic)"""
        self.structuring_active = True
        # TODO: GPIO.output(config.ACTUATORS.get("structured_water_valve"), True)
        print(f"[WATER] Structured water activated - ORP: {self.quality.orp_mv} mV")
        
    def _deactivate_structuring(self):
        """Turn off structured water unit"""
        self.structuring_active = False
        print(f"[WATER] Structured water deactivated - ORP: {self.quality.orp_mv} mV")
        
    def _open_bypass(self):
        """Open bypass valve (use normal water)"""
        self.bypass_active = True
        print(f"[WATER] Bypass opened - ORP too high: {self.quality.orp_mv} mV")
        
    def _close_bypass(self):
        """Close bypass valve (use structured water)"""
        self.bypass_active = False
        print(f"[WATER] Bypass closed - ORP optimal")
        
    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "structuring_active": self.structuring_active,
            "bypass_active": self.bypass_active,
            "quality": self.quality.get_status()
        }


# ==================== MIST CONTROLLER ====================

class MistController:
    """Controls misting system for all zones and areas"""
    
    MODES = ["open_area", "covered_area", "inside_greenhouse"]
    
    def __init__(self):
        self.zone_mist_active: Dict[int, bool] = {}
        self.mode_active: Dict[str, bool] = {mode: False for mode in self.MODES}
        
    def should_mist_zone(self, zone_id: int, humidity: float, target_humidity: float) -> bool:
        """Determine if zone needs misting"""
        return humidity < (target_humidity - 5)  # Mist when 5% below target
    
    def control_zone(self, zone_id: int, humidity: float, target_humidity: float):
        """Control mist for a specific zone"""
        should = self.should_mist_zone(zone_id, humidity, target_humidity)
        if should and not self.zone_mist_active.get(zone_id, False):
            self._activate_zone_mist(zone_id)
        elif not should and self.zone_mist_active.get(zone_id, False):
            self._deactivate_zone_mist(zone_id)
            
    def _activate_zone_mist(self, zone_id: int):
        self.zone_mist_active[zone_id] = True
        print(f"[MIST] Zone {zone_id} mist ON")
        
    def _deactivate_zone_mist(self, zone_id: int):
        self.zone_mist_active[zone_id] = False
        print(f"[MIST] Zone {zone_id} mist OFF")
        
    def get_status(self) -> Dict:
        return {
            "zone_mist_active": self.zone_mist_active,
            "mode_active": self.mode_active
        }


# ==================== FISH TUB CONTROLLER ====================

class FishTubController:
    """Manages aquaculture parameters"""
    
    def __init__(self):
        self.enabled = config.FISH_TUB.get("enabled", True)
        self.water_quality = WaterQuality()
        self.feeder_last_time = 0
        self.feeder_active = False
        
    def update_sensors(self, quality: WaterQuality):
        self.water_quality = quality
        
    def needs_heating(self) -> bool:
        """Check if fish water needs heating"""
        min_temp = config.FISH_TUB.get("water_temp_min_c", 24)
        return self.water_quality.temperature_c < min_temp
    
    def needs_cooling(self) -> bool:
        """Check if fish water needs cooling"""
        max_temp = config.FISH_TUB.get("water_temp_max_c", 30)
        return self.water_quality.temperature_c > max_temp
    
    def needs_aeration(self) -> bool:
        """Check if dissolved oxygen is too low"""
        return self.water_quality.do_mgl < 4.0
    
    def needs_water_change(self) -> bool:
        """Check if ammonia or nitrite is toxic"""
        return self.water_quality.ammonia_ppm > 0.5 or self.water_quality.nitrite_ppm > 1.0
    
    def should_feed(self) -> bool:
        """Check if it's time to auto-feed"""
        if not self.enabled:
            return False
        interval = config.FISH_TUB.get("feeding_interval_hours", 4)
        now = time.time()
        if now - self.feeder_last_time >= interval * 3600:
            self.feeder_last_time = now
            return True
        return False
    
    def control(self):
        """Run fish tub control logic"""
        if self.needs_heating():
            print(f"[FISH] Water heating needed - temp: {self.water_quality.temperature_c}°C")
        if self.needs_aeration():
            print(f"[FISH] Aeration needed - DO: {self.water_quality.do_mgl} mg/L")
        if self.needs_water_change():
            print(f"[FISH] WATER CHANGE NEEDED - Ammonia: {self.water_quality.ammonia_ppm} ppm")
        if self.should_feed():
            self._trigger_feeder()
            
    def _trigger_feeder(self):
        """Activate auto-feeder"""
        self.feeder_active = True
        print(f"[FISH] Auto-feeder triggered")
        # TODO: GPIO.output(config.ACTUATORS.get("auto_feeder_pin"), True)
        time.sleep(2)
        # TODO: GPIO.output(config.ACTUATORS.get("auto_feeder_pin"), False)
        self.feeder_active = False
        
    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "water_quality": self.water_quality.get_status(),
            "needs_heating": self.needs_heating(),
            "needs_aeration": self.needs_aeration(),
            "needs_water_change": self.needs_water_change(),
        }


# ==================== MAIN WATER CONTROLLER ====================

class WaterController:
    """Master water controller - integrates all subsystems"""
    
    def __init__(self):
        self.structured_water = StructuredWaterController()
        self.mist = MistController()
        self.fish_tub = FishTubController()
        self.running = False
        self.control_thread = None
        self.db = DatabaseManager() if DatabaseManager else None
        
    def update_all_sensors(self, 
                          water_quality: WaterQuality = None,
                          zone_humidity: Dict[int, float] = None):
        """Update all sensor readings"""
        if water_quality:
            self.structured_water.update_sensors(water_quality)
            self.fish_tub.update_sensors(water_quality)
            
    def _control_loop(self):
        """Main control loop"""
        while self.running:
            # Control structured water
            self.structured_water.control()
            
            # Control fish tub
            self.fish_tub.control()
            
            # Log to database
            if self.db:
                self.db.log_growth_entry(
                    zone=0,  # Zone 0 = water system
                    crop="water_quality",
                    measurements=self.structured_water.get_status()["quality"]
                )
            
            time.sleep(config.SYSTEM.get("ai_interval_seconds", 30))
    
    def start(self):
        """Start water controller"""
        if self.running:
            return
        self.running = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        print("[INFO] Water controller started")
        
    def stop(self):
        """Stop water controller"""
        self.running = False
        print("[INFO] Water controller stopped")
        
    def get_status(self) -> Dict:
        return {
            "structured_water": self.structured_water.get_status(),
            "mist": self.mist.get_status(),
            "fish_tub": self.fish_tub.get_status()
        }


# ==================== TEST ====================

if __name__ == "__main__":
    print("=== ENKOMOS Water Controller Test ===")
    
    controller = WaterController()
    
    # Simulate water quality
    test_quality = WaterQuality()
    test_quality.update(orp_mv=180, ph=6.8, do_mgl=5.5, temperature_c=26)
    
    controller.update_all_sensors(water_quality=test_quality)
    controller.start()
    
    time.sleep(5)
    
    print("\nStatus:", controller.get_status())
    
    controller.stop()
    print("\nWater Controller ready.")
