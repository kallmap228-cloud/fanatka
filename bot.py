import asyncio
import logging
import random
import os
import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramNetworkError

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

async def check_username_status(username: str, session: aiohttp.ClientSession):
    try:
        async with session.get(f"https://t.me/{username}", headers=HEADERS, timeout=3) as resp:
            if resp.status in (429, 403):
                return None
            if resp.status != 200:
                return False
            html = await resp.text()
            if any(marker in html for marker in ["tgme_page_photo", "tgme_page_extra", "tgme_page_description", "suspended"]):
                return False
    except Exception:
        return None

    try:
        async with session.get(f"https://fragment.com/username/{username}", headers=HEADERS, timeout=3) as resp:
            if resp.status == 200:
                f_html = await resp.text()
                blocked_terms = ["Auction", "Sold", "On sale", "Minimum Bid", "Place bid", "Taken", "Unavailable"]
                if any(term in f_html for term in blocked_terms):
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
    await message.answer("👋 Бот готов к работе! Выберите действие ниже:", reply_markup=main_kb())

@dp.message(F.text == "🎲 Найти 5-буквенные")
async def find_5_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    msg = await message.answer("🔎 Ищу подходящий юзернейм...")
    task = asyncio.create_task(search_random_loop(msg, length=5))
    user_tasks[message.from_user.id] = task

@dp.message(F.text == "🎲 Найти 6-буквенные")
async def find_6_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    stop_previous_task(message.from_user.id)
    msg = await message.answer("🔎 Ищу подходящий юзернейм...")
    task = asyncio.create_task(search_random_loop(msg, length=6))
    user_tasks[message.from_user.id] = task

async def search_random_loop(msg: types.Message, length: int):
    try:
        attempts = 0
        async with aiohttp.ClientSession() as session:
            while attempts < 15:
                attempts += 1
                candidates = [generate_readable_username(length) for _ in range(6)]
                tasks = [check_username_status(cand, session) for cand in candidates]
                results = await asyncio.gather(*tasks)
                
                if all(r is None for r in results):
                    await msg.edit_text("⚠️ Telegram ограничил запросы. Подождите 2 минуты.")
                    return

                for cand, status in zip(candidates, results):
                    if status is True:
                        await msg.edit_text(
                            f"✅ Юзернейм найден {length} букв: @{cand}\n\n"
                            f"🔗 https://t.me/{cand}\n"
                            f"🔗 https://fragment.com/username/{cand}",
                            disable_web_page_preview=True
                        )
                        return
                await asyncio.sleep(0.3)
                
            await msg.edit_text("❌ В этой попытке ничего не нашлось. Нажмите кнопку еще раз!")
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
    msg = await message.answer("🔎 Ищу подходящие юзернеймы...")
    task = asyncio.create_task(search_word_loop(msg, word))
    user_tasks[message.from_user.id] = task

async def search_word_loop(msg: types.Message, word: str):
    try:
        candidates = [f"{p}{word}" for p in PREFIXES] + [f"{word}{s}" for s in SUFFIXES]
        random.shuffle(candidates)
        found = []
        
        async with aiohttp.ClientSession() as session:
            batch_size = 6
            for i in range(0, len(candidates), batch_size):
                batch = candidates[i:i + batch_size]
                tasks = [check_username_status(cand, session) for cand in batch]
                results = await asyncio.gather(*tasks)
                
                for cand, status in zip(batch, results):
                    if status is True:
                        found.append(f"@{cand}")
                        if len(found) >= 2:
                            break
                if len(found) >= 2:
                    break
                await asyncio.sleep(0.3)

        if found:
            res = "\n".join(found)
            await msg.edit_text(f"✅ Юзернеймы найдены для «{word}»:\n\n{res}", disable_web_page_preview=True)
        else:
            await msg.edit_text(f"❌ Не удалось найти свободные варианты для «{word}».")
    except asyncio.CancelledError:
        pass

# --- ФИКТИВНЫЙ ВЕБ-СЕРВЕР ДЛЯ БЕСПЛАТНОГО ТАРИФА RENDER ---
async def handle_health(request):
    return web.Response(text="Bot is running!")

async def main():
    # Запускаем виртуальный веб-сервер, чтобы Render не просил денег
    app = web.Application()
    app.router.add_get("/", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    # Запуск самого бота
    while True:
        try:
            await dp.start_polling(bot)
        except (TelegramNetworkError, aiohttp.ClientError):
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
                         
