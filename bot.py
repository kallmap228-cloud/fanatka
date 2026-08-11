import asyncio
import logging
import random
import os
from contextlib import suppress
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter, TelegramNetworkError

# ==================== НАСТРОЙКИ ВЛАДЕЛЬЦА ====================
BOT_TOKEN = "8984242690:AAH0YZPbOLLXWe7Zu2OZlFOmKDDe9flNN8g"
ADMIN_ID = 8974383241
# ============================================================

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

user_tasks = {}

VOWELS = "aeiou"
CONSONANTS = "bcdfghklmnpqrstvwxz"

PREFIXES = ["get", "my", "the", "iam", "hey", "go", "pro", "real", "app", "open", "just", "one", "try", "use", "top", "fast", "pure", "easy", "meta", "cyber"]
SUFFIXES = ["lab", "hub", "pro", "box", "net", "app", "top", "vip", "one", "dev", "zone", "spot", "space", "base", "site", "io", "co", "me", "hq", "inc"]

class Form(StatesGroup):
    waiting_for_word = State()

def generate_readable_username(length: int) -> str:
    """ Генерация читаемых юзернеймов (чередование согласных и гласных) """
    res = []
    start_with_consonant = random.choice([True, False])
    for i in range(length):
        if (i % 2 == 0 and start_with_consonant) or (i % 2 != 0 and not start_with_consonant):
            res.append(random.choice(CONSONANTS))
        else:
            res.append(random.choice(VOWELS))
    return "".join(res)

async def is_username_free(username: str) -> bool:
    """ Нативная проверка через официальный Bot API Telegram """
    try:
        await bot.get_chat(f"@{username}")
        return False  # Если чат найден — юзернейм занят
    except TelegramBadRequest as e:
        # Ошибка "chat not found" означает, что юзернейм полностью свободен!
        if "chat not found" in e.message.lower():
            return True
        return False
    except TelegramRetryAfter as e:
        # Если Telegram просит снизить скорость
        await asyncio.sleep(e.retry_after)
        return await is_username_free(username)
    except Exception:
        return False

def stop_previous_task(user_id: int):
    if user_id in user_tasks and not user_tasks[user_id].done():
        user_tasks[user_id].cancel()

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Найти 5-буквенные"), KeyboardButton(text="🎲 Найти 6-буквенные")],
            [KeyboardButton(text="🔍 Поиск по слову")]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    await message.answer("👋 Бот обновлен и переведен на прямой API Telegram! Выберите действие:", reply_markup=main_kb())

@dp.message(F.text == "🎲 Найти 5-буквенные")
async def find_5_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    msg = await message.answer("🔎 Запускаю прямой поиск 5-буквенных юзернеймов...")
    task = asyncio.create_task(search_random_loop(msg, length=5))
    user_tasks[message.from_user.id] = task

@dp.message(F.text == "🎲 Найти 6-буквенные")
async def find_6_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    msg = await message.answer("🔎 Запускаю прямой поиск 6-буквенных юзернеймов...")
    task = asyncio.create_task(search_random_loop(msg, length=6))
    user_tasks[message.from_user.id] = task

async def search_random_loop(msg: types.Message, length: int):
    try:
        count = 0
        while True:
            count += 1
            cand = generate_readable_username(length)
            
            # Показываем живой прогресс каждые 15 проверок
            if count % 15 == 0:
                with suppress(Exception):
                    await msg.edit_text(f"🔎 Проверено вариантов: {count}... Ищу свободный {length}-буквенный...")

            if await is_username_free(cand):
                await msg.edit_text(
                    f"✅ **Найден свободный юзернейм ({length} букв):**\n\n"
                    f"👉 `@{cand}`\n\n"
                    f"🔗 https://t.me/{cand}\n"
                    f"🔗 https://fragment.com/username/{cand}",
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                return
            
            await asyncio.sleep(0.08)  # Безопасный интервал для Telegram API
    except asyncio.CancelledError:
        pass

@dp.message(F.text == "🔍 Поиск по слову")
async def ask_word(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    await state.set_state(Form.waiting_for_word)
    await message.answer("Введите базовое слово (например: `apple` или `tiger`):")

@dp.message(Form.waiting_for_word)
async def process_word(message: types.Message, state: FSMContext):
    word = message.text.strip().lower()
    await state.clear()
    
    if not word.isalpha():
        await message.answer("⚠️ Вводите только буквы латинского алфавита.")
        return

    stop_previous_task(message.from_user.id)
    msg = await message.answer(f"🔎 Ищу свободные комбинации для «{word}»...")
    task = asyncio.create_task(search_word_loop(msg, word))
    user_tasks[message.from_user.id] = task

async def search_word_loop(msg: types.Message, word: str):
    try:
        candidates = [f"{p}{word}" for p in PREFIXES] + [f"{word}{s}" for s in SUFFIXES]
        random.shuffle(candidates)
        found = []
        
        for cand in candidates:
            if await is_username_free(cand):
                found.append(f"@{cand}")
                if len(found) >= 2:
                    break
            await asyncio.sleep(0.08)

        if found:
            res = "\n".join(found)
            await msg.edit_text(f"✅ Найдены свободные варианты для «{word}»:\n\n{res}", disable_web_page_preview=True)
        else:
            await msg.edit_text(f"❌ Все стандартные комбинации для «{word}» оказались заняты.")
    except asyncio.CancelledError:
        pass

# --- ВЕБ-СЕРВЕР ДЛЯ БЕСПЛАТНОГО ТАРИФА RENDER ---
async def handle_health(request):
    return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    while True:
        try:
            await dp.start_polling(bot)
        except (TelegramNetworkError, Exception):
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
