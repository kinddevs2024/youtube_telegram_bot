
import os
import re
import asyncio
import tempfile
import shutil
from pathlib import Path

import yt_dlp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
# The hosted Telegram Bot API accepts uploads up to 50 MB.
MAX_SIZE = 49 * 1024 * 1024

CAPTION = "👉 @videola_yukla_bot"


def valid_url(url):
    return re.match(
        r"^https?://(www\.|m\.)?(youtube\.com|youtu\.be)/",
        url
    ) is not None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 YouTube Downloader botiga xush kelibsiz!\n\n"
        "YouTube video havolasini yuboring."
    )


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not valid_url(url):
        await update.message.reply_text("❌ YouTube havolasi noto‘g‘ri.")
        return

    context.user_data["url"] = url

    keyboard = [
        [
            InlineKeyboardButton("360p", callback_data="360"),
            InlineKeyboardButton("480p", callback_data="480"),
        ],
        [
            InlineKeyboardButton("720p", callback_data="720"),
            InlineKeyboardButton("1080p", callback_data="1080"),
        ],
        [
            InlineKeyboardButton("Eng yuqori sifat", callback_data="best"),
        ],
    ]

    await update.message.reply_text(
        "📺 Video sifatini tanlang:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def download(url, quality, folder):

    if quality not in {"360", "480", "720", "1080", "best"}:
        raise ValueError("Video sifati noto‘g‘ri.")

    def check_size(progress):
        if progress.get("downloaded_bytes", 0) > MAX_SIZE:
            raise ValueError("Video 49 MB dan katta. Pastroq sifatni tanlang.")

    if quality == "best":
        fmt = "bestvideo*+bestaudio/best"
    else:
        fmt = (
            f"bestvideo*[height<={quality}]+bestaudio/"
            f"best[height<={quality}]/best"
        )

    options = {
        "format": fmt,
        "outtmpl": str(Path(folder) / "%(title).100s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "max_filesize": MAX_SIZE,
        "quiet": False,
        "no_warnings": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "progress_hooks": [check_size],
        "js_runtimes": {"node": {"path": shutil.which("node") or "node"}},
        "format_sort": ["res", "ext:mp4:m4a"],
    }

    cookie_source = os.getenv("YOUTUBE_COOKIES_FILE")
    if cookie_source:
        # yt-dlp updates its cookie jar; keep the supplied secret read-only.
        cookie_copy = Path(folder) / "youtube-cookies.txt"
        shutil.copyfile(cookie_source, cookie_copy)
        cookie_copy.chmod(0o600)
        options["cookiefile"] = str(cookie_copy)

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    files = [
        f for f in Path(folder).iterdir()
        if f.is_file() and f.suffix.lower() in (
            ".mp4", ".mkv", ".webm", ".mov"
        )
    ]

    if not files:
        raise Exception("Video yuklanmadi yoki 49 MB dan katta. Pastroq sifatni tanlang.")

    video = max(files, key=lambda f: f.stat().st_size)

    if video.stat().st_size > MAX_SIZE:
        raise Exception("Video 49 MB dan katta. Pastroq sifatni tanlang.")

    return video


async def choose_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("url")
    quality = query.data

    if not url:
        await query.edit_message_text(
            "Havola topilmadi. Qayta yuboring."
        )
        return

    await query.edit_message_text("⏳ Video yuklanmoqda...")

    try:
        with tempfile.TemporaryDirectory() as folder:

            video = await asyncio.to_thread(
                download, url, quality, folder
            )

            size = video.stat().st_size / (1024 * 1024)

            await query.message.reply_text(
                f"📤 Telegram'ga video yuborilmoqda: {size:.1f} MB"
            )

            with open(video, "rb") as f:
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    caption=CAPTION,
                    supports_streaming=True,
                    filename=video.name,
                    read_timeout=3600,
                    write_timeout=3600,
                    connect_timeout=60,
                    pool_timeout=60,
                )

        await query.message.reply_text("✅ Tayyor!")

    except Exception as error:
        await query.message.reply_text(
            f"❌ Xatolik: {str(error)[:500]}"
        )


def main():

    if not TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida topilmadi!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)
    )

    app.add_handler(
        CallbackQueryHandler(choose_quality, pattern=r"^(360|480|720|1080|best)$")
    )

    print("BOT ISHGA TUSHDI!")

    app.run_polling()


if __name__ == "__main__":
    main()
