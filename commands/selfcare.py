"""Команда /selfcare (самоотсос)."""
import time
import json
import random
import logging
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.cooldown_manager import CooldownManager
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

cooldown_manager = CooldownManager()

DATA_FILE = Path.cwd() / "data" / "selfcare.json"

COOLDOWN_MAP = {
    0: 10800,  # 3 часа
    1: 9000,   # 2.5 часа
    2: 7200,   # 2 часа
    3: 3600    # 1 час
}

COOLDOWN_NAMES = {
    0: "3 часа",
    1: "2.5 часа",
    2: "2 часа",
    3: "1 час"
}


def load_selfcare_data() -> dict:
    try:
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading selfcare data: {e}")
    return {}


def save_selfcare_data(data: dict):
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving selfcare data: {e}")


def get_broken_ribs(user_id: int) -> int:
    data = load_selfcare_data()
    user_data = data.get(str(user_id), {})
    if user_data.get("ribs_broken"):
        return 3
    return user_data.get("broken_ribs", 0)


def set_broken_ribs(user_id: int, count: int):
    data = load_selfcare_data()
    if str(user_id) not in data:
        data[str(user_id)] = {}
    data[str(user_id)]["broken_ribs"] = count
    if count >= 3:
        data[str(user_id)]["ribs_broken"] = True
    save_selfcare_data(data)


def format_time_remaining(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} ч.")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes} мин.")
    parts.append(f"{secs} сек.")
    return " ".join(parts)


SELFCARE_MESSAGES = [
    "🍆 {user} мастерски выполнил самоотсос! Гибкость на высоте! 🤸‍♂️",
    "🔥 {user} показал невероятную растяжку и сделал себе приятно! 😏",
    "💪 {user} порадовал себя минетиком и доказал, что йога - это не только про медитацию! 🧘‍♂️",
    "🎯 {user} достиг новых высот в самообслуживании! Браво! 👏",
    "🌟 {user} порадовался минетиком и продемонстрировал акробатические навыки высшего класса! 🤹‍♂️",
    "🏆 {user} отсосал сам себе и получает золотую медаль по самодостаточности! 🥇",
    "🎪 {user} пососал себе. Да ты бы мог выступать в цирке с такой гибкостью! 🎭"
]

RIBS_MESSAGES = [
    "💀 *ХРУСТ* Ребро треснуло! Но гибкость увеличилась!",
    "🦴 *КРАК* Еще одно ребро пожертвовано ради искусства!",
    "💥 *ЩЕЛК* Боль - это временно, а самоотсос - навсегда!",
    "⚡ *ХРЯСЬ* Ребра ломаются, но дух не сломлен!",
    "🔨 *ТРЕЩ* Жертвы ради великой цели!"
]


@router.message(Command("selfcare", "самоотсос", "минет"))
async def selfcare_command(message: Message, bot: Bot):
    if not message.from_user:
        return
        
    user = message.from_user
    chat_id = message.chat.id
    
    if message.chat.type == "private":
        await send_error_message(message, "🚫 Эта команда работает только в группах!")
        return
        
    cooldown_key = f"selfcare_cooldown:{user.id}:{chat_id}"
    broken_ribs = get_broken_ribs(user.id)
    
    cooldown_time = COOLDOWN_MAP.get(broken_ribs, 10800)
    remaining_time = cooldown_manager.check_cooldown(cooldown_key, cooldown_time)
    
    if remaining_time is not None:
        time_str = format_time_remaining(remaining_time)
        await message.reply(
            f"🚫 <b>Вы уже слишком устали от растяжки!</b>\n\n"
            f"⏰ Силы вернутся через {time_str}\n"
            f"💡 <i>Отдыхайте, спина должна прийти в норму...</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return
        
    cooldown_manager.set_cooldown(cooldown_key)
    
    user_link = get_user_link(user.id, user.first_name)
    success_msg = random.choice(SELFCARE_MESSAGES).format(user=user_link)
    
    if broken_ribs < 3:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🦴 Сломать ребро", callback_data=f"selfcare_break_rib:{user.id}")
        ]])
        await message.reply(
            f"{success_msg}\n\n"
            f"💡 <i>Вы можете уменьшить будущий кулдаун, если сломаете ребро для гибкости!</i>\n"
            f"Текущий кулдаун: {COOLDOWN_NAMES[broken_ribs]}.",
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        await message.reply(
            success_msg,
            parse_mode="HTML",
            disable_web_page_preview=True
        )


@router.callback_query(F.data.startswith("selfcare_break_rib:"))
async def selfcare_break_rib_callback(callback_query: CallbackQuery):
    _, target_user_id = callback_query.data.split(":")
    target_user_id = int(target_user_id)
    
    if callback_query.from_user.id != target_user_id:
        await callback_query.answer("⚠️ Это не ваши ребра трещат!", show_alert=True)
        return
        
    broken_ribs = get_broken_ribs(target_user_id)
    if broken_ribs >= 3:
        await callback_query.answer("Вы уже сломали все 3 ребра!", show_alert=True)
        return
        
    new_ribs = broken_ribs + 1
    set_broken_ribs(target_user_id, new_ribs)
    
    user_link = get_user_link(target_user_id, callback_query.from_user.first_name)
    success_msg = random.choice(SELFCARE_MESSAGES).format(user=user_link)
    
    crack_msg = random.choice(RIBS_MESSAGES)
    new_cd_name = COOLDOWN_NAMES[new_ribs]
    
    if new_ribs < 3:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🦴 Сломать еще ребро", callback_data=f"selfcare_break_rib:{target_user_id}")
        ]])
        text = (
            f"{success_msg}\n\n"
            f"💥 {crack_msg}\n"
            f"Сломано ребер: {new_ribs}/3. Будущий кулдаун уменьшен до {new_cd_name}!"
        )
        await callback_query.message.edit_text(
            text=text,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    else:
        text = (
            f"{success_msg}\n\n"
            f"💥 {crack_msg}\n"
            f"🎉 <b>Все ребра сломаны!</b> Кулдаун уменьшен до {new_cd_name}! Теперь ты настоящий мастер! 🏆"
        )
        await callback_query.message.edit_text(
            text=text,
            reply_markup=None,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
    await callback_query.answer()
