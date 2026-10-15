"""
Free Fire Matchmaking Web Dashboard & Multi-Account Parallel Worker
Dual-compatible with AI Studio Preview (Port 3000) and Railway Ingress ($PORT)
"""

import os
import sys
import json
import time
import logging
from flask import Flask, jsonify, request, render_template, Response

from engine import FFMatchmakingEngine
from message_ids import Opcodes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("FF-Railway-Server")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "ff-secret-railway-key-2026")

# Initialize Engine with accounts.js
engine = FFMatchmakingEngine(
    accounts_file=os.path.join(BASE_DIR, "accounts.js"),
    devices_file=os.path.join(BASE_DIR, "devices.json"),
    cache_file=os.path.join(BASE_DIR, "token_cache.json")
)

# 24/7 Headless Background Worker Startup
# This executes automatically when Gunicorn imports main:app on Railway,
# ensuring EXP is farmed continuously even when NO browser tab is open!
if os.environ.get("AUTO_START", "true").lower() == "true":
    logger.info("24/7 Background Support Enabled: Spawning parallel farming threads for all accounts in accounts.js...")
    engine.start_all()

@app.after_request
def add_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response

@app.route("/")
def index():
    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify(engine.get_stats())
    try:
        return render_template("index.html")
    except Exception as e:
        logger.error(f"Template rendering failed: {e}")
        return jsonify(engine.get_stats())

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "uptime": int(time.time() - engine.start_time)
    }), 200

@app.route("/api/status")
def api_status():
    return jsonify(engine.get_stats())

@app.route("/api/worker/start", methods=["POST"])
def api_worker_start():
    data = request.get_json() or {}
    account_id = data.get("account_id")
    if not account_id or account_id == "ALL":
        result = engine.start_all()
    else:
        result = engine.start_worker(account_id)
    return jsonify(result)

@app.route("/api/worker/stop", methods=["POST"])
def api_worker_stop():
    data = request.get_json() or {}
    account_id = data.get("account_id")
    if not account_id or account_id == "ALL":
        result = engine.stop_all()
    else:
        result = engine.stop_worker(account_id)
    return jsonify(result)

@app.route("/api/accounts", methods=["GET"])
def api_accounts():
    stats = engine.get_stats()
    return jsonify(stats.get("accounts", []))

@app.route("/api/accounts/add", methods=["POST"])
def api_accounts_add():
    data = request.get_json() or {}
    result = engine.add_account(data)
    return jsonify(result)

@app.route("/api/accounts/delete/<account_id>", methods=["DELETE", "POST"])
def api_accounts_delete(account_id):
    result = engine.delete_account(account_id)
    return jsonify(result)

@app.route("/api/accounts/verify/<account_id>", methods=["POST"])
def api_accounts_verify(account_id):
    result = engine.verify_account(account_id)
    return jsonify(result)

@app.route("/api/accounts/verify_all", methods=["POST"])
def api_accounts_verify_all():
    result = engine.verify_all()
    return jsonify(result)

@app.route("/api/accounts/export/json")
def api_export_json():
    content = engine.export_accounts_json()
    return Response(
        content,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment;filename=accounts.json"}
    )

@app.route("/api/accounts/export/js")
def api_export_js():
    content = engine.export_accounts_js()
    return Response(
        content,
        mimetype="application/javascript",
        headers={"Content-Disposition": "attachment;filename=accounts.js"}
    )

@app.route("/api/logs")
def api_logs():
    account_id = request.args.get("account_id")
    limit = int(request.args.get("limit", 100))
    return jsonify(engine.get_logs(account_id=account_id, limit=limit))

if __name__ == "__main__":
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_ID"):
        port = int(os.environ.get("PORT", 5000))
    else:
        port = 3000
    host = os.environ.get("HOST", "0.0.0.0")
    
    logger.info(f"Free Fire Matchmaking Studio listening on {host}:{port}")
    app.run(host=host, port=port, debug=False)
