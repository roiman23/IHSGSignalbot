# Swing Trading Signal Bot (IDX) — Panduan Lengkap

Bot Telegram terintegrasi untuk swing trading saham IDX: filter likuiditas,
sinyal teknikal (EMA/RSI/MACD/Fibonacci), manajemen risiko & position sizing,
watchlist, dan auto-screener harian untuk seluruh saham LQ45.

## Struktur File

| File | Fungsi |
|---|---|
| `config.py` | Baca semua konfigurasi dari environment variable |
| `liquidity_filter.py` | Filter saham "gorengan" (turnover, harga, volume minimum) |
| `risk_manager.py` | Hitung position sizing (lot) berdasar risk % dan alokasi maks |
| `signals.py` | Ambil data riil (Yahoo Finance), hitung indikator, generate sinyal |
| `screener.py` | Ambil daftar LQ45 otomatis + scan paralel semua saham |
| `storage.py` | Watchlist sederhana berbasis file JSON |
| `bot.py` | Bot Telegram utama (semua command + inline keyboard + job harian) |
| `run_screener_once.py` | Script sekali-jalan untuk PythonAnywhere Scheduled Task |
| `requirements.txt` | Daftar dependency Python |
| `Procfile` | Perintah start untuk Render |

---

## Langkah 1 — Buat Bot di BotFather

1. Buka Telegram, cari **@BotFather**.
2. Kirim `/newbot`, ikuti instruksi (nama + username unik, misal `SwingTraderPro_bot`).
3. Simpan **API Token** yang diberikan — ini nilai untuk `BOT_TOKEN`.
4. Jika mau kirim sinyal otomatis ke channel: buat channel baru, tambahkan bot
   sebagai **Administrator**, lalu catat username channel (`@nama_channel`)
   atau ID numeriknya untuk `CHANNEL_ID`.

## Langkah 2 — Environment Variable yang Dibutuhkan

```
BOT_TOKEN=isi_token_dari_botfather
CHANNEL_ID=@nama_channel_kamu        # opsional, untuk auto-screener harian
MODE=polling                          # "polling" (Render) atau "webhook" (PythonAnywhere)
WEBHOOK_URL=https://namamu.pythonanywhere.com   # wajib jika MODE=webhook
DEFAULT_CAPITAL=50000000
DEFAULT_RISK_PCT=0.02
```

**Jangan pernah menaruh token langsung di kode** — kalau repo-nya publik di
GitHub, token bisa dicuri orang dan bot kamu dibajak untuk spam.

## Langkah 3 — Uji Coba Lokal (opsional, sebelum deploy)

```bash
pip install -r requirements.txt
export BOT_TOKEN="token_kamu"
export MODE="polling"
python bot.py
```

Buka Telegram, chat bot kamu, kirim `/start`. Coba `/scan BBCA` untuk tes
analisis dengan data riil.

---

## Opsi A — Deploy ke Render (Direkomendasikan, Mode Polling)

Render punya tipe service **Background Worker** yang cocok untuk bot polling
(tidak butuh URL publik/webhook). *Catatan: cek dulu halaman pricing Render
saat ini — kebijakan free tier untuk proses yang selalu menyala (always-on)
bisa berubah, jadi ada kemungkinan tipe Background Worker perlu paket
berbayar (mulai sekitar $7/bulan).*

1. Push semua file di atas ke repository GitHub (**pastikan `.env` / token
   tidak ikut ter-commit**).
2. Login ke [render.com](https://render.com), klik **New +** → **Background Worker**.
3. Hubungkan ke repo GitHub kamu.
4. Isi konfigurasi:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py` (sudah otomatis terbaca dari `Procfile`)
5. Di tab **Environment**, tambahkan semua environment variable dari Langkah 2
   (set `MODE=polling`, tidak perlu `WEBHOOK_URL`).
6. Klik **Create Background Worker**. Render akan build lalu menjalankan bot
   otomatis. Cek tab **Logs** — harus muncul `Menjalankan bot dalam mode POLLING...`.
7. Test lagi di Telegram dengan `/start`.

Bot akan otomatis mengirim hasil screening LQ45 ke `CHANNEL_ID` tiap hari
bursa jam 16:05 WIB (bisa diubah lewat `SCREENER_HOUR` / `SCREENER_MINUTE`).

---

## Opsi B — Deploy ke PythonAnywhere

PythonAnywhere **free tier tidak mendukung proses yang selalu menyala**
(polling 24/7) maupun membuka port webhook custom. Ada dua cara realistis:

### B1. Bot interaktif penuh (butuh paket berbayar "Always-on Task")

1. Upload semua file lewat tab **Files** (atau `git clone` dari konsol Bash PA).
2. Buka tab **Consoles** → **Bash**, jalankan:
   ```bash
   pip install --user -r requirements.txt
   ```
3. Buka tab **Tasks** → **Always-on Tasks** (fitur berbayar), buat task baru:
   ```
   python3.x /home/usernamekamu/trading_bot/bot.py
   ```
4. Set environment variable lewat file `.env` yang di-load manual di awal
   `bot.py`, atau set langsung di command task (`BOT_TOKEN=xxx python3 bot.py`).
5. `MODE` cukup `polling` — Always-on Task berjalan seperti proses biasa,
   tidak perlu webhook/port publik.

### B2. Hanya Auto-Screener Harian (Gratis, tanpa command interaktif)

Cocok kalau kamu hanya butuh sinyal harian otomatis ke Telegram, tanpa perlu
membalas command `/scan` secara real-time.

1. Upload file project (minimal: `config.py`, `liquidity_filter.py`,
   `risk_manager.py`, `signals.py`, `screener.py`, `run_screener_once.py`,
   `requirements.txt`).
2. Di konsol Bash: `pip install --user -r requirements.txt`.
3. Buka tab **Tasks** → **Scheduled Tasks** (tersedia di free tier).
4. Set jam eksekusi — **ingat PythonAnywhere pakai UTC**, jadi untuk jam
   16:05 WIB (UTC+7) isi jam **09:05 UTC**.
5. Command:
   ```
   BOT_TOKEN=xxx CHANNEL_ID=@channelkamu python3.x /home/usernamekamu/trading_bot/run_screener_once.py
   ```
6. Simpan. Script ini akan jalan sekali per hari, scan LQ45, kirim hasil ke
   channel, lalu proses berhenti sendiri (hemat kuota CPU free tier).

---

## Command Bot yang Tersedia

| Command | Fungsi |
|---|---|
| `/start` | Menu utama |
| `/scan TICKER` | Analisis lengkap 1 saham (likuiditas + sinyal + plan) |
| `/plan TICKER ENTRY SL TP` | Hitung RRR dari harga manual |
| `/size MODAL RISK_PERSEN` | Hitung lot aman dari plan terakhir |
| `/watchlist` | Lihat saham yang sudah disimpan |
| `/screener` | Jalankan scan seluruh LQ45 sekarang juga |

## Cakupan Screener: Seluruh IHSG (Bukan Cuma LQ45)

`/screener` dan auto-screener harian sekarang menyasar **seluruh saham
yang tercatat di BEI (~900 emiten)**, bukan cuma 45 anggota LQ45. Karena
IDX tidak punya API publik resmi yang terdokumentasi untuk daftar
lengkap emiten, `screener.py` memakai 3 lapis fallback (otomatis, tanpa
perlu kamu atur manual):

1. **Endpoint idx.co.id** (`GetSecuritiesStock`) — cakupan paling lengkap,
   tapi ini endpoint hasil reverse-engineering dari website publik IDX,
   bukan API resmi yang dijamin stabil. Bisa berubah/diblokir kapan saja.
2. **Fallback: gabungan IDX80 + LQ45 dari Wikipedia** (~80-90 saham
   likuid) — dipakai otomatis kalau Tier 1 gagal.
3. **Fallback terakhir: daftar statis LQ45** — selalu bisa dipakai
   walau tidak ada koneksi ke IDX/Wikipedia sama sekali.

Bot akan mencetak log yang jelas di setiap tier yang gagal/berhasil,
supaya kamu tahu cakupan mana yang sedang dipakai hari itu.

## Parameter yang Bisa Diatur (Environment Variable Tambahan)

| Variable | Default | Fungsi |
|---|---|---|
| `SCREENER_MAX_WORKERS` | `6` | Jumlah thread paralel saat scan. Naikkan hati-hati — makin banyak, makin cepat tapi makin rawan kena rate-limit Yahoo Finance. |
| `SCREENER_REQUEST_DELAY` | `0.0` | Jeda (detik) antar request per thread, untuk memperlambat laju request kalau sering kena error/blokir. |
| `SCREENER_MAX_STOCKS` | `0` (tanpa batas) | Batasi jumlah saham yang di-scan per run — berguna kalau full IHSG kelamaan di hosting gratis. |

## Batasan yang Perlu Kamu Sadari

- **Scan seluruh IHSG makan waktu jauh lebih lama** dari LQ45 saja —
  wajar kalau `/screener` butuh beberapa menit untuk ~900 saham. Untuk
  auto-screener harian ini tidak masalah karena berjalan di background,
  tapi kalau kamu pakai hosting gratis dengan batas waktu eksekusi,
  pertimbangkan set `SCREENER_MAX_STOCKS` supaya tidak timeout.
- **Endpoint resmi IDX yang dipakai Tier 1 tidak didokumentasikan
  publik** — ini titik paling rapuh di seluruh sistem. Kalau suatu saat
  formatnya berubah, bot otomatis turun ke Tier 2 (IDX80+LQ45), bukan
  error total — tapi cakupannya jadi lebih sempit dari yang kamu harapkan.
  Cek log secara berkala untuk tahu tier mana yang aktif.
- **Data dari Yahoo Finance** untuk saham `.JK` kadang delay atau data
  volume-nya kurang presisi dibanding data resmi BEI — cukup untuk swing
  trading (holding harian-mingguan), jangan dipakai untuk keputusan intraday.
- **Watchlist disimpan di file lokal** (`watchlist.json`) — di Render/PA,
  file ini bisa hilang saat redeploy. Untuk pemakaian jangka panjang, ganti
  ke database (SQLite/Postgres).
- Bot ini adalah **alat bantu analisis, bukan auto-executor** — tidak
  terhubung ke broker manapun, jadi tidak ada risiko order otomatis salah
  eksekusi. Keputusan beli/jual tetap manual olehmu.
