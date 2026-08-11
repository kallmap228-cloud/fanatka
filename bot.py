import asyncio
import logging
import random
import os
import time
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

user_searches = {}

VOWELS = "aeiou"
CONSONANTS = "bcdfghklmnpqrstvwxz"

PREFIXES = ["get", "my", "the", "iam", "hey", "go", "pro", "real", "app", "open", "just", "one", "try", "use", "top", "fast", "pure", "easy", "meta", "cyber"]
SUFFIXES = ["lab", "hub", "pro", "box", "net", "app", "top", "vip", "one", "dev", "zone", "spot", "space", "base", "site", "io", "co", "me", "hq", "inc"]

SPINNERS = ["⚡️", "📡", "🔍", "🎲", "🔄", "✨"]

KNOWN_TAKEN = {
    "admin", "owner", "group", "channel", "music", "photo", "video", "media", "world",
    "super", "cyber", "smart", "store", "cloud", "happy", "black", "white", "gamer",
    "agent", "apple", "money", "space", "poker", "coins", "trade", "trend", "flash",
    "magic", "house", "hotel", "beach", "party", "dance", "night", "light", "dream",
    "smile", "heart", "angel", "devil", "ghost", "witch", "ninja", "pirate", "robot",
    "alien", "tiger", "lion", "bear", "wolf", "eagle", "shark", "whale", "snake",
    "paper", "stone", "water", "earth", "fire", "storm", "solar", "lunar", "star",
    "planet", "galaxy", "astro", "cosmo", "delta", "alpha", "omega", "sigma", "ultra",
    "crypto", "bitcoin", "coin", "token", "chain", "block", "wallet", "market"
}

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

async def cancel_and_clean_previous(user_id: int):
    """ Отменяет прошлый поиск и мгновенно удаляет старое сообщение """
    if user_id in user_searches:
        data = user_searches.pop(user_id)
        task = data.get("task")
        msg = data.get("msg")
        
        if task and not task.done():
            task.cancel()
        if msg:
            with suppress(Exception):
                await msg.delete()

async def check_web_sources(username: str, session: ClientSession) -> bool:
    """ Молниеносная проверка веб-страниц с таймаутом 0.8 сек """
    try:
        url = f"https://fragment.com/username/{username}"
        async with session.get(url, headers=HEADERS, timeout=ClientTimeout(total=0.8)) as resp:
            if resp.status == 200:
                html = await resp.text()
                invalid_markers = ["Auction", "Sold", "On sale", "Minimum Bid", "Place bid", "Buy for", "Taken", "Owner"]
                if any(marker in html for marker in invalid_markers):
                    return False
    except Exception:
        pass

    try:
        url = f"https://t.me/{username}"
        async with session.get(url, headers=HEADERS, timeout=ClientTimeout(total=0.8)) as resp:
            if resp.status == 200:
                html = await resp.text()
                if any(m in html for m in ["tgme_page_photo", "tgme_page_extra", "tgme_page_description", "suspended"]):
                    return False
    except Exception:
        pass

    return True

async def is_username_free(username: str, session: ClientSession) -> bool:
    if username in KNOWN_TAKEN:
        return False

    # 1. Мгновенная проверка через Bot API
    try:
        await bot.get_chat(f"@{username}")
        return False  # Найдено -> Занято
    except TelegramBadRequest as e:
        if "chat not found" not in e.message.lower():
            return False
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        return False
    except Exception:
        return False

    # 2. Проверка веб-ресурсов (Fragment / t.me) с жестким лимитом по времени
    try:
        return await asyncio.wait_for(check_web_sources(username, session), timeout=1.2)
    except Exception:
        return False

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
    await cancel_and_clean_previous(message.from_user.id)
    await message.answer("👋 **Сканер юзернеймов готов к работе!**\nВыберите нужный вариант ниже:", reply_markup=main_kb(), parse_mode="Markdown")

@dp.message(F.text == "🎲 Найти 5-буквенные")
async def find_5_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await cancel_and_clean_previous(message.from_user.id)
    msg = await message.answer("⚡️ **Запуск сканера 5-буквенных юзернеймов...**", parse_mode="Markdown")
    
    task = asyncio.create_task(search_random_loop(msg, length=5, user_id=message.from_user.id))
    user_searches[message.from_user.id] = {"task": task, "msg": msg}

@dp.message(F.text == "🎲 Найти 6-буквенные")
async def find_6_letters(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await cancel_and_clean_previous(message.from_user.id)
    msg = await message.answer("⚡️ **Запуск сканера 6-буквенных юзернеймов...**", parse_mode="Markdown")
    
    task = asyncio.create_task(search_random_loop(msg, length=6, user_id=message.from_user.id))
    user_searches[message.from_user.id] = {"task": task, "msg": msg}

async def search_random_loop(msg: types.Message, length: int, user_id: int):
    try:
        count = 0
        start_time = time.time()
        last_update = 0
        
        async with ClientSession() as session:
            while True:
                count += 1
                cand = generate_readable_username(length)
                current_time = time.time()

                # Плавная анимация каждые 1.2 секунды
                if current_time - last_update >= 1.2:
                    last_update = current_time
                    elapsed = int(current_time - start_time)
                    spinner = SPINNERS[count % len(SPINNERS)]
                    
                    text = (
                        f"<b>{spinner} СКАНИРОВАНИЕ TELEGRAM</b>\n\n"
                        f"🎯 <b>Цель:</b> {length}-буквенные юзернеймы\n"
                        f"⏱ <b>Время в поиске:</b> {elapsed} сек.\n"
                        f"📊 <b>Проверено вариантов:</b> {count}\n"
                        f"👀 <b>Проверяю сейчас:</b> <code>@{cand}</code>\n\n"
                        f"──────────────────\n"
                        f"<i>💡 Нажмите любую кнопку для отмены</i>"
                    )
                    with suppress(Exception):
                        await msg.edit_text(text, parse_mode="HTML")

                # Проверка юзернейма
                try:
                    if await is_username_free(cand, session):
                        elapsed = int(time.time() - start_time)
                        result_text = (
                            f"<b>🎉 НАЙДЕН СВОБОДНЫЙ ЮЗЕРНЕЙМ!</b>\n\n"
                            f"⏱ <b>Время поиска:</b> {elapsed} сек.\n"
                            f"📊 <b>Проверено:</b> {count} вариантов\n\n"
                            f"<b>Нажмите, чтобы скопировать:</b>\n"
                            f"• С собачкой: <code>@{cand}</code>\n"
                            f"• Без собачки: <code>{cand}</code>\n\n"
                            f"🔗 <a href='https://t.me/{cand}'>Открыть в Telegram</a>\n"
                            f"🔗 <a href='https://fragment.com/username/{cand}'>Проверить на Fragment</a>"
                        )
                        await msg.edit_text(result_text, parse_mode="HTML", disable_web_page_preview=True)
                        user_searches.pop(user_id, None)
                        return
                except Exception:
                    pass
                
                await asyncio.sleep(0.02)
    except asyncio.CancelledError:
        pass

@dp.message(F.text == "🔍 Поиск по слову")
async def ask_word(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await cancel_and_clean_previous(message.from_user.id)
    await state.set_state(Form.waiting_for_word)
    await message.answer("Введите базовое слово (например: `apple` или `tiger`):")

@dp.message(Form.waiting_for_word)
async def process_word(message: types.Message, state: FSMContext):
    word = message.text.strip().lower()
    await state.clear()
    
    if not word.isalpha():
        await message.answer("⚠️ Вводите только буквы латинского алфавита.")
        return

    await cancel_and_clean_previous(message.from_user.id)
    msg = await message.answer(f"🔎 Сканирую варианты для «{word}»...")
    
    task = asyncio.create_task(search_word_loop(msg, word, user_id=message.from_user.id))
    user_searches[message.from_user.id] = {"task": task, "msg": msg}

async def search_word_loop(msg: types.Message, word: str, user_id: int):
    try:
        candidates = [f"{p}{word}" for p in PREFIXES] + [f"{word}{s}" for s in SUFFIXES]
        random.shuffle(candidates)
        found = []
        
        async with ClientSession() as session:
            for cand in candidates:
                try:
                    if await is_username_free(cand, session):
                        found.append(f"<code>@{cand}</code>")
                        if len(found) >= 2:
                            break
                except Exception:
                    pass
                await asyncio.sleep(0.05)

        if found:
            res = "\n".join(found)
            await msg.edit_text(
                f"<b>✅ Найдены свободные варианты для «{word}» (нажмите для копирования):</b>\n\n{res}", 
                parse_mode="HTML", 
                disable_web_page_preview=True
            )
        else:
            await msg.edit_text(f"❌ Все комбинации для «{word}» оказались заняты.")
        
        user_searches.pop(user_id, None)
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
