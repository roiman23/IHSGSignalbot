"""
bot.py
Bot Telegram terintegrasi: Filter Likuiditas + Sinyal Teknikal + Manajemen
Risiko + Auto Daily Screener + Watchlist. Siap deploy ke Render (polling,
Background Worker) atau PythonAnywhere (webhook, Web App).

Command:
  /start                        -> menu utama (inline keyboard)
  /scan TICKER                  -> analisis lengkap 1 saham
  /plan TICKER ENTRY SL TP      -> hitung RRR manual
  /size MODAL RISK_PERSEN       -> hitung position sizing dari plan terakhir
  /watchlist                    -> lihat watchlist tersimpan
  /screener                     -> jalankan screening seluruh saham IHSG sekarang juga
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import config
from risk_manager import RiskManager
from screener import get_ihsg_tickers, run_screening
from signals import generate_signal
from storage import add_to_watchlist, get_watchlist

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Menyimpan trading plan terakhir per user (in-memory, cukup untuk /size)
LAST_PLAN = {}


# ---------------------------------------------------------------------------
# HELPER FORMAT PESAN
# ---------------------------------------------------------------------------

def format_scan_result(result: dict) -> str:
    ticker = result["ticker"]

    if result["action"] == "NO_DATA":
        return f"❌ **{ticker}**: {result['reason']}"

    if result["action"] == "REJECTED":
        return (
            f"🚫 **ANALISIS ${ticker}**\n"
            f"Status: DITOLAK (Tidak Likuid)\n"
            f"Alasan: {result['reason']}"
        )

    if result["action"] in ("HOLD", "SELL"):
        icon = "⏸" if result["action"] == "HOLD" else "🔻"
        return (
            f"{icon} **${ticker}**\n"
            f"Harga: Rp {result['price']:,.0f}\n"
            f"Sinyal: {result['action']}\n"
            f"Catatan: {result['reason']}"
        )

    # action == BUY
    return (
        f"🎯 **TRADING PLAN: ${ticker}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Filter Likuiditas: PASSED\n"
        f"📊 Strategi: {result['strategy']}\n"
        f"💵 Harga Saat Ini: Rp {result['price']:,.0f}\n"
        f"📈 RSI(14): {result['rsi']}\n"
        f"📥 Buy Zone (Fibo): Rp {result['entry_zone']}\n"
        f"🛡 Stop Loss: Rp {result['sl']:,.0f}\n"
        f"🎯 Target 1: Rp {result['tp1']:,.0f}\n"
        f"🚀 Target 2: Rp {result['tp2']:,.0f}\n"
        f"⚖️ RRR: 1:{result['rrr']}\n"
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📊 Cara Scan Saham", callback_data="info_scan"),
            InlineKeyboardButton("📋 Cara Buat Plan", callback_data="info_plan"),
        ],
        [
            InlineKeyboardButton("🗂 Watchlist Saya", callback_data="show_watchlist"),
            InlineKeyboardButton("🔥 Screener Seluruh IHSG", callback_data="run_screener"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ---------------------------------------------------------------------------
# COMMAND HANDLERS
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "⚡ **SWING TRADING COMMAND CENTER** ⚡\n\n"
        "Bot ini membantu kamu screening saham likuid, mengecek sinyal "
        "teknikal, dan menghitung trading plan (Entry/SL/TP/RRR/Position "
        "Sizing) untuk swing trading saham IDX.\n\n"
        "Command cepat:\n"
        "`/scan TICKER` — analisis lengkap 1 saham\n"
        "`/plan TICKER ENTRY SL TP` — hitung RRR manual\n"
        "`/size MODAL RISK_PERSEN` — hitung lot dari plan terakhir\n"
        "`/watchlist` — lihat saham tersimpan\n"
        "`/screener` — scan seluruh saham IHSG sekarang (bisa makan waktu beberapa menit)"
    )
    if update.message:
        await update.message.reply_text(
            text, reply_markup=main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
        )


async def scan_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "⚠️ Masukkan kode saham.\nContoh: `/scan BUMI`", parse_mode=ParseMode.MARKDOWN
        )
        return

    ticker = context.args[0].upper()
    msg = await update.message.reply_text(f"⏳ Menganalisis ${ticker}...")

    result = generate_signal(ticker)
    text = format_scan_result(result)

    keyboard_rows = []
    if result["action"] == "BUY":
        LAST_PLAN[update.effective_user.id] = result
        keyboard_rows.append([
            InlineKeyboardButton("🧮 Hitung Lot", callback_data=f"calc_lot_{ticker}"),
            InlineKeyboardButton("💾 Simpan Watchlist", callback_data=f"save_wl_{ticker}"),
        ])
    keyboard_rows.append([InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")])

    await msg.edit_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN
    )


async def trading_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 4:
        await update.message.reply_text(
            "⚠️ Format salah!\nGunakan: `/plan TICKER ENTRY STOP_LOSS TARGET_PROFIT`\n"
            "Contoh: `/plan BUMI 140 133 154`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        ticker = context.args[0].upper()
        entry = float(context.args[1])
        sl = float(context.args[2])
        tp = float(context.args[3])
    except ValueError:
        await update.message.reply_text("❌ Entry/SL/TP harus berupa angka.")
        return

    risk_point = entry - sl
    reward_point = tp - entry
    if risk_point <= 0 or reward_point <= 0:
        await update.message.reply_text(
            "❌ Entry harus lebih besar dari Stop Loss dan lebih kecil dari Target Profit."
        )
        return

    risk_pct = (risk_point / entry) * 100
    reward_pct = (reward_point / entry) * 100
    rrr = reward_point / risk_point
    status = "✅ LAYAK (RRR ideal)" if rrr >= 2 else "⚠️ RISKY (RRR kurang dari 1:2)"

    LAST_PLAN[update.effective_user.id] = {
        "ticker": ticker, "price": entry, "sl": sl, "tp1": tp, "rrr": round(rrr, 2),
    }

    report = (
        f"📋 **TRADING PLAN: ${ticker}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Entry: Rp {entry:,.0f}\n"
        f"🛡 Stop Loss: Rp {sl:,.0f} (-{risk_pct:.2f}%)\n"
        f"🚀 Target Profit: Rp {tp:,.0f} (+{reward_pct:.2f}%)\n"
        f"⚖️ RRR: 1:{rrr:.2f}\n"
        f"📌 Status: {status}"
    )
    keyboard = [
        [InlineKeyboardButton("🧮 Hitung Lot", callback_data=f"calc_lot_{ticker}")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")],
    ]
    await update.message.reply_text(
        report, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN
    )


async def position_sizing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    plan = LAST_PLAN.get(user_id)
    if not plan:
        await update.message.reply_text(
            "⚠️ Buat `/scan` atau `/plan` dulu sebelum menghitung position sizing."
        )
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Format: `/size MODAL RISK_PERSEN`\nContoh: `/size 10000000 2`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        capital = float(context.args[0])
        risk_pct = float(context.args[1]) / 100
    except ValueError:
        await update.message.reply_text("❌ Modal dan persen risiko harus angka.")
        return

    entry = plan.get("price")
    sl = plan.get("sl")
    if entry is None or sl is None:
        await update.message.reply_text("⚠️ Plan terakhir tidak lengkap, buat ulang dengan /plan atau /scan.")
        return

    try:
        rm = RiskManager(total_capital=capital, risk_per_trade_pct=risk_pct)
        pos = rm.calculate_position_size(entry_price=entry, stop_loss_price=sl)
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}")
        return

    result = (
        f"🧮 **POSITION SIZING: ${plan['ticker']}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Modal: Rp {capital:,.0f}\n"
        f"⚠️ Maks Risiko ({context.args[1]}%): Rp {pos['max_risk_amount']:,.0f}\n"
        f"📦 Rekomendasi Beli: **{pos['lots']} LOT**\n"
        f"💵 Total Nilai Beli: Rp {pos['total_investment']:,.0f}\n"
        f"📊 Dibatasi oleh: {pos['limited_by']}"
    )
    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)


async def watchlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    wl = get_watchlist(update.effective_user.id)
    if not wl:
        text = "🗂 Watchlist kamu masih kosong. Gunakan `/scan TICKER` lalu simpan ke watchlist."
    else:
        text = "🗂 **WATCHLIST KAMU:**\n\n" + "\n".join(f"• ${t}" for t in wl)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def screener_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text(
        "⏳ Menjalankan screening SELURUH saham IHSG...\n"
        "Ini bisa makan waktu beberapa menit (ratusan saham dianalisis satu per satu "
        "dari Yahoo Finance), mohon tunggu ya."
    )
    results = await _run_screening_async()
    text = _format_screener_results(results)
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)


async def _run_screening_async():
    # run_screening bersifat blocking (network I/O ke Yahoo Finance),
    # jalankan di thread terpisah agar tidak memblokir event loop bot.
    import asyncio

    tickers = get_ihsg_tickers()
    if config.SCREENER_MAX_STOCKS > 0:
        tickers = tickers[: config.SCREENER_MAX_STOCKS]

    return await asyncio.to_thread(
        run_screening,
        tickers=tickers,
        max_workers=config.SCREENER_MAX_WORKERS,
        request_delay=config.SCREENER_REQUEST_DELAY,
    )


def _format_screener_results(results) -> str:
    if not results:
        return "ℹ️ Tidak ada saham IHSG yang memenuhi kriteria setup BUY saat ini."

    lines = [f"🔥 **HASIL DAILY SCREENER (IHSG)** — {len(results)} saham lolos 🔥\n"]
    for r in results[:15]:  # batasi biar pesan tidak kepanjangan
        lines.append(
            f"🎯 **${r['ticker'].replace('.JK', '')}** | Rp {r['price']:,.0f} "
            f"(RSI {r['rsi']})\n"
            f"   Entry: {r['entry_zone']} | SL: {r['sl']:,.0f} | "
            f"TP1: {r['tp1']:,.0f} | RRR 1:{r['rrr']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CALLBACK QUERY (INLINE BUTTON) HANDLER
# ---------------------------------------------------------------------------

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "back_home":
        await start(update, context)

    elif data == "info_scan":
        await query.edit_message_text(
            "Gunakan: `/scan TICKER`\nContoh: `/scan BUMI`",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "info_plan":
        await query.edit_message_text(
            "Gunakan: `/plan TICKER ENTRY SL TARGET`\nContoh: `/plan BUMI 140 133 154`",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Kembali", callback_data="back_home")]]
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "show_watchlist":
        wl = get_watchlist(user_id)
        text = (
            "🗂 **WATCHLIST KAMU:**\n\n" + "\n".join(f"• ${t}" for t in wl)
            if wl else "🗂 Watchlist masih kosong."
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data == "run_screener":
        await query.edit_message_text(
            "⏳ Menjalankan screening seluruh saham IHSG... (bisa beberapa menit)"
        )
        results = await _run_screening_async()
        text = _format_screener_results(results)
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data.startswith("save_wl_"):
        ticker = data.split("_", 2)[2]
        added = add_to_watchlist(user_id, ticker)
        msg_text = (
            f"✅ **${ticker}** disimpan ke watchlist!" if added
            else f"ℹ️ **${ticker}** sudah ada di watchlist."
        )
        await query.edit_message_text(
            msg_text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu Utama", callback_data="back_home")]]
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif data.startswith("calc_lot_"):
        ticker = data.split("_", 2)[2]
        plan = LAST_PLAN.get(user_id)
        if not plan or plan.get("ticker") != ticker:
            await query.edit_message_text(
                f"⚠️ Plan untuk ${ticker} tidak ditemukan, jalankan /scan atau /plan lagi."
            )
            return
        await query.edit_message_text(
            f"🧮 **Position Sizing untuk ${ticker}**\n\n"
            f"Kirim: `/size MODAL RISK_PERSEN`\n"
            f"Contoh: `/size 10000000 2` (Modal 10 juta, risiko maks 2%)",
            parse_mode=ParseMode.MARKDOWN,
        )


# ---------------------------------------------------------------------------
# JOB HARIAN (AUTO SCREENER -> KIRIM KE CHANNEL)
# ---------------------------------------------------------------------------

async def daily_screener_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not config.CHANNEL_ID:
        logger.warning("CHANNEL_ID belum diset, lewati auto screener harian.")
        return
    logger.info("Menjalankan auto screening harian...")
    results = await _run_screening_async()
    text = _format_screener_results(results)
    try:
        await context.bot.send_message(
            chat_id=config.CHANNEL_ID, text=text, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Gagal mengirim hasil screener ke channel: {e}")


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def build_application() -> Application:
    config.validate()
    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan_stock))
    app.add_handler(CommandHandler("plan", trading_plan))
    app.add_handler(CommandHandler("size", position_sizing))
    app.add_handler(CommandHandler("watchlist", watchlist_cmd))
    app.add_handler(CommandHandler("screener", screener_cmd))
    app.add_handler(CallbackQueryHandler(button_click))

    if app.job_queue is not None:
        import datetime
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(config.TIMEZONE)
        except Exception:
            tz = None
        app.job_queue.run_daily(
            daily_screener_job,
            time=datetime.time(hour=config.SCREENER_HOUR, minute=config.SCREENER_MINUTE, tzinfo=tz),
            days=(0, 1, 2, 3, 4),  # Senin-Jumat (0=Senin di PTB JobQueue)
        )
    else:
        logger.warning(
            "JobQueue tidak aktif. Install dengan: pip install \"python-telegram-bot[job-queue]\""
        )

    return app


def main() -> None:
    app = build_application()

    if config.MODE == "webhook":
        logger.info(f"Menjalankan bot dalam mode WEBHOOK di port {config.PORT}...")
        app.run_webhook(
            listen="0.0.0.0",
            port=config.PORT,
            url_path=config.BOT_TOKEN,
            webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}",
        )
    else:
        logger.info("Menjalankan bot dalam mode POLLING...")
        app.run_polling()


if __name__ == "__main__":
    main()
