# 🎵 FINAL CLEAN MUSIC BOT (FIXED VERSION)

import os
import re
import json
import random
import string
import sqlite3
import hashlib
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
import yt_dlp


BOT_TOKEN = "8746618909:AAFTS7g8hv8qIlFdPNCRFESMftKXIyrFHqU"
BOT_USERNAME = "@MUSIC_Flexxyrich_bot"

DB_PATH = "musicbot.db"
MUSIC_DIR = Path("music_storage")
MUSIC_DIR.mkdir(exist_ok=True)

(SET_PASSWORD, CONFIRM_PASSWORD,
 ENTER_PASSWORD_VIEW,
 RESET_ASK_KEY, RESET_NEW_PASS, RESET_CONFIRM_PASS,
 REGEN_KEYS_CONFIRM,
 AWAIT_VIDEO_LINK) = range(8)


# ───── DATABASE ─────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            password TEXT,
            keys TEXT
        );

        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            name TEXT
        );

        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id INTEGER,
            title TEXT,
            file_path TEXT
        );
        """)


def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def generate_keys():
    return [''.join(random.choices(string.ascii_uppercase + string.digits, k=8)) for _ in range(3)]


# ───── UI ─────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Account", callback_data="account"),
         InlineKeyboardButton("🔗 Referral", callback_data="ref")],
        [InlineKeyboardButton("💾 Saved", callback_data="saved"),
         InlineKeyboardButton("🔑 Password", callback_data="password")]
    ])


# ───── AUDIO DOWNLOAD ─────
def download_audio(query, folder):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(folder / "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
        "quiet": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            info = info["entries"][0]

            title = re.sub(r'[\\/*?:"<>|]', "", info["title"])

            files = list(folder.glob("*.mp3"))
            latest = sorted(files, key=lambda x: x.stat().st_mtime)[-1]

            return title, str(latest)
    except:
        return None


# ───── START ─────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Welcome!", reply_markup=main_keyboard())


# ───── BUTTON HANDLER ─────
async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "account":
        await query.edit_message_text(f"Your ID: {query.from_user.id}")

    elif query.data == "ref":
        link = f"https://t.me/{BOT_USERNAME}?start={query.from_user.id}"
        await query.edit_message_text(link)

    elif query.data == "saved":
        await query.edit_message_text("Enter password:")
        return ENTER_PASSWORD_VIEW

    elif query.data == "password":
        await query.edit_message_text("Set password:")
        return SET_PASSWORD


# ───── PASSWORD FLOW ─────
async def set_pass(update, ctx):
    ctx.user_data["pw"] = update.message.text
    await update.message.reply_text("Confirm password:")
    return CONFIRM_PASSWORD


async def confirm_pass(update, ctx):
    if update.message.text != ctx.user_data["pw"]:
        await update.message.reply_text("Mismatch ❌")
        return ConversationHandler.END

    keys = generate_keys()
    hashed = hash_password(update.message.text)

    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO users VALUES (?,?,?,?)",
                     (update.effective_user.id, "", hashed, json.dumps(keys)))

    await update.message.reply_text(f"Saved!\nKeys:\n{keys}")
    return ConversationHandler.END


# ───── VIEW SAVED ─────
async def check_pass(update, ctx):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE chat_id=?",
                           (update.effective_user.id,)).fetchone()

    if not row or hash_password(update.message.text) != row["password"]:
        await update.message.reply_text("Wrong ❌")
        return ConversationHandler.END

    await update.message.reply_text("Access Granted ✅")
    return ConversationHandler.END


# ───── FOLDER COMMAND ─────
async def folder_song(update, ctx):
    chat_id = update.effective_user.id
    parts = update.message.text.split()

    folder = parts[0][1:]
    song = " ".join(parts[1:])

    user_folder = MUSIC_DIR / str(chat_id) / folder
    user_folder.mkdir(parents=True, exist_ok=True)

    msg = await update.message.reply_text("Searching...")

    result = download_audio(song, user_folder)

    if result:
        title, path = result
        await msg.edit_text("Sending...")
        with open(path, "rb") as f:
            await update.message.reply_audio(f, title=title)
    else:
        await msg.edit_text("Send link manually")


# ───── MAIN ─────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app