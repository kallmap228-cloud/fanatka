import asyncio
import logging
import random
import os
from contextlib import suppress
from aiohttp import web, ClientSession, ClientTimeout

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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
}

class Form(StatesGroup):
    waiting_for_word = State()

def generate_readable_username(length: int) -> str:
    res = []
    start_with_consonant = random.choice([True, False])
    for i in range(length):
        if (i % 2 == 0 and start_with_consonant) or (i % 2 != 0 and not start_with_consonant):
            res.append(random.choice(CONSONANTS))
        else:
            res.append(random.choice(VOWELS))
    return "".join(res)

async def is_username_free(username: str, session: ClientSession) -> bool:
    """
    Тройная проверка доступности:
    1. Telegram Bot API (проверка активных аккаунтов/каналов)
    2. Fragment.com (проверка аукционов, NFT и продаваемых юзернеймов)
    3. t.me (проверка системных блокировок)
    """
    # 1. Проверка через Telegram Bot API
    try:
        await bot.get_chat(f"@{username}")
        return False  # Аккаунт/канал существует -> Занят
    except TelegramBadRequest as e:
        if "chat not found" not in e.message.lower():
            return False  # Забанен или недействителен
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        return await is_username_free(username, session)
    except Exception:
        return False

    # 2. Проверка через Fragment.com (Отсеивает ekafu и подобные NFT)
    try:
        url = f"https://fragment.com/username/{username}"
        async with session.get(url, headers=HEADERS, timeout=ClientTimeout(total=3)) as resp:
            if resp.status == 200:
                html = await resp.text()
                # Маркеры того, что юзернейм на Fragment (продан, на аукционе, занят)
                invalid_markers = [
                    "Auction", "Sold", "On sale", "Minimum Bid", 
                    "Place bid", "Buy for", "Taken", "Owner"
                ]
                if any(marker in html for marker in invalid_markers):
                    return False
    except Exception:
        pass

    # 3. Дополнительная веб-проверка t.me
    try:
        url = f"https://t.me/{username}"
        async with session.get(url, headers=HEADERS, timeout=ClientTimeout(total=3)) as resp:
            if resp.status == 200:
                html = await resp.text()
                if any(m in html for m in ["tgme_page_photo", "tgme_page_extra", "tgme_page_description", "suspended"]):
                    return False
    except Exception:
        pass

    return True

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
    await message.answer("👋 Бот обновлен! Добавлена глубокая проверка Fragment и фильтрация NFT.", reply_markup=main_kb())

@dp.message(F.text == "🎲 Найти 5-буквенные")
async def find_5_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    msg = await message.answer("🔎 Ищу свободный 5-буквенный юзернейм (с фильтром Fragment)...")
    task = asyncio.create_task(search_random_loop(msg, length=5))
    user_tasks[message.from_user.id] = task

@dp.message(F.text == "🎲 Найти 6-буквенные")
async def find_6_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    msg = await message.answer("🔎 Ищу свободный 6-буквенный юзернейм (с фильтром Fragment)...")
    task = asyncio.create_task(search_random_loop(msg, length=6))
    user_tasks[message.from_user.id] = task

async def search_random_loop(msg: types.Message, length: int):
    try:
        count = 0
        async with ClientSession() as session:
            while True:
                count += 1
                cand = generate_readable_username(length)
                
                if count % 15 == 0:
                    with suppress(Exception):
                        await msg.edit_text(f"🔎 Проверено вариантов: {count}... Ищу свободный {length}-буквенный...")

                if await is_username_free(cand, session):
                    # Форматирование HTML для копирования в один клик через <code>
                    text = (
                        f"<b>✅ Найден 100% свободный юзернейм!</b>\n\n"
                        f"Нажмите для копирования:\n"
                        f"• С собачкой: <code>@{cand}</code>\n"
                        f"• Без собачки: <code>{cand}</code>\n\n"
                        f"🔗 <a href='https://t.me/{cand}'>Открыть в Telegram</a>\n"
                        f"🔗 <a href='https://fragment.com/username/{cand}'>Проверить на Fragment</a>"
                    )
                    await msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)
                    return
                
                await asyncio.sleep(0.1)
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
    msg = await message.answer(f"🔎 Ищу свободные варианты для «{word}»...")
    task = asyncio.create_task(search_word_loop(msg, word))
    user_tasks[message.from_user.id] = task

async def search_word_loop(msg: types.Message, word: str):
    try:
        candidates = [f"{p}{word}" for p in PREFIXES] + [f"{word}{s}" for s in SUFFIXES]
        random.shuffle(candidates)
        found = []
        
        async with ClientSession() as session:
            for cand in candidates:
                if await is_username_free(cand, session):
                    found.append(f"<code>@{cand}</code>")
                    if len(found) >= 2:
                        break
                await asyncio.sleep(0.1)

        if found:
            res = "\n".join(found)
            await msg.edit_text(
                f"<b>✅ Найдены варианты для «{word}» (нажмите для копирования):</b>\n\n{res}", 
                parse_mode="HTML", 
                disable_web_page_preview=True
            )
        else:
            await msg.edit_text(f"❌ Все комбинации для «{word}» оказались заняты.")
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
