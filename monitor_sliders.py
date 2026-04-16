"""
ENKOMOS - Monitor Sliders (Web UI)
Energy & Keystone Operating Management Operating System

Web-based manual override interface with touch/drag sliders.
Real-time monitoring of all zones and subsystems.
"""

import json
import time
import threading
import os
import sys
from datetime import datetime
from typing import Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ImportError:
    print("[ERROR] config.py not found. Running in demo mode.")
    class config:
        SYSTEM = {"name": "ENKOMOS", "version": "1.0.0"}
        ZONES = {1: {"name": "Zone 1"}, 2: {"name": "Zone 2"}, 3: {"name": "Zone 3"},
                 4: {"name": "Zone 4"}, 5: {"name": "Zone 5"}, 6: {"name": "Zone 6"}}
        MANUAL_OVERRIDE = {"auto_reset_override_minutes": 240}

try:
    from ai_engine import AIEngine
except ImportError:
    print("[WARN] ai_engine.py not found. Running in standalone demo mode.")
    AIEngine = None


# ==================== HTML TEMPLATE ====================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <title>ENKOMOS - Control Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a3e2a 0%, #1a5c3a 100%);
            color: #f0f0e0;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        h1 {
            text-align: center;
            margin-bottom: 10px;
            font-size: 2.2em;
            letter-spacing: 2px;
        }
        
        .subtitle {
            text-align: center;
            margin-bottom: 30px;
            opacity: 0.8;
            font-style: italic;
        }
        
        /* Status Bar */
        .status-bar {
            background: rgba(0,0,0,0.5);
            border-radius: 15px;
            padding: 15px 20px;
            margin-bottom: 25px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            gap: 15px;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-led {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #0f0;
            box-shadow: 0 0 5px #0f0;
            animation: pulse 2s infinite;
        }
        
        .status-led.warning {
            background: #ff0;
            box-shadow: 0 0 5px #ff0;
        }
        
        .status-led.critical {
            background: #f00;
            box-shadow: 0 0 5px #f00;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Zone Grid */
        .zones-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }
        
        .zone-card {
            background: rgba(0,0,0,0.4);
            border-radius: 20px;
            padding: 20px;
            backdrop-filter: blur(5px);
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.2s;
        }
        
        .zone-card:hover {
            transform: translateY(-3px);
        }
        
        .zone-title {
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 15px;
            border-bottom: 2px solid #ffd700;
            display: inline-block;
            padding-bottom: 5px;
        }
        
        .sensor-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 20px;
        }
        
        .sensor {
            background: rgba(0,0,0,0.3);
            padding: 8px 12px;
            border-radius: 10px;
            text-align: center;
        }
        
        .sensor-label {
            font-size: 0.8em;
            opacity: 0.7;
        }
        
        .sensor-value {
            font-size: 1.3em;
            font-weight: bold;
        }
        
        .slider-container {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.2);
        }
        
        .slider-label {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        
        input[type="range"] {
            width: 100%;
            height: 6px;
            -webkit-appearance: none;
            background: linear-gradient(90deg, #2ecc71, #e74c3c);
            border-radius: 5px;
            outline: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: #ffd700;
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 0 5px #ffd700;
        }
        
        .override-badge {
            display: inline-block;
            background: #ff6600;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 0.7em;
            margin-left: 10px;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        button {
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 0.85em;
        }
        
        button:hover {
            background: rgba(255,255,255,0.3);
            transform: scale(1.02);
        }
        
        button.danger {
            background: rgba(220, 53, 69, 0.5);
            border-color: #dc3545;
        }
        
        button.danger:hover {
            background: rgba(220, 53, 69, 0.7);
        }
        
        button.warning {
            background: rgba(255, 193, 7, 0.3);
            border-color: #ffc107;
        }
        
        /* System Panel */
        .system-panel {
            background: rgba(0,0,0,0.4);
            border-radius: 20px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .system-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .energy-bar {
            background: #2c3e50;
            border-radius: 10px;
            height: 20px;
            overflow: hidden;
            margin-top: 5px;
        }
        
        .energy-fill {
            background: linear-gradient(90deg, #2ecc71, #f1c40f);
            height: 100%;
            width: 0%;
            transition: width 0.3s;
            border-radius: 10px;
        }
        
        .alert-list {
            margin-top: 15px;
            max-height: 150px;
            overflow-y: auto;
            font-size: 0.85em;
        }
        
        .alert-item {
            padding: 5px 10px;
            background: rgba(0,0,0,0.3);
            margin-bottom: 5px;
            border-radius: 8px;
            border-left: 3px solid #ffc107;
        }
        
        .alert-item.critical {
            border-left-color: #dc3545;
            background: rgba(220, 53, 69, 0.2);
        }
        
        @media (max-width: 768px) {
            body { padding: 10px; }
            .zones-grid { grid-template-columns: 1fr; }
            .sensor-grid { grid-template-columns: repeat(2, 1fr); }
            .status-bar { flex-direction: column; }
        }
        
        .refresh-note {
            text-align: center;
            font-size: 0.7em;
            margin-top: 20px;
            opacity: 0.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌿 ENKOMOS</h1>
        <div class="subtitle">Energy & Keystone Operating Management Operating System</div>
        
        <div class="status-bar" id="statusBar">
            <div class="status-item"><span class="status-led" id="modeLed"></span><span id="modeText">Loading...</span></div>
            <div class="status-item">🔋 Battery: <span id="batteryStatus">--</span></div>
            <div class="status-item">⚡ Load: <span id="loadStatus">--</span> kW</div>
            <div class="status-item">💧 Water ORP: <span id="orpStatus">--</span> mV</div>
            <div class="status-item">📡 Last Update: <span id="lastUpdate">--</span></div>
        </div>
        
        <div class="zones-grid" id="zonesGrid"></div>
        
        <div class="system-panel">
            <h3>🔋 Energy System</h3>
            <div class="system-grid">
                <div>
                    <div>Solar: <span id="solarKw">--</span> kW</div>
                    <div>Wind: <span id="windKw">--</span> kW</div>
                    <div>Biogas: <span id="biogasKw">--</span> kW</div>
                </div>
                <div>
                    <div>Battery SOC</div>
                    <div class="energy-bar"><div class="energy-fill" id="batteryFill"></div></div>
                    <div id="batteryPercent">--%</div>
                </div>
                <div>
                    <div>AC Frequency: <span id="acFreq">--</span> Hz</div>
                    <div>Mode: <span id="systemMode">--</span></div>
                </div>
            </div>
        </div>
        
        <div class="system-panel">
            <h3>⚠️ Alerts</h3>
            <div class="alert-list" id="alertList">
                <div>No alerts</div>
            </div>
        </div>
        
        <div class="system-panel">
            <h3>🖐️ Global Controls</h3>
            <div class="button-group">
                <button id="clearAllOverridesBtn" class="warning">Clear All Overrides</button>
                <button id="emergencyStopBtn" class="danger">⚠️ EMERGENCY STOP</button>
                <button id="refreshBtn">🔄 Refresh</button>
            </div>
        </div>
        
        <div class="refresh-note">Auto-refreshes every 5 seconds | Touch/drag sliders for manual override</div>
    </div>
    
    <script>
        // API endpoints
        const API_STATUS = '/api/status';
        const API_SLIDER = '/api/slider';
        const API_OVERRIDE_CLEAR = '/api/override/clear';
        const API_EMERGENCY_STOP = '/api/emergency/stop';
        
        let refreshInterval = null;
        
        // Format number
        function formatNumber(value, decimals = 1) {
            if (value === undefined || value === null) return '--';
            return Number(value).toFixed(decimals);
        }
        
        // Update UI with status data
        function updateUI(data) {
            // Mode LED
            const modeLed = document.getElementById('modeLed');
            const modeText = document.getElementById('modeText');
            if (data.ai_engine) {
                const mode = data.ai_engine.mode || 'unknown';
                modeText.innerText = `Mode: ${mode.toUpperCase()}`;
                if (mode === 'emergency') {
                    modeLed.className = 'status-led critical';
                } else if (mode === 'manual') {
                    modeLed.className = 'status-led warning';
                } else {
                    modeLed.className = 'status-led';
                }
            }
            
            // Battery and energy
            if (data.energy && data.energy.battery) {
                const soc = data.energy.battery.soc_percent || 0;
                document.getElementById('batteryStatus').innerText = formatNumber(soc, 0) + '%';
                document.getElementById('batteryFill').style.width = soc + '%';
                document.getElementById('batteryPercent').innerText = formatNumber(soc, 0) + '%';
            }
            
            if (data.energy && data.energy.generation) {
                document.getElementById('solarKw').innerText = formatNumber(data.energy.generation.solar?.output_kw);
                document.getElementById('windKw').innerText = formatNumber(data.energy.generation.wind?.output_kw);
                document.getElementById('biogasKw').innerText = formatNumber(data.energy.generation.biogas?.output_kw);
            }
            
            if (data.energy && data.energy.load_kw !== undefined) {
                document.getElementById('loadStatus').innerText = formatNumber(data.energy.load_kw);
            }
            
            if (data.energy && data.energy.ac_frequency) {
                document.getElementById('acFreq').innerText = formatNumber(data.energy.ac_frequency.current_frequency_hz, 1);
            }
            
            // Water ORP
            if (data.water && data.water.structured_water && data.water.structured_water.quality) {
                document.getElementById('orpStatus').innerText = formatNumber(data.water.structured_water.quality.orp_mv, 0);
            }
            
            document.getElementById('systemMode').innerText = data.ai_engine?.mode || 'unknown';
            document.getElementById('lastUpdate').innerText = new Date().toLocaleTimeString();
            
            // Zones
            updateZones(data);
            
            // Alerts
            updateAlerts(data);
        }
        
        function updateZones(data) {
            const zonesGrid = document.getElementById('zonesGrid');
            const zones = data.climate || {};
            
            let html = '';
            for (const [zoneId, zoneData] of Object.entries(zones)) {
                const isManual = zoneData.manual_override || false;
                const remaining = zoneData.override_remaining_min || 0;
                
                html += `
                    <div class="zone-card" data-zone="${zoneId}">
                        <div class="zone-title">
                            Zone ${zoneId}
                            ${isManual ? '<span class="override-badge">MANUAL</span>' : ''}
                        </div>
                        <div class="sensor-grid">
                            <div class="sensor">
                                <div class="sensor-label">🌡️ Temperature</div>
                                <div class="sensor-value">${formatNumber(zoneData.temp_c)}°C</div>
                            </div>
                            <div class="sensor">
                                <div class="sensor-label">💧 Humidity</div>
                                <div class="sensor-value">${formatNumber(zoneData.humidity)}%</div>
                            </div>
                            <div class="sensor">
                                <div class="sensor-label">CO₂</div>
                                <div class="sensor-value">${formatNumber(zoneData.co2_ppm, 0)} ppm</div>
                            </div>
                            <div class="sensor">
                                <div class="sensor-label">💨 VPD</div>
                                <div class="sensor-value">${formatNumber(zoneData.vpd_kpa)} kPa</div>
                            </div>
                        </div>
                        <div class="slider-container">
                            <div class="slider-label">
                                <span>🌡️ Temperature Target</span>
                                <span id="tempTarget_${zoneId}">--</span>
                            </div>
                            <input type="range" id="tempSlider_${zoneId}" min="10" max="40" step="0.5" 
                                   onchange="sendSliderValue(${zoneId}, 'temp', this.value)">
                            <div class="slider-label" style="margin-top: 10px;">
                                <span>💧 Humidity Target</span>
                                <span id="humTarget_${zoneId}">--</span>
                            </div>
                            <input type="range" id="humSlider_${zoneId}" min="30" max="90" step="1"
                                   onchange="sendSliderValue(${zoneId}, 'humidity', this.value)">
                        </div>
                        <div class="button-group">
                            <button onclick="clearOverride(${zoneId})">Clear Override</button>
                            <button onclick="setOverride(${zoneId})">Override 4 Hours</button>
                        </div>
                        ${isManual ? `<div style="font-size:0.7em; margin-top:8px;">Manual: ${remaining} min remaining</div>` : ''}
                    </div>
                `;
            }
            zonesGrid.innerHTML = html;
            
            // Set slider values based on zone data
            for (const [zoneId, zoneData] of Object.entries(zones)) {
                const tempSlider = document.getElementById(`tempSlider_${zoneId}`);
                const humSlider = document.getElementById(`humSlider_${zoneId}`);
                if (tempSlider) tempSlider.value = zoneData.temp_c || 20;
                if (humSlider) humSlider.value = zoneData.humidity || 60;
                document.getElementById(`tempTarget_${zoneId}`).innerText = zoneData.temp_c?.toFixed(1) + '°C';
                document.getElementById(`humTarget_${zoneId}`).innerText = zoneData.humidity?.toFixed(0) + '%';
            }
        }
        
        function updateAlerts(data) {
            const alertList = document.getElementById('alertList');
            const alerts = data.alerts || {};
            const warnings = alerts.warnings || [];
            const critical = alerts.critical || [];
            
            if (warnings.length === 0 && critical.length === 0) {
                alertList.innerHTML = '<div>✅ No active alerts</div>';
                return;
            }
            
            let html = '';
            for (const alert of critical) {
                html += `<div class="alert-item critical">🔴 ${escapeHtml(alert)}</div>`;
            }
            for (const alert of warnings) {
                html += `<div class="alert-item">🟡 ${escapeHtml(alert)}</div>`;
            }
            alertList.innerHTML = html;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // API calls
        async function fetchStatus() {
            try {
                const response = await fetch(API_STATUS);
                const data = await response.json();
                updateUI(data);
            } catch (e) {
                console.error('Status fetch error:', e);
            }
        }
        
        async function sendSliderValue(zoneId, type, value) {
            try {
                const response = await fetch(API_SLIDER, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ zone: zoneId, type: type, value: parseFloat(value) })
                });
                const result = await response.json();
                if (result.success) {
                    console.log(`Slider sent: Zone ${zoneId} ${type}=${value}`);
                    setTimeout(fetchStatus, 500);
                }
            } catch (e) {
                console.error('Slider error:', e);
            }
        }
        
        async function setOverride(zoneId) {
            try {
                await fetch(`/api/override/set?zone=${zoneId}`, { method: 'POST' });
                fetchStatus();
            } catch (e) {
                console.error('Override error:', e);
            }
        }
        
        async function clearOverride(zoneId) {
            try {
                await fetch(`/api/override/clear?zone=${zoneId}`, { method: 'POST' });
                fetchStatus();
            } catch (e) {
                console.error('Clear override error:', e);
            }
        }
        
        async function clearAllOverrides() {
            try {
                await fetch('/api/override/clear_all', { method: 'POST' });
                fetchStatus();
            } catch (e) {
                console.error('Clear all error:', e);
            }
        }
        
        async function emergencyStop() {
            if (confirm('⚠️ EMERGENCY STOP: This will shut down all systems. Continue?')) {
                try {
                    await fetch(API_EMERGENCY_STOP, { method: 'POST' });
                    fetchStatus();
                } catch (e) {
                    console.error('Emergency stop error:', e);
                }
            }
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            fetchStatus();
            refreshInterval = setInterval(fetchStatus, 5000);
            
            document.getElementById('clearAllOverridesBtn').onclick = clearAllOverrides;
            document.getElementById('emergencyStopBtn').onclick = emergencyStop;
            document.getElementById('refreshBtn').onclick = fetchStatus;
        });
    </script>
</body>
</html>
'''


# ==================== HTTP REQUEST HANDLER ====================

class ENKOMOSHandler(BaseHTTPRequestHandler):
    """HTTP handler for ENKOMOS web interface"""
    
    ai_engine = None  # Class variable set from main
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            self._serve_html()
        elif parsed.path == '/api/status':
            self._serve_status()
        else:
            self._serve_404()
    
    def do_POST(self):
        """Handle POST requests"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/slider':
            self._handle_slider()
        elif parsed.path == '/api/override/set':
            self._handle_override_set(parsed)
        elif parsed.path == '/api/override/clear':
            self._handle_override_clear(parsed)
        elif parsed.path == '/api/override/clear_all':
            self._handle_override_clear_all()
        elif parsed.path == '/api/emergency/stop':
            self._handle_emergency_stop()
        else:
            self._serve_404()
    
    def _serve_html(self):
        """Serve the main HTML page"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
    
    def _serve_status(self):
        """Serve system status JSON"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        if self.ai_engine:
            status = self.ai_engine.get_full_status()
        else:
            status = {"error": "AI Engine not connected"}
        
        self.wfile.write(json.dumps(status).encode('utf-8'))
    
    def _handle_slider(self):
        """Handle slider value from UI"""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
            zone = data.get('zone')
            value_type = data.get('type')
            value = data.get('value')
            
            if self.ai_engine and zone:
                # Set manual override when slider is used
                self.ai_engine.set_manual_override(zone)
                print(f"[UI] Zone {zone} manual override - {value_type} set to {value}")
            
            self._send_json({"success": True, "message": f"Zone {zone} {value_type} set to {value}"})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)})
    
    def _handle_override_set(self, parsed):
        """Handle override set request"""
        params = parse_qs(parsed.query)
        zone = params.get('zone', [None])[0]
        
        if zone and self.ai_engine:
            self.ai_engine.set_manual_override(int(zone))
            print(f"[UI] Zone {zone} manual override activated")
        
        self._send_json({"success": True})
    
    def _handle_override_clear(self, parsed):
        """Handle override clear request"""
        params = parse_qs(parsed.query)
        zone = params.get('zone', [None])[0]
        
        if zone and self.ai_engine:
            self.ai_engine.clear_manual_override(int(zone))
            print(f"[UI] Zone {zone} manual override cleared")
        
        self._send_json({"success": True})
    
    def _handle_override_clear_all(self):
        """Handle clear all overrides"""
        if self.ai_engine and hasattr(self.ai_engine, 'climate'):
            for zone_id in self.ai_engine.climate.zones:
                self.ai_engine.clear_manual_override(zone_id)
        print("[UI] All manual overrides cleared")
        self._send_json({"success": True})
    
    def _handle_emergency_stop(self):
        """Handle emergency stop"""
        if self.ai_engine:
            self.ai_engine.emergency_shutdown("Web UI emergency button")
            print("[UI] EMERGENCY STOP triggered from web interface")
        self._send_json({"success": True, "emergency": True})
    
    def _serve_404(self):
        """Serve 404 response"""
        self.send_response(404)
        self.end_headers()
    
    def _send_json(self, data):
        """Send JSON response"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))


# ==================== WEB SERVER ====================

class MonitorSlidersServer:
    """Web server for ENKOMOS monitor interface"""
    
    def __init__(self, ai_engine=None, port=8080):
        self.ai_engine = ai_engine
        self.port = port
        self.server = None
        self.running = False
        
        # Set the class variable for the handler
        ENKOMOSHandler.ai_engine = ai_engine
    
    def start(self):
        """Start the web server"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), ENKOMOSHandler)
            self.running = True
            print(f"[UI] Monitor Sliders web server started on port {self.port}")
            print(f"[UI] Open http://localhost:{self.port} in your browser")
            print(f"[UI] From other devices: http://<your-ip>:{self.port}")
            
            while self.running:
                self.server.handle_request()
        except KeyboardInterrupt:
            print("\n[UI] Server stopped")
        except Exception as e:
            print(f"[UI] Server error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the web server"""
        self.running = False
        if self.server:
            self.server.server_close()
            print("[UI] Web server stopped")


# ==================== MAIN ====================

if __name__ == "__main__":
    print("=== ENKOMOS Monitor Sliders ===")
    
    # Try to connect to AI Engine
    ai = None
    try:
        # Try to get existing AI Engine instance or create new
        ai = AIEngine()
        ai.start()
        print("[UI] Connected to AI Engine")
    except Exception as e:
        print(f"[UI] Could not connect to AI Engine: {e}")
        print("[UI] Running in standalone demo mode (limited functionality)")
    
    # Start web server
    server = MonitorSlidersServer(ai_engine=ai, port=8080)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[UI] Shutting down...")
        if ai:
            ai.stop()
        server.stop()
