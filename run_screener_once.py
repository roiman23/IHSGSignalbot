"""
run_screener_once.py
Script sekali-jalan: scan LQ45 lalu kirim hasil ke Telegram, lalu keluar.
Didesain khusus untuk PythonAnywhere "Scheduled Task" (free tier) yang
hanya bisa menjalankan script singkat pada jam tertentu -- BUKAN proses
yang selalu menyala. Untuk bot interaktif (command /scan, /plan, dst)
tetap perlu proses polling/webhook yang selalu hidup (lihat bot.py).
"""

import asyncio

from telegram import Bot
from telegram.constants import ParseMode

import config
from screener import get_ihsg_tickers, run_screening


def format_results(results) -> str:
    if not results:
        return "ℹ️ Tidak ada saham IHSG yang memenuhi kriteria setup BUY hari ini."
    lines = [f"🔥 **HASIL DAILY SCREENER (IHSG)** — {len(results)} saham lolos 🔥\n"]
    for r in results[:15]:
        lines.append(
            f"🎯 **${r['ticker'].replace('.JK', '')}** | Rp {r['price']:,.0f} (RSI {r['rsi']})\n"
            f"   Entry: {r['entry_zone']} | SL: {r['sl']:,.0f} | "
            f"TP1: {r['tp1']:,.0f} | RRR 1:{r['rrr']}"
        )
    return "\n".join(lines)


async def main():
    config.validate()
    if not config.CHANNEL_ID:
        raise RuntimeError("CHANNEL_ID belum diset di environment variable.")

    tickers = get_ihsg_tickers()
    if config.SCREENER_MAX_STOCKS > 0:
        tickers = tickers[: config.SCREENER_MAX_STOCKS]

    results = run_screening(
        tickers=tickers,
        max_workers=config.SCREENER_MAX_WORKERS,
        request_delay=config.SCREENER_REQUEST_DELAY,
    )
    text = format_results(results)

    bot = Bot(token=config.BOT_TOKEN)
    await bot.send_message(chat_id=config.CHANNEL_ID, text=text, parse_mode=ParseMode.MARKDOWN)
    print("Screening selesai dan hasil sudah dikirim ke Telegram.")


if __name__ == "__main__":
    asyncio.run(main())
