import re
import requests
from mgrs import MGRS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from dotenv import load_dotenv
import os
from urllib.parse import urlparse, parse_qs

load_dotenv()
TOKEN = os.getenv("TOKEN")

m = MGRS()

# Константи для меню
MAIN_MENU = "main_menu"
CONVERT_TO_MGRS = "to_mgrs"
CONVERT_TO_GOOGLE = "to_google"

# Стан користувача
user_state = {}

def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Google Maps → MGRS", callback_data=CONVERT_TO_MGRS),
            InlineKeyboardButton("MGRS → Google Maps", callback_data=CONVERT_TO_GOOGLE),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data=MAIN_MENU)]
    ]
    return InlineKeyboardMarkup(keyboard)

def resolve_short_url(short_url):
    try:
        response = requests.head(short_url, allow_redirects=True)
        return response.url
    except Exception as e:
        print("Помилка при розвʼязанні короткого посилання:", e)
        return None

def extract_coordinates(url):
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)|/(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if match:
        lat = float(match.group(1) or match.group(3))
        lon = float(match.group(2) or match.group(4))
        return lat, lon

    match2 = re.search(r'/search/(-?\d+\.\d+),\+?(-?\d+\.\d+)', url)
    if match2:
        lat = float(match2.group(1))
        lon = float(match2.group(2))
        return lat, lon

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if "query" in query_params:
        val = query_params["query"][0]
        coords_match = re.match(r'(-?\d+\.\d+),(-?\d+\.\d+)', val)
        if coords_match:
            lat = float(coords_match.group(1))
            lon = float(coords_match.group(2))
            return lat, lon

    return None

def convert_to_mgrs(lat, lon):
    return m.toMGRS(lat, lon)

def convert_mgrs_to_latlon(mgrs_string):
    try:
        latlon = m.toLatLon(mgrs_string)
        return latlon
    except Exception:
        return None

def make_google_maps_link(lat, lon):
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state.pop(update.effective_user.id, None)
    await update.message.reply_text(
        "Виберіть тип конвертації:",
        reply_markup=get_main_menu_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice = query.data

    if choice == MAIN_MENU:
        user_state.pop(user_id, None)
        await query.edit_message_text(
            "Виберіть тип конвертації:",
            reply_markup=get_main_menu_keyboard()
        )
    elif choice == CONVERT_TO_MGRS:
        user_state[user_id] = CONVERT_TO_MGRS
        await query.edit_message_text(
            "Надішліть мені посилання з Google Maps (можна коротке).",
            reply_markup=get_back_keyboard()
        )
    elif choice == CONVERT_TO_GOOGLE:
        user_state[user_id] = CONVERT_TO_GOOGLE
        await query.edit_message_text(
            "Надішліть мені координати у форматі MGRS.",
            reply_markup=get_back_keyboard()
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_state:
        await update.message.reply_text(
            "Будь ласка, спершу оберіть тип конвертації через команду /start",
            reply_markup=get_main_menu_keyboard()
        )
        return

    mode = user_state[user_id]

    if mode == CONVERT_TO_MGRS:
        if "maps.app.goo.gl" in text:
            final_url = resolve_short_url(text)
            if final_url:
                coords = extract_coordinates(final_url)
                if coords:
                    lat, lon = coords
                    mgrs_coord = convert_to_mgrs(lat, lon)
                    await update.message.reply_text(
                        f"✅ MGRS координати:\n`{mgrs_coord}`",
                        parse_mode="MarkdownV2",
                        reply_markup=get_back_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "Не вдалося витягти координати з кінцевого посилання.",
                        reply_markup=get_back_keyboard()
                    )
            else:
                await update.message.reply_text(
                    "Не вдалося розпізнати коротке посилання.",
                    reply_markup=get_back_keyboard()
                )
        else:
            coords = extract_coordinates(text)
            if coords:
                lat, lon = coords
                mgrs_coord = convert_to_mgrs(lat, lon)
                await update.message.reply_text(
                    f"✅ MGRS координати:\n`{mgrs_coord}`",
                    parse_mode="MarkdownV2",
                    reply_markup=get_back_keyboard()
                )
            else:
                await update.message.reply_text(
                    "Не вдалося знайти координати у тексті. Надішліть правильне посилання з Google Maps.",
                    reply_markup=get_back_keyboard()
                )

    elif mode == CONVERT_TO_GOOGLE:
        latlon = convert_mgrs_to_latlon(text)
        if latlon:
            lat, lon = latlon
            link = make_google_maps_link(lat, lon)
            await update.message.reply_text(
                f"✅ Посилання на Google Maps:\n{link}",
                reply_markup=get_back_keyboard()
            )
        else:
            await update.message.reply_text(
                "Невірний формат MGRS. Будь ласка, надішліть правильний рядок у форматі MGRS.",
                reply_markup=get_back_keyboard()
            )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Використання:\n"
        "/start - вибір типу конвертації\n"
        "Після вибору надішліть потрібні дані."
    )

def main():
    if not TOKEN:
        print("Помилка: не заданий TOKEN. Встанови змінну середовища TOKEN у файлі .env")
        return
    
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущений...")
    app.run_polling()

if __name__ == "__main__":
    main()
