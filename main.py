import asyncio
import logging
import contextlib
import io
import os
import threading
import time
import requests
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

from aiogram.types import (
    ChatJoinRequest, InlineKeyboardMarkup, ReplyKeyboardMarkup,
    KeyboardButton, InlineKeyboardButton, Message,
    FSInputFile, BufferedInputFile,
)
from aiogram.filters import Command
from aiogram import Bot, Dispatcher, F, types

import db   # модуль работы с базой

# при старте приложения инициализируем базу
db.init_db()

# 🌐 Flask-сервер для аптайма
app = Flask(__name__)

@app.route('/')
def home():
    return '✅ Бот работает!'

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


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

user_welcome_messages = {}

# --- Хэндлеры ---

async def save_user(user):
    db.save_user(user.id, user.username, user.first_name)

async def is_subscribed(bot: Bot, user_id: int, channel: str) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

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

async def track_subscription(bot: Bot, user_id: int, message: Message):
    for _ in range(24):
        await asyncio.sleep(5)
        if await is_subscribed(bot, user_id, REQUIRED_CHANNEL):
            await message.answer("✅ Подписка есть, сейчас тебя добавят быстрее!")
            break

async def handle_start(message: Message):
    await save_user(message.from_user)
    subscribe_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/+h1MceCx2NK9kNmJi")]
        ]
    )
    await message.answer(
        "🚀 Скоро у нас появится удобное приложение!\n\nА пока можешь подписаться на Telegram-канал 👇",
        reply_markup=subscribe_keyboard
    )

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
            "Чтобы ускорить одобрение заявки, подпишись на канал @svechkinn",
            reply_markup=keyboard
        )
        asyncio.create_task(track_subscription(message.bot, user_id, message))

async def broadcast(bot: Bot, text: str):
    users = db.get_users()
    for user_id, username, first_name in users:
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

# 📢 Рассылка медиа (только для админа)
async def handle_broadcast_media(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.reply_to_message:
        await message.answer("❌ Используй команду /broadcast_media как ответ на медиа‑сообщение")
        return

    users = db.get_users()
    for user_id, username, first_name in users:
        try:
            await message.reply_to_message.copy_to(chat_id=user_id)
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Не удалось отправить {user_id}: {e}")

    await message.answer("✅ Рассылка медиа завершена")

async def handle_list_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = db.get_users()
    if not users:
        await message.answer("❌ Пока нет сохранённых пользователей")
        return
    lines = []
    for user_id, username, first_name in users:
        name = username if username else first_name
        lines.append(f"{user_id} — {name}")
    user_list = "\n".join(lines)
    await message.answer(f"📋 Список пользователей:\n{user_list}")

async def handle_export_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = db.get_users()
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

# 🚀 Основная функция
async def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"
    )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # регистрируем хэндлеры
    dp.chat_join_request.register(approve_request, F.chat.id == CHANNEL_ID)
    dp.message.register(handle_start, F.text == "/start")
    dp.message.register(handle_broadcast_media, F.text == "/broadcast_media")
    dp.message.register(handle_broadcast, F.text.startswith("/broadcast"))
    dp.message.register(handle_list_users, F.text == "/list_users")
    dp.message.register(handle_export_users, F.text == "/export_users")
    dp.message.register(handle_any_message, F.text)

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as ex:
        logging.error(f'[Exception]: {ex}', exc_info=True)
    finally:
        await bot.session.close()

# 🔄 Самопинг
def ping_self():
    while True:
        try:
            requests.get("https://telegram-flask-bot-production-eb79.up.railway.app")
        except:
            pass
        time.sleep(600)


threading.Thread(target=ping_self).start()

if __name__ == '__main__':
    keep_alive()  # запуск Flask-сервера
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())