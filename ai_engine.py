"""
ENKOMOS - AI Engine (Master Decision Core)
Energy & Keystone Operating Management Operating System

Integrates all controllers: Climate, Water, Energy.
Makes autonomous decisions. Respects manual override.
Logs everything. Learns from patterns.
"""

import time
import threading
import sys
import os
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field

# Add paths for imports (temporary - will be fixed after folder reorganization)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ImportError:
    print("[ERROR] config.py not found. Running in demo mode.")
    # Fallback config for demo
    class config:
        SYSTEM = {"mode": "autonomous", "ai_interval_seconds": 30, "log_level": "INFO"}
        ZONES = {1: {"name": "Zone1", "active": True}, 2: {"name": "Zone2", "active": True}}
        MANUAL_OVERRIDE = {"auto_reset_override_minutes": 240, "require_confirmation_for_critical": True}
        SAFETY = {"max_temp_before_shutdown_c": 45, "emergency_stop_pin": 5}

try:
    from climate_controller import ClimateController
    from water_controller import WaterController
    from energy_controller import EnergyController
    from database_manager import DatabaseManager
except ImportError as e:
    print(f"[ERROR] Missing module: {e}")
    print("[WARN] Running in limited mode. Some features disabled.")
    ClimateController = None
    WaterController = None
    EnergyController = None
    DatabaseManager = None


# ==================== DATA CLASSES ====================

@dataclass
class SystemDecision:
    """Record of an AI decision"""
    timestamp: str
    decision_type: str  # climate, water, energy, emergency
    zone: int
    action: str
    reason: str
    manual_override: bool = False


@dataclass
class SystemStatus:
    """Overall system status snapshot"""
    timestamp: str
    mode: str  # autonomous, manual, hybrid, emergency
    zones_active: int
    alerts: List[str] = field(default_factory=list)
    critical_alerts: List[str] = field(default_factory=list)


# ==================== AI ENGINE ====================

class AIEngine:
    """
    Master AI Engine for ENKOMOS.
    
    Integrates all subsystems and makes autonomous decisions.
    Follows the sacred hierarchy:
    1. Physical manual override (highest)
    2. Digital manual override
    3. AI autonomous (default)
    4. Emergency stop (overrides all)
    """
    
    def __init__(self):
        """Initialize all controllers and AI engine"""
        print("[AI] Initializing ENKOMOS AI Engine...")
        
        # Initialize subsystems (graceful fallback if missing)
        self.climate = ClimateController() if ClimateController else None
        self.water = WaterController() if WaterController else None
        self.energy = EnergyController() if EnergyController else None
        self.db = DatabaseManager() if DatabaseManager else None
        
        # System state
        self.mode = config.SYSTEM.get("mode", "autonomous")
        self.running = False
        self.emergency_stop_triggered = False
        self.control_thread = None
        self.monitor_thread = None
        
        # Decision log
        self.decisions: List[SystemDecision] = []
        self.max_decisions_log = 1000
        
        # Alert state
        self.alerts: List[str] = []
        self.critical_alerts: List[str] = []
        
        # Zone status cache
        self.zone_status_cache: Dict[int, Dict] = {}
        
        print(f"[AI] ENKOMOS AI Engine initialized in {self.mode} mode")
        
    # ==================== ALERT MANAGEMENT ====================
    
    def add_alert(self, alert: str, critical: bool = False):
        """Add an alert to the system"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_alert = f"[{timestamp}] {alert}"
        
        if critical:
            self.critical_alerts.append(formatted_alert)
            print(f"[ALERT-CRITICAL] {alert}")
        else:
            self.alerts.append(formatted_alert)
            print(f"[ALERT] {alert}")
            
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        if len(self.critical_alerts) > 50:
            self.critical_alerts = self.critical_alerts[-50:]
            
    def clear_alerts(self, critical_only: bool = False):
        """Clear alerts"""
        if critical_only:
            self.critical_alerts = []
        else:
            self.alerts = []
            self.critical_alerts = []
            
    # ==================== DECISION LOGGING ====================
    
    def log_decision(self, decision_type: str, zone: int, action: str, reason: str, manual: bool = False):
        """Log an AI or manual decision"""
        decision = SystemDecision(
            timestamp=datetime.now().isoformat(),
            decision_type=decision_type,
            zone=zone,
            action=action,
            reason=reason,
            manual_override=manual
        )
        self.decisions.append(decision)
        
        # Trim log
        if len(self.decisions) > self.max_decisions_log:
            self.decisions = self.decisions[-self.max_decisions_log:]
            
        # Also log to database
        if self.db:
            self.db.log_growth_entry(
                zone=zone,
                crop="system_decisions",
                measurements={
                    "decision_type": decision_type,
                    "action": action,
                    "reason": reason,
                    "manual": manual
                }
            )
            
    # ==================== SAFETY CHECKS ====================
    
    def check_safety(self) -> bool:
        """
        Perform safety checks.
        Returns True if safe, False if emergency shutdown needed.
        """
        if not self.climate:
            return True
            
        # Check all zones for dangerous temperatures
        for zone_id, zone_status in self.climate.get_all_zones_status().items():
            temp = zone_status.get("temp_c", 20)
            max_temp = config.SAFETY.get("max_temp_before_shutdown_c", 45)
            
            if temp > max_temp:
                self.add_alert(f"Zone {zone_id} temperature {temp}°C exceeds {max_temp}°C limit", critical=True)
                return False
                
            if temp < 0:
                self.add_alert(f"Zone {zone_id} temperature {temp}°C below freezing", critical=True)
                return False
                
        # Check battery health if energy controller exists
        if self.energy:
            battery_status = self.energy.get_status().get("battery", {})
            battery_temp = battery_status.get("temperature_c", 25)
            if battery_temp > 55:
                self.add_alert(f"Battery temperature {battery_temp}°C too high", critical=True)
                return False
                
        return True
    
    # ==================== EMERGENCY HANDLING ====================
    
    def emergency_shutdown(self, reason: str = "Manual or safety trigger"):
        """Emergency shutdown - overrides everything"""
        self.emergency_stop_triggered = True
        self.mode = "emergency"
        self.add_alert(f"EMERGENCY SHUTDOWN: {reason}", critical=True)
        
        # Stop all subsystems
        if self.climate:
            self.climate.emergency_shutdown()
        if self.energy:
            self.energy.emergency_shutdown()
        if self.water:
            # Water controller may not have emergency shutdown yet
            pass
            
        self.log_decision("emergency", 0, "shutdown", reason, manual=False)
        print("[EMERGENCY] All systems halted. Manual restart required.")
        
    def emergency_reset(self):
        """Reset from emergency state"""
        self.emergency_stop_triggered = False
        self.mode = config.SYSTEM.get("mode", "autonomous")
        self.clear_alerts(critical_only=True)
        self.add_alert("Emergency reset - systems restarting", critical=False)
        print("[AI] Emergency reset. Systems restarting.")
        
    # ==================== MANUAL OVERRIDE HANDLING ====================
    
    def set_manual_override(self, zone_id: int, duration_minutes: int = None):
        """Set manual override for a specific zone"""
        if duration_minutes is None:
            duration_minutes = config.MANUAL_OVERRIDE.get("auto_reset_override_minutes", 240)
            
        if self.climate:
            self.climate.set_manual_override(zone_id, duration_minutes)
            
        self.log_decision("manual_override", zone_id, "override_activated", 
                         f"Duration: {duration_minutes} minutes", manual=True)
        print(f"[MANUAL] Zone {zone_id} manual override for {duration_minutes} minutes")
        
    def clear_manual_override(self, zone_id: int):
        """Clear manual override for a zone"""
        if self.climate:
            self.climate.clear_manual_override(zone_id)
            
        self.log_decision("manual_override", zone_id, "override_cleared", 
                         "Return to AI control", manual=True)
        print(f"[MANUAL] Zone {zone_id} manual override cleared")
        
    # ==================== AI DECISION MAKING ====================
    
    def _make_climate_decisions(self):
        """AI decisions for climate control"""
        if not self.climate:
            return
            
        for zone_id, zone_status in self.climate.get_all_zones_status().items():
            if zone_status.get("manual_override", False):
                continue  # Skip if manual override active
                
            # Check temperature
            if zone_status.get("needs_heating", False):
                self.log_decision("climate", zone_id, "heating_on", 
                                f"Temp {zone_status['temp_c']}°C below min", manual=False)
                                
            elif zone_status.get("needs_cooling", False):
                self.log_decision("climate", zone_id, "cooling_on",
                                f"Temp {zone_status['temp_c']}°C above max", manual=False)
                                
            # Check humidity
            if zone_status.get("needs_humidifying", False):
                self.log_decision("climate", zone_id, "humidifying_on",
                                f"Humidity {zone_status['humidity']}% below min", manual=False)
                                
            elif zone_status.get("needs_dehumidifying", False):
                self.log_decision("climate", zone_id, "dehumidifying_on",
                                f"Humidity {zone_status['humidity']}% above max", manual=False)
                                
    def _make_energy_decisions(self):
        """AI decisions for energy management"""
        if not self.energy:
            return
            
        energy_status = self.energy.get_status()
        battery_soc = energy_status.get("battery", {}).get("soc_percent", 80)
        
        # Log low battery condition
        if battery_soc < 30:
            self.add_alert(f"Battery low: {battery_soc}% remaining", critical=False)
            self.log_decision("energy", 0, "low_battery_alert",
                            f"Battery at {battery_soc}%", manual=False)
                            
        elif battery_soc < 20:
            self.add_alert(f"Battery critically low: {battery_soc}%", critical=True)
            
    def _make_water_decisions(self):
        """AI decisions for water management"""
        if not self.water:
            return
            
        water_status = self.water.get_status()
        fish_status = water_status.get("fish_tub", {})
        
        # Check fish health
        if fish_status.get("needs_water_change", False):
            water_quality = fish_status.get("water_quality", {})
            self.add_alert(f"Fish tub needs water change - Ammonia: {water_quality.get('ammonia_ppm', 0)} ppm", 
                          critical=False)
            self.log_decision("water", 0, "water_change_needed",
                            f"Ammonia {water_quality.get('ammonia_ppm', 0)} ppm", manual=False)
                            
        # Check structured water
        structured_status = water_status.get("structured_water", {})
        if not structured_status.get("quality", {}).get("orp_optimal", True):
            orp = structured_status.get("quality", {}).get("orp_mv", 0)
            self.log_decision("water", 0, "structured_water_adjusting",
                            f"ORP at {orp} mV - optimizing", manual=False)
                            
    # ==================== MONITORING ====================
    
    def _monitor_loop(self):
        """Continuous monitoring for safety and alerts"""
        while self.running and not self.emergency_stop_triggered:
            # Safety check
            if not self.check_safety():
                self.emergency_shutdown("Safety check failed")
                break
                
            # Update zone status cache
            if self.climate:
                self.zone_status_cache = self.climate.get_all_zones_status()
                
            time.sleep(5)  # Check every 5 seconds
            
    def _ai_loop(self):
        """Main AI decision loop"""
        while self.running and not self.emergency_stop_triggered:
            if self.mode == "autonomous":
                self._make_climate_decisions()
                self._make_energy_decisions()
                self._make_water_decisions()
                
            elif self.mode == "hybrid":
                # Hybrid mode: AI suggests but doesn't act
                pass
                
            # Log system status periodically
            if self.db and int(time.time()) % 300 < 30:  # Every 5 minutes
                status = self.get_system_status()
                self.db.log_growth_entry(
                    zone=0,
                    crop="system_status",
                    measurements={
                        "mode": status.mode,
                        "zones_active": status.zones_active,
                        "alert_count": len(status.alerts),
                        "critical_alert_count": len(status.critical_alerts)
                    }
                )
                
            time.sleep(config.SYSTEM.get("ai_interval_seconds", 30))
            
    # ==================== SYSTEM CONTROL ====================
    
    def start(self):
        """Start the entire ENKOMOS system"""
        if self.running:
            print("[AI] System already running")
            return
            
        print("[AI] Starting ENKOMOS AI Engine...")
        
        # Start all subsystems
        if self.climate:
            self.climate.start()
        if self.water:
            self.water.start()
        if self.energy:
            self.energy.start()
            
        self.running = True
        self.emergency_stop_triggered = False
        
        # Start threads
        self.control_thread = threading.Thread(target=self._ai_loop, daemon=True)
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.control_thread.start()
        self.monitor_thread.start()
        
        self.log_decision("system", 0, "system_start", "ENKOMOS AI Engine started", manual=False)
        print("[AI] ENKOMOS AI Engine running")
        
    def stop(self):
        """Stop the entire ENKOMOS system (graceful)"""
        print("[AI] Stopping ENKOMOS AI Engine...")
        self.running = False
        
        # Stop subsystems
        if self.climate:
            self.climate.stop()
        if self.water:
            self.water.stop()
        if self.energy:
            self.energy.stop()
            
        self.log_decision("system", 0, "system_stop", "Graceful shutdown", manual=False)
        print("[AI] ENKOMOS AI Engine stopped")
        
    def get_system_status(self) -> SystemStatus:
        """Get comprehensive system status"""
        zones_active = 0
        if self.climate:
            zones_active = len(self.climate.zones) if hasattr(self.climate, 'zones') else 0
            
        return SystemStatus(
            timestamp=datetime.now().isoformat(),
            mode=self.mode,
            zones_active=zones_active,
            alerts=self.alerts[-10:],  # Last 10 alerts
            critical_alerts=self.critical_alerts[-5:]  # Last 5 critical alerts
        )
        
    def get_full_status(self) -> Dict:
        """Get complete status of all subsystems"""
        return {
            "ai_engine": {
                "mode": self.mode,
                "running": self.running,
                "emergency_stop": self.emergency_stop_triggered,
                "decisions_logged": len(self.decisions)
            },
            "climate": self.climate.get_all_zones_status() if self.climate else {"error": "Not available"},
            "water": self.water.get_status() if self.water else {"error": "Not available"},
            "energy": self.energy.get_status() if self.energy else {"error": "Not available"},
            "alerts": {
                "warnings": self.alerts[-5:],
                "critical": self.critical_alerts[-3:]
            }
        }
        
    def set_mode(self, mode: str):
        """Change system mode: autonomous, manual, hybrid, emergency"""
        valid_modes = ["autonomous", "manual", "hybrid", "emergency"]
        if mode not in valid_modes:
            print(f"[AI] Invalid mode: {mode}. Use {valid_modes}")
            return
            
        old_mode = self.mode
        self.mode = mode
        self.log_decision("system", 0, f"mode_change_{mode}", f"Changed from {old_mode} to {mode}", manual=True)
        print(f"[AI] Mode changed: {old_mode} -> {mode}")


# ==================== COMMAND LINE TEST ====================

if __name__ == "__main__":
    print("=== ENKOMOS AI Engine Test ===")
    
    # Create and start AI engine
    ai = AIEngine()
    ai.start()
    
    # Let it run for a few seconds
    time.sleep(10)
    
    # Get status
    print("\n" + "="*50)
    print("SYSTEM STATUS")
    print("="*50)
    status = ai.get_system_status()
    print(f"Mode: {status.mode}")
    print(f"Zones Active: {status.zones_active}")
    print(f"Alerts: {len(status.alerts)}")
    print(f"Critical Alerts: {len(status.critical_alerts)}")
    
    print("\n" + "="*50)
    print("FULL STATUS")
    print("="*50)
    full_status = ai.get_full_status()
    for key, value in full_status.items():
        if key not in ["climate", "water", "energy"]:
            print(f"{key}: {value}")
    
    # Stop
    print("\nStopping AI Engine...")
    ai.stop()
    print("\nAI Engine ready for deployment.")
