"""
memory.py — Persistent chat history + user settings for Void AI
"""
import json
import threading
from config import DB_FILE, MAX_HISTORY

_lock = threading.Lock()


def _load():
    with _lock:
        if DB_FILE.exists():
            try:
                return json.loads(DB_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}


def _save(data):
    with _lock:
        DB_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _init_user(uid, data):
    if str(uid) not in data:
        data[str(uid)] = {
            "history":       [],
            "mode":          "auto",       # auto | groq | mistral
            "groq_model":    "llama-3.3-70b",
            "mistral_model": "mistral-large",
            "language":      "auto",
            "voice_reply":   False,
            "stats":         {"messages": 0, "voice": 0, "images": 0},
        }
    return data[str(uid)]


# ── History ───────────────────────────────────────────────────────────────────

def get_history(uid):
    data = _load()
    rec  = _init_user(uid, data)
    return rec["history"]


def add_message(uid, role, content):
    data = _load()
    rec  = _init_user(uid, data)
    rec["history"].append({"role": role, "content": content})
    if len(rec["history"]) > MAX_HISTORY:
        rec["history"] = rec["history"][-MAX_HISTORY:]
    _save(data)


def clear_history(uid):
    data = _load()
    _init_user(uid, data)
    data[str(uid)]["history"] = []
    _save(data)


def get_context(uid, system_prompt):
    return [{"role": "system", "content": system_prompt}] + get_history(uid)


# ── Settings ──────────────────────────────────────────────────────────────────

def get(uid, key, default=None):
    data = _load()
    rec  = _init_user(uid, data)
    return rec.get(key, default)


def put(uid, key, value):
    data = _load()
    _init_user(uid, data)
    data[str(uid)][key] = value
    _save(data)


def bump(uid, key):
    data = _load()
    _init_user(uid, data)
    data[str(uid)].setdefault("stats", {})
    data[str(uid)]["stats"][key] = data[str(uid)]["stats"].get(key, 0) + 1
    _save(data)


def get_stats(uid):
    data = _load()
    rec  = _init_user(uid, data)
    return rec.get("stats", {})


def total_users():
    return len(_load())
