"""
ENKOMOS - Energy Controller
Energy & Keystone Operating Management Operating System

Manages all power sources: solar PV, wind turbine, biogas generator.
Controls sodium-ion battery bank (AC coupled).
Logs AC frequency for growth research.
"""

import time
import threading
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

try:
    import config
except ImportError:
    print("[ERROR] config.py not found. Using fallback.")
    class config:
        ENERGY = {
            "primary_source": "solar",
            "battery_capacity_kwh": 100,
            "battery_min_soc_percent": 30,
            "solar_pv_power_kw": 50,
            "wind_turbine_power_kw": 10,
            "biogas_power_kw": 20,
            "frequency_logging": True
        }
        SYSTEM = {"ai_interval_seconds": 30}

try:
    from database_manager import DatabaseManager
except ImportError:
    DatabaseManager = None


# ==================== ENUMS ====================

class PowerSource(Enum):
    SOLAR = "solar"
    WIND = "wind"
    BIOGAS = "biogas"
    BATTERY = "battery"
    GRID = "grid"  # Fallback only


# ==================== BATTERY MANAGER ====================

class SodiumIonBattery:
    """Sodium-ion battery bank management (AC coupled)"""
    
    def __init__(self, capacity_kwh: float = 100.0):
        self.capacity_kwh = capacity_kwh
        self.current_soc_percent = 80.0  # State of Charge (0-100)
        self.current_charge_kw = 0.0
        self.current_discharge_kw = 0.0
        self.temperature_c = 25.0
        self.cycles = 0
        
        # Thresholds from config
        self.min_soc = config.ENERGY.get("battery_min_soc_percent", 30)
        self.max_soc = 95  # Sodium-ion safe max
        
    def update_soc(self, delta_kwh: float):
        """Update state of charge based on energy in/out"""
        delta_percent = (delta_kwh / self.capacity_kwh) * 100
        self.current_soc_percent += delta_percent
        self.current_soc_percent = max(0, min(100, self.current_soc_percent))
        
    def can_discharge(self, required_kw: float) -> bool:
        """Check if battery can supply required power"""
        # Reserve minimum SOC
        usable_percent = self.current_soc_percent - self.min_soc
        usable_kwh = (usable_percent / 100) * self.capacity_kwh
        # Rough estimate: can supply required_kw for at least 1 hour
        return usable_kwh > required_kw
    
    def can_charge(self) -> bool:
        """Check if battery can accept more charge"""
        return self.current_soc_percent < self.max_soc
    
    def get_available_kwh(self) -> float:
        """Get usable energy (above min SOC)"""
        usable_percent = max(0, self.current_soc_percent - self.min_soc)
        return (usable_percent / 100) * self.capacity_kwh
    
    def get_status(self) -> Dict:
        return {
            "soc_percent": round(self.current_soc_percent, 1),
            "available_kwh": round(self.get_available_kwh(), 1),
            "temperature_c": self.temperature_c,
            "charge_kw": self.current_charge_kw,
            "discharge_kw": self.current_discharge_kw,
            "cycles": self.cycles
        }


# ==================== POWER SOURCE CONTROLLERS ====================

class SolarController:
    """Solar PV array management"""
    
    def __init__(self, rated_kw: float = 50.0):
        self.rated_kw = rated_kw
        self.current_output_kw = 0.0
        self.irradiance_w_m2 = 0.0
        self.temperature_c = 25.0
        
    def update(self, irradiance_w_m2: float, panel_temp_c: float = 25.0):
        """Update based on real sensor data"""
        self.irradiance_w_m2 = irradiance_w_m2
        self.temperature_c = panel_temp_c
        
        # Simple model: output proportional to irradiance
        # 1000 W/m2 = full rated power
        efficiency_temp = 1 - (panel_temp_c - 25) * 0.004  # 0.4% loss per degree above 25
        self.current_output_kw = self.rated_kw * (irradiance_w_m2 / 1000) * max(0, efficiency_temp)
        self.current_output_kw = max(0, min(self.rated_kw, self.current_output_kw))
        
    def get_status(self) -> Dict:
        return {
            "output_kw": round(self.current_output_kw, 1),
            "irradiance_w_m2": self.irradiance_w_m2,
            "temperature_c": self.temperature_c,
            "efficiency_percent": round((self.current_output_kw / self.rated_kw) * 100, 1) if self.rated_kw else 0
        }


class WindController:
    """Wind turbine management"""
    
    def __init__(self, rated_kw: float = 10.0):
        self.rated_kw = rated_kw
        self.current_output_kw = 0.0
        self.wind_speed_ms = 0.0
        
    def update(self, wind_speed_ms: float):
        """Update based on anemometer data"""
        self.wind_speed_ms = wind_speed_ms
        
        # Simplified power curve
        cut_in = 3.0      # m/s - starts producing
        rated_wind = 12.0  # m/s - full power
        cut_out = 25.0     # m/s - stops for safety
        
        if wind_speed_ms < cut_in or wind_speed_ms > cut_out:
            self.current_output_kw = 0
        elif wind_speed_ms >= rated_wind:
            self.current_output_kw = self.rated_kw
        else:
            # Cubic relationship between cut_in and rated_wind
            ratio = (wind_speed_ms - cut_in) / (rated_wind - cut_in)
            self.current_output_kw = self.rated_kw * (ratio ** 3)
            
    def get_status(self) -> Dict:
        return {
            "output_kw": round(self.current_output_kw, 1),
            "wind_speed_ms": self.wind_speed_ms,
            "efficiency_percent": round((self.current_output_kw / self.rated_kw) * 100, 1) if self.rated_kw else 0
        }


class BiogasController:
    """Biogas generator management (CHP unit)"""
    
    def __init__(self, rated_kw: float = 20.0):
        self.rated_kw = rated_kw
        self.current_output_kw = 0.0
        self.fuel_level_percent = 80.0
        self.running = False
        
    def update_fuel_level(self, percent: float):
        """Update from digester sensors"""
        self.fuel_level_percent = max(0, min(100, percent))
        
    def start(self):
        """Start biogas generator"""
        if self.fuel_level_percent > 10:
            self.running = True
            self.current_output_kw = self.rated_kw
            print(f"[BIOGAS] Generator started - fuel: {self.fuel_level_percent}%")
        else:
            print(f"[BIOGAS] Cannot start - low fuel: {self.fuel_level_percent}%")
            
    def stop(self):
        """Stop biogas generator"""
        self.running = False
        self.current_output_kw = 0
        print("[BIOGAS] Generator stopped")
        
    def should_run(self, battery_soc: float, load_kw: float) -> bool:
        """Determine if generator should run based on conditions"""
        # Run if battery low AND load is high
        if battery_soc < 30 and load_kw > 5:
            return True
        # Run if fuel is abundant (avoid waste)
        if self.fuel_level_percent > 80 and battery_soc < 70:
            return True
        return False
    
    def get_status(self) -> Dict:
        return {
            "output_kw": round(self.current_output_kw, 1),
            "fuel_level_percent": self.fuel_level_percent,
            "running": self.running
        }


# ==================== AC FREQUENCY LOGGER ====================

class ACFrequencyLogger:
    """Logs AC line frequency for growth research correlation"""
    
    def __init__(self):
        self.enabled = config.ENERGY.get("frequency_logging", True)
        self.current_frequency_hz = 50.0  # Portugal standard
        self.history: List[Dict] = []
        self.db = DatabaseManager() if DatabaseManager else None
        
    def update(self, measured_freq_hz: float):
        """Update from frequency sensor"""
        self.current_frequency_hz = measured_freq_hz
        
        if self.enabled:
            self.history.append({
                "timestamp": datetime.now().isoformat(),
                "frequency_hz": measured_freq_hz
            })
            # Keep last 1000 readings
            if len(self.history) > 1000:
                self.history = self.history[-1000:]
                
            # Log to database
            if self.db:
                self.db.log_growth_entry(
                    zone=0,  # Zone 0 = system
                    crop="ac_frequency",
                    measurements={"frequency_hz": measured_freq_hz}
                )
                
    def get_average(self, minutes: int = 60) -> float:
        """Get average frequency over last N minutes"""
        if not self.history:
            return 50.0
            
        cutoff = datetime.now().timestamp() - (minutes * 60)
        recent = [h["frequency_hz"] for h in self.history 
                  if datetime.fromisoformat(h["timestamp"]).timestamp() > cutoff]
        if not recent:
            return 50.0
        return sum(recent) / len(recent)
    
    def get_status(self) -> Dict:
        return {
            "enabled": self.enabled,
            "current_frequency_hz": self.current_frequency_hz,
            "average_1h_hz": self.get_average(60),
            "average_24h_hz": self.get_average(1440)
        }


# ==================== MAIN ENERGY CONTROLLER ====================

class EnergyController:
    """Master energy controller - balances all sources and battery"""
    
    def __init__(self):
        # Initialize components
        self.battery = SodiumIonBattery(config.ENERGY.get("battery_capacity_kwh", 100))
        self.solar = SolarController(config.ENERGY.get("solar_pv_power_kw", 50))
        self.wind = WindController(config.ENERGY.get("wind_turbine_power_kw", 10))
        self.biogas = BiogasController(config.ENERGY.get("biogas_power_kw", 20))
        self.frequency_logger = ACFrequencyLogger()
        
        self.primary_source = config.ENERGY.get("primary_source", "solar")
        self.current_load_kw = 0.0
        self.total_generation_kw = 0.0
        self.running = False
        self.control_thread = None
        self.db = DatabaseManager() if DatabaseManager else None
        
    def update_sensors(self, 
                       irradiance_w_m2: float = 500,
                       panel_temp_c: float = 25,
                       wind_speed_ms: float = 5,
                       battery_temp_c: float = 25,
                       ac_frequency_hz: float = 50.0,
                       load_kw: float = 0.0):
        """Update all energy sensors"""
        self.solar.update(irradiance_w_m2, panel_temp_c)
        self.wind.update(wind_speed_ms)
        self.battery.temperature_c = battery_temp_c
        self.frequency_logger.update(ac_frequency_hz)
        self.current_load_kw = load_kw
        
        # Calculate total generation
        self.total_generation_kw = self.solar.current_output_kw + self.wind.current_output_kw
        
        # If biogas is running, add its output
        if self.biogas.running:
            self.total_generation_kw += self.biogas.current_output_kw
            
    def _balance_power(self):
        """Core power balancing logic"""
        power_balance = self.total_generation_kw - self.current_load_kw
        
        if power_balance > 0:
            # Excess power: charge battery
            if self.battery.can_charge():
                charge_kw = min(power_balance, 50)  # Max charge rate 50kW
                self.battery.current_charge_kw = charge_kw
                self.battery.update_soc(charge_kw / 3600)  # Convert kW to kWh per second (simplified)
                print(f"[ENERGY] Charging battery: {charge_kw:.1f} kW")
            else:
                # Battery full - dump excess to resistive load (water heater, compost accelerator)
                print(f"[ENERGY] Battery full - dumping {power_balance:.1f} kW")
                
        elif power_balance < 0:
            # Deficit: discharge battery or start biogas
            deficit = abs(power_balance)
            
            if self.battery.can_discharge(deficit):
                self.battery.current_discharge_kw = deficit
                self.battery.update_soc(-deficit / 3600)
                print(f"[ENERGY] Discharging battery: {deficit:.1f} kW")
            else:
                # Battery insufficient - start biogas if available
                if self.biogas.should_run(self.battery.current_soc_percent, deficit):
                    self.biogas.start()
                    # Recalculate with biogas
                    self.total_generation_kw += self.biogas.current_output_kw
                else:
                    # Critical: reduce load or alert
                    print(f"[ALERT] Energy deficit! Battery at {self.battery.current_soc_percent:.1f}%")
                    
        else:
            # Perfect balance
            self.battery.current_charge_kw = 0
            self.battery.current_discharge_kw = 0
            
        # Stop biogas if no longer needed
        if self.biogas.running and not self.biogas.should_run(self.battery.current_soc_percent, self.current_load_kw):
            self.biogas.stop()
            
    def _control_loop(self):
        """Main control loop"""
        while self.running:
            self._balance_power()
            
            # Log to database
            if self.db:
                self.db.log_growth_entry(
                    zone=0,
                    crop="energy_system",
                    measurements={
                        "solar_kw": self.solar.current_output_kw,
                        "wind_kw": self.wind.current_output_kw,
                        "biogas_kw": self.biogas.current_output_kw if self.biogas.running else 0,
                        "load_kw": self.current_load_kw,
                        "battery_soc": self.battery.current_soc_percent,
                        "ac_frequency": self.frequency_logger.current_frequency_hz
                    }
                )
                
            time.sleep(config.SYSTEM.get("ai_interval_seconds", 30))
    
    def start(self):
        """Start energy controller"""
        if self.running:
            return
        self.running = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        print("[INFO] Energy controller started")
        
    def stop(self):
        """Stop energy controller"""
        self.running = False
        if self.biogas.running:
            self.biogas.stop()
        print("[INFO] Energy controller stopped")
        
    def emergency_shutdown(self):
        """Emergency: stop all generation and disconnect load"""
        self.biogas.stop()
        self.battery.current_discharge_kw = 0
        print("[ALERT] Energy emergency shutdown")
        
    def get_status(self) -> Dict:
        return {
            "generation": {
                "solar": self.solar.get_status(),
                "wind": self.wind.get_status(),
                "biogas": self.biogas.get_status(),
                "total_kw": round(self.total_generation_kw, 1)
            },
            "battery": self.battery.get_status(),
            "load_kw": round(self.current_load_kw, 1),
            "ac_frequency": self.frequency_logger.get_status(),
            "primary_source": self.primary_source
        }


# ==================== TEST ====================

if __name__ == "__main__":
    print("=== ENKOMOS Energy Controller Test ===")
    
    controller = EnergyController()
    
    # Simulate a sunny day with load
    print("\n[TEST] Simulating midday - high solar, medium load")
    controller.update_sensors(
        irradiance_w_m2=900,
        panel_temp_c=35,
        wind_speed_ms=4,
        load_kw=30
    )
    controller.start()
    time.sleep(5)
    
    print("\nStatus:", controller.get_status())
    
    # Simulate night - low solar, high load
    print("\n[TEST] Simulating night - no solar, high load")
    controller.update_sensors(
        irradiance_w_m2=0,
        panel_temp_c=20,
        wind_speed_ms=2,
        load_kw=35
    )
    time.sleep(5)
    
    controller.stop()
    print("\nEnergy Controller ready.")
