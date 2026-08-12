import asyncio
import logging
import random
import os
import time
from contextlib import suppress

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramNetworkError

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8984242690:AAH0YZPbOLLXWe7Zu2OZlFOmKDDe9flNN8g"
ADMIN_ID = 8974383241
# ===================================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_searches = {}

VOWELS = "aeiou"
CONSONANTS = "bcdfghklmnpqrstvwxz"

def generate_username(length: int) -> str:
    res = []
    for i in range(length):
        res.append(random.choice(CONSONANTS if i % 2 == 0 else VOWELS))
    return "".join(res)

async def cancel_search(user_id: int):
    if user_id in user_searches:
        data = user_searches.pop(user_id)
        if not data["task"].done():
            data["task"].cancel()
        with suppress(Exception):
            await data["msg"].delete()

async def is_username_free(username: str) -> bool:
    """Самый надежный способ: проверка через API Telegram"""
    try:
        await bot.get_chat(f"@{username}")
        return False  # Занят
    except TelegramBadRequest as e:
        if "chat not found" in e.message.lower():
            return True  # Свободен!
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after) # Ждем, если Telegram просит
    except Exception:
        pass
    return False

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await cancel_search(message.from_user.id)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎲 Найти 5-буквенный"), KeyboardButton(text="🎲 Найти 6-буквенный")]
    ], resize_keyboard=True)
    await message.answer("👋 Бот перезапущен. Теперь он работает в «Стабильном режиме» без лишних запросов.", reply_markup=kb)

@dp.message(F.text.in_(["🎲 Найти 5-буквенный", "🎲 Найти 6-буквенный"]))
async def start_search(message: types.Message):
    await cancel_search(message.from_user.id)
    length = 5 if "5" in message.text else 6
    msg = await message.answer(f"🔍 Запуск поиска {length}-буквенных имен...")
    task = asyncio.create_task(search_loop(msg, length, message.from_user.id))
    user_searches[message.from_user.id] = {"task": task, "msg": msg}

async def search_loop(msg: types.Message, length: int, user_id: int):
    count = 0
    start_time = time.time()
    
    while True:
        count += 1
        cand = generate_username(length)
        
        # Обновляем статус каждые 2 секунды (чтобы не спамить в Telegram)
        if count % 5 == 0:
            with suppress(Exception):
                await msg.edit_text(
                    f"📡 <b>Сканирую...</b>\n\n"
                    f"⏱ Прошло: {int(time.time() - start_time)} сек\n"
                    f"📊 Проверено: {count}\n"
                    f"👀 Текущий: <code>@{cand}</code>\n"
                    f"<i>(Бот работает в фоновом режиме)</i>",
                    parse_mode="HTML"
                )

        if await is_username_free(cand):
            await msg.edit_text(
                f"✅ <b>НАЙДЕНО!</b>\n\n"
                f"Юзернейм: <code>@{cand}</code>\n"
                f"🔗 <a href='https://t.me/{cand}'>Открыть в Telegram</a>",
                parse_mode="HTML"
            )
            return

        # Пауза, чтобы не получить бан от Telegram
        await asyncio.sleep(0.5)

# --- БАЗОВЫЙ WEB-СЕРВЕР ДЛЯ RENDER ---
from aiohttp import web
async def handle(request): return web.Response(text="Bot is running")
async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
