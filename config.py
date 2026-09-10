"""
config.py
Konfigurasi terpusat bot. Semua nilai sensitif (token, chat id) DIAMBIL DARI
ENVIRONMENT VARIABLE -- jangan pernah hardcode token di kode saat deploy
ke Render / PythonAnywhere (repo publik = token bocor = bot dibajak orang).
"""

import os

# --- Wajib diisi lewat Environment Variable di platform hosting ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")  # contoh: "@nama_channel" atau "-1001234567890"

# --- Mode Jalan Bot ---
# "polling"  -> dipakai untuk Render Background Worker (tidak butuh URL publik)
# "webhook"  -> dipakai untuk PythonAnywhere / Render Web Service (butuh URL publik HTTPS)
MODE = os.environ.get("MODE", "polling").lower()
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")  # contoh: https://namamu.pythonanywhere.com
PORT = int(os.environ.get("PORT", "8080"))

# --- Parameter Trading Default (bisa diubah lewat command /size di bot) ---
DEFAULT_CAPITAL = float(os.environ.get("DEFAULT_CAPITAL", "50000000"))       # Rp 50 juta
DEFAULT_RISK_PCT = float(os.environ.get("DEFAULT_RISK_PCT", "0.02"))        # 2% per trade
DEFAULT_MAX_ALLOC_PCT = float(os.environ.get("DEFAULT_MAX_ALLOC_PCT", "0.20"))  # 20% per saham

# --- Parameter Filter Likuiditas ---
MIN_VALUE = float(os.environ.get("MIN_VALUE", "5000000000"))  # Rp 5 Miliar/hari
MIN_PRICE = float(os.environ.get("MIN_PRICE", "100"))
MIN_FREQ = int(os.environ.get("MIN_FREQ", "1000"))

# --- Jadwal Auto Screener Harian (Asia/Jakarta) ---
SCREENER_HOUR = int(os.environ.get("SCREENER_HOUR", "16"))
SCREENER_MINUTE = int(os.environ.get("SCREENER_MINUTE", "5"))
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Jakarta")

# --- Parameter Screening Seluruh IHSG ---
# Full IHSG bisa ~900 saham -- worker dibuat moderat & ada jeda kecil antar
# request supaya tidak kena rate-limit Yahoo Finance. Kalau proses terasa
# terlalu lama/lambat di hosting kamu, kecilkan SCREENER_MAX_WORKERS atau
# batasi jumlah saham lewat SCREENER_MAX_STOCKS.
SCREENER_MAX_WORKERS = int(os.environ.get("SCREENER_MAX_WORKERS", "6"))
SCREENER_REQUEST_DELAY = float(os.environ.get("SCREENER_REQUEST_DELAY", "0.0"))
SCREENER_MAX_STOCKS = int(os.environ.get("SCREENER_MAX_STOCKS", "0"))  # 0 = tanpa batas


def validate():
    """Cek konfigurasi wajib sebelum bot dijalankan."""
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if MODE == "webhook" and not WEBHOOK_URL:
        missing.append("WEBHOOK_URL (wajib jika MODE=webhook)")
    if missing:
        raise RuntimeError(
            "Environment variable belum lengkap: " + ", ".join(missing)
        )
