"""
screener.py
Mengambil daftar SELURUH saham yang tercatat di BEI/IHSG (bukan cuma
LQ45), lalu menjalankan generate_signal() untuk semua ticker secara
paralel.

CATATAN PENTING SOAL SUMBER DATA:
IDX tidak menyediakan API resmi publik yang didokumentasikan untuk daftar
seluruh emiten (900+ saham). Endpoint di bawah ini (GetSecuritiesStock)
dipakai secara luas oleh scraper-scraper IDX (termasuk beberapa proyek
Node.js yang sejenis dengan idx-bei), tapi sifatnya "reverse-engineered"
dari website publik idx.co.id -- BUKAN kontrak API resmi. Endpoint ini
bisa berubah atau diblokir kapan saja tanpa pemberitahuan. Karena itu
fungsi di bawah punya 3 lapis fallback:

  1. Endpoint resmi idx.co.id (paling lengkap & akurat, ~900 saham)
  2. Gabungan konstituen IDX80 + LQ45 dari Wikipedia (~90 saham likuid)
  3. Daftar statis LQ45 (paling minim, tapi pasti selalu bisa dipakai)
"""

import concurrent.futures
import time

import pandas as pd
import requests

from signals import generate_signal

IDX_STOCK_LIST_URL = "https://www.idx.co.id/primary/StockData/GetSecuritiesStock"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.idx.co.id/",
}

# Fallback paling minim -- dipakai kalau SEMUA metode lain gagal total.
FALLBACK_LQ45 = [
    "ACES.JK", "ADRO.JK", "AMRT.JK", "ANTM.JK", "ARTO.JK", "ASII.JK", "BBCA.JK",
    "BBNI.JK", "BBRI.JK", "BBTN.JK", "BMRI.JK", "BRPT.JK", "BUKA.JK", "BUMI.JK",
    "CPIN.JK", "EMTK.JK", "EXCL.JK", "GOTO.JK", "HRUM.JK", "ICBP.JK", "INCO.JK",
    "INDF.JK", "INKP.JK", "INTP.JK", "ITMG.JK", "KLBF.JK", "MDKA.JK", "MEDC.JK",
    "MIKA.JK", "MNCN.JK", "PGAS.JK", "PTBA.JK", "SRTG.JK", "TBIG.JK",
    "TPIA.JK", "TOWR.JK", "TLKM.JK", "UNTR.JK", "UNVR.JK",
]


def _to_ticker(code: str) -> str:
    code = str(code).strip().upper()
    return code if code.endswith(".JK") else f"{code}.JK"


def _fetch_all_ihsg_from_idx_official(timeout: int = 15):
    """
    Tier 1: Coba ambil SELURUH saham tercatat langsung dari idx.co.id.
    Return list ticker, atau None kalau gagal / format berubah.
    """
    try:
        resp = requests.get(IDX_STOCK_LIST_URL, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # Struktur JSON dari endpoint ini bisa berupa list langsung atau
        # dibungkus di key seperti "data"/"Items" -- coba beberapa kemungkinan.
        rows = data if isinstance(data, list) else data.get("data") or data.get("Items") or []
        if not rows:
            raise ValueError("Response tidak berisi daftar saham (format tidak dikenali)")

        codes = []
        for row in rows:
            code = row.get("Code") or row.get("code") or row.get("KodeEmiten")
            if code:
                codes.append(_to_ticker(code))

        if len(codes) < 300:  # sanity check -- IHSG harusnya ratusan saham
            raise ValueError(f"Jumlah saham hasil fetch mencurigakan sedikit ({len(codes)})")

        return sorted(set(codes))
    except Exception as e:
        print(f"⚠️ Tier 1 gagal (endpoint resmi IDX): {e}")
        return None


def _fetch_idx80_lq45_from_wikipedia():
    """
    Tier 2: Gabungan konstituen IDX80 + LQ45 dari Wikipedia. Cakupan lebih
    luas dari LQ45 saja (~80-90 saham likuid & bermarket-cap besar).
    """
    all_codes = set()
    for url in ("https://id.wikipedia.org/wiki/IDX80", "https://id.wikipedia.org/wiki/LQ45"):
        try:
            tables = pd.read_html(url)
            for table in tables:
                kode_cols = [c for c in table.columns if "kode" in str(c).lower()]
                if not kode_cols:
                    continue
                codes = table[kode_cols[0]].astype(str).str.strip().str.upper()
                codes = codes[codes.str.match(r"^[A-Z]{3,5}$")]  # buang baris bukan kode saham
                all_codes.update(_to_ticker(c) for c in codes)
        except Exception as e:
            print(f"⚠️ Gagal ambil tabel dari {url}: {e}")

    if len(all_codes) < 30:
        return None
    return sorted(all_codes)


def get_ihsg_tickers(force_refresh: bool = False):
    """
    Ambil daftar ticker untuk di-screening, dengan fallback berlapis:
    IDX resmi -> IDX80+LQ45 Wikipedia -> daftar statis LQ45.
    """
    tickers = _fetch_all_ihsg_from_idx_official()
    if tickers:
        print(f"Berhasil mengambil {len(tickers)} saham dari endpoint resmi IDX.")
        return tickers

    tickers = _fetch_idx80_lq45_from_wikipedia()
    if tickers:
        print(f"Pakai fallback IDX80+LQ45 ({len(tickers)} saham), bukan full IHSG.")
        return tickers

    print(f"Semua metode gagal, pakai fallback statis LQ45 ({len(FALLBACK_LQ45)} saham).")
    return FALLBACK_LQ45


# Dipertahankan untuk kompatibilitas / kalau user hanya mau scan LQ45 saja.
def get_lq45_tickers():
    try:
        tables = pd.read_html("https://id.wikipedia.org/wiki/LQ45")
        for table in tables:
            kode_cols = [c for c in table.columns if "kode" in str(c).lower()]
            if kode_cols:
                codes = table[kode_cols[0]].astype(str).str.strip().str.upper()
                tickers = [_to_ticker(c) for c in codes if len(c) <= 5]
                if len(tickers) >= 20:
                    return tickers
        raise ValueError("Tabel LQ45 tidak ditemukan / terlalu sedikit hasil")
    except Exception as e:
        print(f"Gagal scraping LQ45 ({e}), pakai fallback statis.")
        return FALLBACK_LQ45


def run_screening(tickers=None, max_workers: int = 6, request_delay: float = 0.0):
    """
    Jalankan generate_signal() untuk semua ticker secara paralel.

    max_workers sengaja dibuat moderat (default 6) karena scan ratusan
    saham sekaligus ke Yahoo Finance berisiko kena rate-limit/blokir
    sementara kalau workernya terlalu banyak. Untuk full IHSG (~900 saham)
    proses ini wajar makan waktu beberapa menit -- itu normal, karena
    dijalankan sebagai job harian, bukan realtime.
    """
    if tickers is None:
        tickers = get_ihsg_tickers()

    results = []

    def _analyze(ticker):
        if request_delay:
            time.sleep(request_delay)
        return generate_signal(ticker)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_analyze, t): t for t in tickers}
        for future in concurrent.futures.as_completed(future_map):
            ticker = future_map[future]
            try:
                result = future.result()
                if result.get("action") == "BUY":
                    results.append(result)
            except Exception as e:
                print(f"Error saat menganalisis {ticker}: {e}")

    results.sort(key=lambda r: r.get("rrr", 0), reverse=True)
    return results
