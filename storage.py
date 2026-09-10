"""
storage.py
Penyimpanan watchlist sederhana berbasis file JSON.
Catatan: di Render/PythonAnywhere free tier, file ini bisa hilang saat
redeploy. Untuk penggunaan jangka panjang, ganti dengan database
(SQLite/Postgres) -- struktur fungsi di bawah sengaja dibuat sederhana
supaya gampang diganti nanti.
"""

import json
import os
import threading

_LOCK = threading.Lock()
_FILE = os.environ.get("WATCHLIST_FILE", "watchlist.json")


def _load():
    if not os.path.exists(_FILE):
        return {}
    try:
        with open(_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data):
    with open(_FILE, "w") as f:
        json.dump(data, f)


def add_to_watchlist(user_id: int, ticker: str):
    with _LOCK:
        data = _load()
        key = str(user_id)
        data.setdefault(key, [])
        if ticker not in data[key]:
            data[key].append(ticker)
            _save(data)
            return True
        return False


def get_watchlist(user_id: int):
    with _LOCK:
        data = _load()
        return data.get(str(user_id), [])
