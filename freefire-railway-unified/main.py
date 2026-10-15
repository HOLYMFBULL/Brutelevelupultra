"""
Unified Free Fire Matchmaking Bot & Dashboard Server
Optimized for Railway deployment (reads $PORT, /health check, background workers)
Unifies newbrsup/lc.py and UDP_LEAKED_BY_SAITO/main.py (parts 1-5)
"""

import os
import sys
import json
import time
import logging
import threading
from flask import Flask, jsonify, request, render_template, send_from_directory

# Import core engine and opcodes
from engine import FFMatchmakingEngine
from message_ids import Opcodes

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("FF-Railway-Server")

# Base directory of the project
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize Flask App with absolute template folder
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "ff-secret-railway-key-2026")

# Global engine instance with absolute file paths
engine = FFMatchmakingEngine(
    accounts_file=os.path.join(BASE_DIR, "accounts.json"),
    devices_file=os.path.join(BASE_DIR, "devices.json"),
    users_file=os.path.join(BASE_DIR, "users.json"),
    cache_file=os.path.join(BASE_DIR, "token_cache.json")
)

# Background worker thread controller
engine_thread = None
is_running = False

def background_worker():
    global is_running
    logger.info("Background matchmaking worker started.")
    while is_running:
        try:
            engine.process_tick()
            time.sleep(1.0)
        except Exception as e:
            logger.error(f"Error in engine tick: {e}", exc_info=True)
            time.sleep(5.0)
    logger.info("Background matchmaking worker stopped.")

@app.route("/")
def index():
    """Serve the interactive web dashboard interface"""
    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return api_info()
    try:
        return render_template("index.html")
    except Exception as e:
        logger.warning(f"Could not render template: {e}")
        return api_info()

@app.route("/api/info")
def api_info():
    """Serve the raw JSON system metadata"""
    return jsonify({
        "status": "online",
        "service": "Railway FreeFire Matchmaking Studio",
        "version": "2.4.0-unified",
        "port": os.getenv("PORT", "5000"),
        "engine_active": is_running,
        "accounts_loaded": len(engine.accounts),
        "devices_configured": len(engine.devices),
        "endpoints": {
            "health": "/health",
            "status": "/api/status",
            "start_match": "/api/match/start",
            "cancel_match": "/api/match/cancel",
            "accounts": "/api/accounts",
            "devices": "/api/devices",
            "logs": "/api/logs"
        }
    })

@app.route("/health")
def health():
    """Railway health check probe endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "uptime_seconds": int(time.time() - engine.start_time)
    }), 200

@app.route("/api/status")
def api_status():
    """Returns engine state, active matchmaking queue, and recent events"""
    return jsonify(engine.get_status())

@app.route("/api/match/start", methods=["POST"])
def api_start_match():
    """Trigger StartMatch packet request for loaded account/squad"""
    data = request.get_json() or {}
    account_id = data.get("account_id")
    mode = data.get("mode", 2) # Ranked
    team_type = data.get("team_type", 1) # Solo=1, Duo=2, Squad=4
    region = data.get("region", "IND")
    
    result = engine.start_match(account_id=account_id, mode=mode, team_type=team_type, region=region)
    return jsonify(result)

@app.route("/api/match/cancel", methods=["POST"])
def api_cancel_match():
    """Cancel active matchmaking queue"""
    result = engine.cancel_match()
    return jsonify(result)

@app.route("/api/accounts", methods=["GET", "POST"])
def api_accounts():
    """View or update bot accounts"""
    if request.method == "POST":
        new_accounts = request.get_json()
        engine.update_accounts(new_accounts)
        return jsonify({"status": "success", "count": len(new_accounts)})
    return jsonify(engine.accounts)

@app.route("/api/devices", methods=["GET"])
def api_devices():
    """View configured device hardware fingerprints"""
    return jsonify(engine.devices)

@app.route("/api/logs", methods=["GET"])
def api_logs():
    """Get recent network logs and packet events"""
    limit = int(request.args.get("limit", 50))
    return jsonify(engine.get_logs(limit))

@app.route("/api/engine/start", methods=["POST"])
def api_engine_start():
    """Start background matchmaking daemon"""
    global is_running, engine_thread
    if not is_running:
        is_running = True
        engine_thread = threading.Thread(target=background_worker, daemon=True)
        engine_thread.start()
        return jsonify({"status": "started", "active": True})
    return jsonify({"status": "already_running", "active": True})

@app.route("/api/engine/stop", methods=["POST"])
def api_engine_stop():
    """Stop background matchmaking daemon"""
    global is_running
    is_running = False
    return jsonify({"status": "stopping", "active": False})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    auto_start = os.environ.get("AUTO_START", "true").lower() == "true"
    
    if auto_start:
        is_running = True
        engine_thread = threading.Thread(target=background_worker, daemon=True)
        engine_thread.start()
        logger.info("Auto-start enabled: Background engine thread spawned.")
        
    logger.info(f"Starting server on {host}:{port} for Railway environment...")
    app.run(host=host, port=port, debug=False)
