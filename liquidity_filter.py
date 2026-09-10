"""
liquidity_filter.py
Menyaring saham "gurem/gorengan" sebelum dianalisis lebih lanjut.
"""

from config import MIN_VALUE, MIN_PRICE, MIN_FREQ


def is_liquid(price: float, avg_value: float, avg_freq: float,
              min_value: float = MIN_VALUE,
              min_price: float = MIN_PRICE,
              min_freq: float = MIN_FREQ):
    """
    Mengecek apakah sebuah saham memenuhi kriteria likuiditas minimum.

    Parameters
    ----------
    price : harga close terakhir
    avg_value : rata-rata nilai transaksi harian (Rp)
    avg_freq : rata-rata frekuensi transaksi harian (proxy: pakai volume jika
               data frekuensi asli tidak tersedia dari sumber data)

    Returns
    -------
    (bool, str) -> (lolos_atau_tidak, alasan)
    """
    if price < min_price:
        return False, f"Harga (Rp {price:,.0f}) di bawah batas minimum Rp {min_price:,.0f}"
    if avg_value < min_value:
        return False, f"Nilai transaksi harian (Rp {avg_value:,.0f}) di bawah batas Rp {min_value:,.0f}"
    if avg_freq < min_freq:
        return False, f"Frekuensi/volume transaksi terlalu rendah ({avg_freq:,.0f})"
    return True, "Likuid"
