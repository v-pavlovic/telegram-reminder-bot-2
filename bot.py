import logging
import json
import os
from datetime import datetime, timedelta
import asyncio

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ─── Setup ────────────────────────────────────────────────
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

PODSETNICI_FILE = "podsetnici.json"

# ─── Pomoćne funkcije za JSON ──────────────────────────────
def ucitaj_podsetnike():
    if not os.path.exists(PODSETNICI_FILE):
        return {}
    with open(PODSETNICI_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def sacuvaj_podsetnike(data):
    with open(PODSETNICI_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── Privremeno čuvanje izbora korisnika ──────────────────
korisnicki_izbor = {}  # { chat_id: "trening" / "lek" / "skola" }

# ─── /start komanda ───────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Zdravo! Ja sam tvoj bot za podsetnike.\n\n"
        "Koristi komandu /biraj da odabereš za šta želiš podsetnik."
    )

# ─── /biraj komanda ───────────────────────────────────────
async def biraj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tastatura = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏋️ 1. Podsetnik za trening?", callback_data="trening")],
        [InlineKeyboardButton("💊 2. Podsetnik za lek?",     callback_data="lek")],
        [InlineKeyboardButton("📚 3. Podsetnik za školu?",   callback_data="skola")],
    ])
    await update.message.reply_text("Izaberi tip podsetnika:", reply_markup=tastatura)

# ─── Kad korisnik klikne dugme (trening/lek/skola) ────────
async def izbor_tipa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tip = query.data  # "trening", "lek" ili "skola"
    chat_id = str(query.message.chat_id)
    korisnicki_izbor[chat_id] = tip

    # Ponudi vremena
    tastatura = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ Za 1 minut (test)",  callback_data="vreme_1")],
        [InlineKeyboardButton("🕐 Za 1 sat",           callback_data="vreme_60")],
        [InlineKeyboardButton("🕕 Za 6 sati",          callback_data="vreme_360")],
        [InlineKeyboardButton("🌅 Za 12 sati",         callback_data="vreme_720")],
        [InlineKeyboardButton("📅 Za 24 sata",         callback_data="vreme_1440")],
    ])

    nazivi = {"trening": "trening", "lek": "lek", "skola": "školu"}
    await query.edit_message_text(
        f"Odabrao si: *{nazivi[tip]}* ✅\nKada da te podsetim?",
        parse_mode="Markdown",
        reply_markup=tastatura
    )

# ─── Kad korisnik izabere vreme ───────────────────────────
async def izbor_vremena(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = str(query.message.chat_id)
    minuti = int(query.data.split("_")[1])  # izvuci broj minuta

    tip = korisnicki_izbor.get(chat_id)
    if not tip:
        await query.edit_message_text("❌ Došlo je do greške. Pokušaj ponovo sa /biraj")
        return

    # Izračunaj kada treba poslati poruku
    vreme_slanja = datetime.now() + timedelta(minutes=minuti)

    # Sačuvaj u JSON
    podsetnici = ucitaj_podsetnike()
    if chat_id not in podsetnici:
        podsetnici[chat_id] = []
    podsetnici[chat_id].append({
        "tip": tip,
        "vreme": vreme_slanja.strftime("%Y-%m-%d %H:%M:%S")
    })
    sacuvaj_podsetnike(podsetnici)

    # Zakažemo slanje poruke
    context.job_queue.run_once(
        posalji_podsetnik,
        when=timedelta(minutes=minuti),
        chat_id=int(chat_id),
        data=tip
    )

    nazivi = {"trening": "trening", "lek": "lek", "skola": "školu"}
    opis_vremena = {
        1: "1 minut",
        60: "1 sat",
        360: "6 sati",
        720: "12 sati",
        1440: "24 sata"
    }

    await query.edit_message_text(
        f"✅ Podsetnik za *{nazivi[tip]}* zakazan!\n"
        f"⏱ Stići će za: *{opis_vremena[minuti]}*\n"
        f"🕐 Tačno vreme: {vreme_slanja.strftime('%H:%M')}",
        parse_mode="Markdown"
    )

# ─── Funkcija koja šalje podsetnik ────────────────────────
async def posalji_podsetnik(context: ContextTypes.DEFAULT_TYPE):
    tip = context.job.data
    chat_id = context.job.chat_id

    nazivi = {"trening": "trening", "lek": "lek", "skola": "školu"}
    emoji = {"trening": "🏋️", "lek": "💊", "skola": "📚"}

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{emoji[tip]} Zdravo! Podsetnik za *{nazivi[tip]}* 🔔",
        parse_mode="Markdown"
    )

# ─── Pokretanje bota ──────────────────────────────────────
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("biraj", biraj))
    app.add_handler(CallbackQueryHandler(izbor_tipa,   pattern="^(trening|lek|skola)$"))
    app.add_handler(CallbackQueryHandler(izbor_vremena, pattern="^vreme_"))

    print("✅ Bot je pokrenut! Pritisni Ctrl+C da ga zaustaviš.")
    app.run_polling()

if __name__ == "__main__":
    main()