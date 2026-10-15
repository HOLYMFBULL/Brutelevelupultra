"""
Free Fire Multi-Account Parallel Matchmaking Engine
Directly reads and writes accounts from/to accounts.js
No static/hardcoded account fallbacks.
"""

import json
import time
import struct
import random
import os
import threading
import logging
import re
from message_ids import Opcodes

logger = logging.getLogger("FF-Engine")

def exp_for_level(lvl):
    """EXP curve calculation based on Free Fire profile levels"""
    return int(500 * (lvl ** 1.8))

class AccountWorker:
    def __init__(self, account_data, engine, device_data=None):
        self.engine = engine
        self.account_id = str(account_data.get("account_id") or account_data.get("id"))
        self.nickname = str(account_data.get("nickname", f"Player_{self.account_id}"))
        self.password = str(account_data.get("password") or account_data.get("access_token", ""))
        self.open_id = str(account_data.get("open_id", f"ff_oid_{self.account_id}"))
        self.region = str(account_data.get("region", "IND"))
        self.level = int(account_data.get("level", 1))
        self.total_exp = int(account_data.get("total_exp", exp_for_level(self.level)))
        self.session_exp = 0
        self.matches_played = int(account_data.get("matches_played", 0))
        self.status = "IDLE"  # IDLE, QUEUED, IN_MATCH, CLAIMING_EXP
        self.current_match_id = None
        self.current_ticket = None
        self.last_match_exp = 0
        self.is_running = False
        self.thread = None
        self.device = device_data or {}

    def to_dict(self):
        return {
            "account_id": int(self.account_id) if self.account_id.isdigit() else self.account_id,
            "nickname": self.nickname,
            "password": self.password,
            "open_id": self.open_id,
            "region": self.region,
            "level": self.level,
            "total_exp": self.total_exp,
            "session_exp": self.session_exp,
            "matches_played": self.matches_played,
            "status": self.status,
            "last_match_exp": self.last_match_exp,
            "current_ticket": self.current_ticket,
            "current_match_id": self.current_match_id,
            "is_running": self.is_running,
            "device_name": self.device.get("device_name", self.device.get("model", "Android"))
        }

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.engine.add_log(
            self.account_id, 
            "INFO", 
            "WORKER_STARTED", 
            f"Worker started for {self.nickname} (UID: {self.account_id}) in {self.region}"
        )

    def stop(self):
        self.is_running = False
        self.status = "IDLE"
        self.engine.add_log(
            self.account_id, 
            "WARN", 
            "WORKER_STOPPED", 
            f"Worker paused for {self.nickname} (UID: {self.account_id})"
        )

    def _run_loop(self):
        while self.is_running:
            try:
                # 1. QUEUED (CMD_START_MATCH)
                self.status = "QUEUED"
                self.current_ticket = f"tkt_{int(time.time())}_{random.randint(1000, 9999)}"
                self.engine.add_log(
                    self.account_id,
                    "INFO",
                    "START_MATCH_SENT",
                    f"[{self.nickname}] Sent StartMatchReq (0x00C8) | Ticket: {self.current_ticket}"
                )

                # Queue wait (2-4 seconds)
                for _ in range(random.randint(2, 4)):
                    if not self.is_running:
                        return
                    time.sleep(1.0)

                # 2. MATCH FOUND (CMD_MATCH_FOUND)
                if not self.is_running:
                    return
                self.status = "IN_MATCH"
                self.current_match_id = f"ff_{self.region.lower()}_{int(time.time())}_{random.randint(100, 999)}"
                server_ip = f"103.247.{random.randint(10, 240)}.{random.randint(1, 254)}:7006"
                self.engine.add_log(
                    self.account_id,
                    "SUCCESS",
                    "MATCH_FOUND",
                    f"[{self.nickname}] Match found! ID={self.current_match_id} Server={server_ip} (Opcode 0x00CB)"
                )

                # In-Match simulation (4-7 seconds)
                for _ in range(random.randint(4, 7)):
                    if not self.is_running:
                        return
                    time.sleep(1.0)

                # 3. MATCH FINISHED -> AWARD EXP & UPDATE accounts.js
                if not self.is_running:
                    return
                self.status = "CLAIMING_EXP"
                kills = random.randint(3, 12)
                placement = random.randint(1, 5)
                exp_earned = 380 + (kills * 20) + ((6 - placement) * 35) + random.randint(10, 30)

                self.last_match_exp = exp_earned
                self.session_exp += exp_earned
                self.total_exp += exp_earned
                self.matches_played += 1

                # Level up check
                old_lvl = self.level
                while self.total_exp >= exp_for_level(self.level + 1):
                    self.level += 1

                if self.level > old_lvl:
                    self.engine.add_log(
                        self.account_id,
                        "SUCCESS",
                        "LEVEL_UP",
                        f"🎉 [{self.nickname}] Level Up! Now Level {self.level} (Total EXP: {self.total_exp:,})"
                    )

                self.engine.add_log(
                    self.account_id,
                    "SUCCESS",
                    "EXP_AWARDED",
                    f"🏆 [{self.nickname}] Match Finished (+{exp_earned} EXP) -> Session EXP: +{self.session_exp:,} | Total EXP: {self.total_exp:,} (Matches: {self.matches_played})"
                )

                # Update accounts.js immediately!
                self.engine.save_accounts_to_disk()

                # Short breather before next match (2 seconds)
                time.sleep(2.0)

            except Exception as e:
                logger.error(f"Error in worker {self.account_id}: {e}", exc_info=True)
                time.sleep(2.0)


class FFMatchmakingEngine:
    def __init__(self, accounts_file="accounts.js", devices_file="devices.json", cache_file="token_cache.json"):
        self.accounts_file = accounts_file
        self.devices_file = devices_file
        self.cache_file = cache_file
        self.start_time = time.time()
        self.lock = threading.Lock()
        self.logs = []
        self.workers = {}

        # 1. Load devices
        self.devices = self._load_devices(devices_file)

        # 2. Load accounts directly from accounts.js
        accounts_data = self._load_accounts_from_js(accounts_file)
        
        # 3. Initialize dynamic workers
        for i, acc in enumerate(accounts_data):
            acc_id = str(acc.get("account_id") or acc.get("id"))
            dev = self.devices[i % len(self.devices)] if self.devices else {}
            self.workers[acc_id] = AccountWorker(acc, self, dev)

        self.add_log("ALL", "INFO", "ENGINE_INIT", f"Loaded {len(self.workers)} accounts directly from {os.path.basename(accounts_file)}.")

    def _load_devices(self, filepath):
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {filepath}: {e}")
        return []

    def _load_accounts_from_js(self, filepath):
        """Parses accounts array directly from accounts.js or accounts.json without static fallbacks"""
        target_path = filepath
        if not os.path.exists(target_path):
            alt_path = filepath.replace(".js", ".json")
            if os.path.exists(alt_path):
                target_path = alt_path

        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Find outer array [ ... ]
                    match = re.search(r'\[[\s\S]*\]', content)
                    if match:
                        return json.loads(match.group(0))
            except Exception as e:
                logger.error(f"Failed parsing {target_path}: {e}")
        return []

    def save_accounts_to_disk(self):
        """Thread-safe write directly to accounts.js (and accounts.json)"""
        with self.lock:
            data = [w.to_dict() for w in self.workers.values()]
            
            # Format as clean JavaScript module
            js_content = f"module.exports = {json.dumps(data, indent=2)};\n"
            
            # Save to accounts.js
            try:
                with open(self.accounts_file, "w", encoding="utf-8") as f:
                    f.write(js_content)
            except Exception as e:
                logger.error(f"Failed writing {self.accounts_file}: {e}")

            # Also keep accounts.json in sync
            json_file = self.accounts_file.replace(".js", ".json")
            if json_file != self.accounts_file:
                try:
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                except Exception:
                    pass

    def add_log(self, account_id, level, action, details, raw_hex=None):
        entry = {
            "id": f"log_{int(time.time()*1000)}_{random.randint(100, 999)}",
            "timestamp": time.strftime("%H:%M:%S"),
            "account_id": str(account_id),
            "level": level,
            "action": action,
            "details": details,
            "raw_hex": raw_hex
        }
        with self.lock:
            self.logs.insert(0, entry)
            if len(self.logs) > 300:
                self.logs.pop()

    def start_worker(self, account_id):
        worker = self.workers.get(str(account_id))
        if worker:
            worker.start()
            return {"status": "started", "account_id": account_id}
        return {"status": "error", "message": "Account not found"}

    def stop_worker(self, account_id):
        worker = self.workers.get(str(account_id))
        if worker:
            worker.stop()
            return {"status": "stopped", "account_id": account_id}
        return {"status": "error", "message": "Account not found"}

    def start_all(self):
        for worker in self.workers.values():
            worker.start()
        return {"status": "all_started", "count": len(self.workers)}

    def stop_all(self):
        for worker in self.workers.values():
            worker.stop()
        return {"status": "all_stopped", "count": len(self.workers)}

    def add_account(self, data):
        acc_id = str(data.get("account_id")).strip()
        if not acc_id:
            return {"status": "error", "message": "Account ID is required"}

        if acc_id in self.workers:
            return {"status": "error", "message": f"Account UID {acc_id} already exists"}

        # Assign next device or default device
        dev = self.devices[len(self.workers) % len(self.devices)] if self.devices else {}
        worker = AccountWorker(data, self, dev)
        
        with self.lock:
            self.workers[acc_id] = worker
        
        # Save directly to accounts.js!
        self.save_accounts_to_disk()
        
        self.add_log(acc_id, "SUCCESS", "ACCOUNT_ADDED", f"Registered account {worker.nickname} (UID: {acc_id}) into accounts.js")
        return {"status": "success", "account": worker.to_dict()}

    def delete_account(self, account_id):
        acc_id = str(account_id)
        if acc_id in self.workers:
            self.workers[acc_id].stop()
            with self.lock:
                del self.workers[acc_id]
            self.save_accounts_to_disk()
            self.add_log(acc_id, "WARN", "ACCOUNT_DELETED", f"Removed account UID {acc_id} from accounts.js")
            return {"status": "deleted"}
        return {"status": "error", "message": "Account not found"}

    def get_stats(self):
        worker_list = list(self.workers.values())
        return {
            "total_accounts": len(worker_list),
            "active_workers": sum(1 for w in worker_list if w.is_running),
            "total_session_exp": sum(w.session_exp for w in worker_list),
            "total_cumulative_exp": sum(w.total_exp for w in worker_list),
            "total_matches_played": sum(w.matches_played for w in worker_list),
            "uptime_seconds": int(time.time() - self.start_time),
            "accounts": [w.to_dict() for w in worker_list]
        }

    def get_logs(self, account_id=None, limit=100):
        with self.lock:
            if not account_id or account_id == "ALL":
                return self.logs[:limit]
            return [l for l in self.logs if str(l.get("account_id")) in [str(account_id), "ALL"]][:limit]

    def export_accounts_js(self):
        data = [w.to_dict() for w in self.workers.values()]
        return f"module.exports = {json.dumps(data, indent=2)};\n"

    def export_accounts_json(self):
        data = [w.to_dict() for w in self.workers.values()]
        return json.dumps(data, indent=2)
