import asyncio
import logging
import contextlib
import sqlite3
import io
import os
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

from aiogram.types import (
    ChatJoinRequest, InlineKeyboardMarkup, ReplyKeyboardMarkup,
    KeyboardButton, InlineKeyboardButton, Message, WebAppInfo,
    FSInputFile,
)
from aiogram.filters import Command
import asyncio
from aiogram import Bot, Dispatcher, F
import logging
import contextlib
import sqlite3
import io
import db   # импортируем наш модуль

# при старте приложения инициализируем базу
db.init_db()
# 🌐 Flask-сервер для UptimeRobot
app_web = Flask('')

@app.route('/')
def home():
    return '✅ Бот работает!'


def run():
    app_web.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 🔐 Загрузка токена из .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 📌 Константы
CHANNEL_ID = -1002217080905
ADMIN_ID = 1008418269
REQUIRED_CHANNEL = "@svechkinn"
TELEGRAM_CHANNEL_LINK = "https://t.me/svechkinn"
TELEGRAM_WEBAPP_URL = "https://yourdomain.com"

user_welcome_messages = {}

# 📂 База пользователей
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT
)
""")
conn.commit()

# Сохранение пользователя
async def save_user(user):
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
        (user.id, user.username, user.first_name)
    )
    conn.commit()

# 🔍 Проверка подписки
async def is_subscribed(bot: Bot, user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

# 🔔 Обработка запроса на вступление
async def approve_request(chat_join: ChatJoinRequest, bot: Bot):
    user_id = chat_join.from_user.id
    if user_id in user_welcome_messages:
        return

    msg = "🔥Здарова! Приму заявку сразу\n\nТолько подтверди что ты не бот - напиши любое сообщение🙏"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Подтвердить")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    sent = await bot.send_message(chat_id=user_id, text=msg, reply_markup=keyboard)
    user_welcome_messages[user_id] = sent.message_id

# 🔄 Фоновая проверка подписки
async def track_subscription(bot: Bot, user_id: int, message: Message):
    for _ in range(24):
        await asyncio.sleep(5)
        if await is_subscribed(bot, user_id, REQUIRED_CHANNEL):
            await message.answer("✅ Подписка есть, сейчас тебя добавят быстрее!")

# ✅ Обработка команды /start
async def handle_start(message: Message):
    await save_user(message.from_user)
    subscribe_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/+h1MceCx2NK9kNmJi")]
        ]
    )
    await message.answer(
        "🚀 Скоро у нас появится удобное приложение!\n\nА пока можешь подписаться на Telegram-канал, чтобы быть в курсе 👇",
        reply_markup=subscribe_keyboard
    )


# ✉️ Обработка любого текста
async def handle_any_message(message: Message):
    await save_user(message.from_user)
    user_id = message.from_user.id
    if user_id in user_welcome_messages:
        await message.answer("Отлично, скоро Администратор добавит тебя! ❗️")
        user_welcome_messages.pop(user_id, None)

        if await is_subscribed(message.bot, user_id, REQUIRED_CHANNEL):
            return

        await asyncio.sleep(15)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="📢 Подписаться", url=TELEGRAM_CHANNEL_LINK)]]
        )
        await message.answer(
            "Чтобы ускорить одобрение заявки, подпишись на переходник-канал @svechkinn",
            reply_markup=keyboard
        )
        asyncio.create_task(track_subscription(message.bot, user_id, message))

# 📢 Простая рассылка
async def broadcast(bot: Bot, text: str):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    for (user_id,) in users:
        try:
            await bot.send_message(chat_id=user_id, text=text)
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Не удалось отправить {user_id}: {e}")

async def handle_broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("❌ Укажи текст: /broadcast <текст>")
        return
    await broadcast(message.bot, text)
    await message.answer("✅ Рассылка завершена")

# 📢 Медиа-рассылка через file_id
async def broadcast_media(bot: Bot, text: str, media_id: str = None, media_type: str = None):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=TELEGRAM_WEBAPP_URL))]
        ]
    )

    for (user_id,) in users:
        try:
            if media_id:
                if media_type == "photo":
                    await bot.send_photo(chat_id=user_id, photo=media_id, caption=text, reply_markup=keyboard)
                elif media_type == "video":
                    await bot.send_video(chat_id=user_id, video=media_id, caption=text, reply_markup=keyboard)
                elif media_type == "document":
                    await bot.send_document(chat_id=user_id, document=media_id, caption=text, reply_markup=keyboard)
            else:
                await bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Не удалось отправить {user_id}: {e}")


async def handle_broadcast_media(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Берём текст из caption, если есть медиа
    if message.caption:
        text = message.caption.replace("/broadcast_media", "").strip()
    else:
        text = message.text.replace("/broadcast_media", "").strip()

    media_id = None
    media_type = None

    if message.photo:
        media_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        media_id = message.video.file_id
        media_type = "video"
    elif message.document:
        media_id = message.document.file_id
        media_type = "document"

    await broadcast_media(message.bot, text, media_id, media_type)
    await message.answer("✅ Медиа-рассылка завершена")

# 📋 Список пользователей
async def handle_list_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT user_id, username, first_name FROM users")
    users = cursor.fetchall()
    if not users:
        await message.answer("❌ Пока нет сохранённых пользователей")
        return
    lines = []
    for user_id, username, first_name in users:
        name = username if username else first_name
        lines.append(f"{user_id} — {name}")
    user_list = "\n".join(lines)
    await message.answer(f"📋 Список пользователей:\n{user_list}")

# 📂 Экспорт пользователей в CSV
async def handle_export_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT user_id, username, first_name FROM users")
    users = cursor.fetchall()
    if not users:
        await message.answer("❌ Пока нет сохранённых пользователей")
        return

    output = io.StringIO()
    output.write("user_id,username,first_name\n")
    for user_id, username, first_name in users:
        output.write(f"{user_id},{username or ''},{first_name or ''}\n")
    data = output.getvalue().encode("utf-8")

    file = BufferedInputFile(data, filename="users.csv")
    await message.answer_document(file, caption="📂 Экспорт пользователей")

# 🚀 Запуск бота
async def start():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"
    )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.chat_join_request.register(approve_request, F.chat.id == CHANNEL_ID)
    dp.message.register(handle_start, F.text == "/start")
    dp.message.register(handle_broadcast, F.text.startswith("/broadcast"))
    dp.message.register(handle_broadcast_media, Command("broadcast_media"))
    dp.message.register(handle_list_users, F.text == "/list_users")
    dp.message.register(handle_export_users, F.text == "/export_users")
    dp.message.register(handle_any_message, F.text)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as ex:
        logging.error(f'[Exception]: {ex}', exc_info=True)
    finally:
        await bot.session.close()


import threading
import time
import requests

def ping_self():
    while True:
        try:
            requests.get("https://telegram-flask-bot.onrender.com")
        except:
            pass
        time.sleep(600)  # каждые 10 минут

threading.Thread(target=ping_self).start()


if __name__ == '__main__':
    keep_alive()  # ← добавь эту строку для запуска Flask-сервера
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(start())
