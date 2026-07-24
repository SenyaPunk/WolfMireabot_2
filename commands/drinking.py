"""Команда /drink — симуляция выпивки."""
import time
import random
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.cooldown_manager import CooldownManager
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

cooldown_manager = CooldownManager()

MAX_DRINKS = 5
DRINKING_COOLDOWN = 3600  # 1 час

DRINKS = {
    "jager": {"name": "Ягерь", "emoji": "🟤"},
    "cognac": {"name": "Коньяк", "emoji": "🥃"},
    "gin": {"name": "Джин", "emoji": "🍸"},
    "absinthe": {"name": "Абсент", "emoji": "🟢"}
}

DRUNK_MESSAGES = {
    1: {
        "text": "ммм, бля, заебись пошло\n😊 тепло разливается по кишкам, настроение - пиздец как прёт вверх"
    },
    2: {
        "text": "ахзвыха, сука, уже в теме!\nмир засиял хуевой радугой, анекдоты рвут пузо, а я чуть не упал от смеха блять"
    },
    3: {
        "text": "<b>ооо, бля щас заебато пойдет...</b>\nязык заплетается в узел, стены пляшут как шлюхи но я еще стою"
    },
    4: {
        "text": "<i>бляяяя... кто</i>, сука, крутит этот ебаный мир\n\nвсе вертится как в мясорубке, бормочу хуйню, но еще не рухнул..."
    },
    5: {
        "text": "🤢 <b>уууух, бля... все, нахуй, завязываю...</b>\n\nмир - сплошной пиздец в карусели, ноги не держат, блевать тянет"
    }
}


def get_drink_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for drink_id, drink_info in DRINKS.items():
        row.append(InlineKeyboardButton(
            text=f"{drink_info['emoji']} {drink_info['name']}",
            callback_data=f"drink:{user_id}:{drink_id}:1"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_continue_keyboard(user_id: int, drink_type: str, level: int) -> InlineKeyboardMarkup:
    if level >= MAX_DRINKS:
        return InlineKeyboardMarkup(inline_keyboard=[])
    drink_info = DRINKS[drink_type]
    button = InlineKeyboardButton(
        text=f"🍻 Выпить еще {drink_info['name']}?",
        callback_data=f"drink:{user_id}:{drink_type}:{level + 1}"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


@router.message(Command("drink", "бухать", "выпить"))
async def drink_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    
    user = message.from_user
    chat_id = message.chat.id
    
    if message.chat.type == "private":
        await send_error_message(message, "🚫 Эта команда работает только в группах!")
        return
        
    cooldown_key = f"drink_cooldown:{user.id}:{chat_id}"
    remaining_time = cooldown_manager.check_cooldown(cooldown_key, DRINKING_COOLDOWN)
    
    if remaining_time is not None:
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        time_str = f"{minutes} мин. {seconds} сек." if minutes > 0 else f"{seconds} сек."
        
        await message.reply(
            f"🤢 <b>Вам уже хватит!</b>\n\n"
            f"⏰ Голова протрезвеет через {time_str}\n"
            f"💡 <i>Подождите, пока алкоголь выйдет из организма...</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return
        
    user_link = get_user_link(user.id, user.first_name)
    await message.reply(
        f"🥃 {user_link}, че нальем в глотку?\n"
        f"Выбирай хрень какую-нибудь, чтоб вштырило:",
        reply_markup=get_drink_keyboard(user.id),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("drink:"))
async def drink_callback(callback_query: CallbackQuery):
    _, target_user_id, drink_id, level = callback_query.data.split(":")
    target_user_id = int(target_user_id)
    level = int(level)
    
    if callback_query.from_user.id != target_user_id:
        await callback_query.answer("⚠️ Это не вашим алкоголем угощают!", show_alert=True)
        return
        
    drink_info = DRINKS[drink_id]
    msg_data = DRUNK_MESSAGES[level]
    
    # Устанавливаем кулдаун на первой рюмке
    if level == 1:
        cooldown_key = f"drink_cooldown:{target_user_id}:{callback_query.message.chat.id}"
        cooldown_manager.set_cooldown(cooldown_key)
        
    user_link = get_user_link(target_user_id, callback_query.from_user.first_name)
    text = (
        f"🥴 <b>Уровень опьянения: {level}/{MAX_DRINKS}</b>\n"
        f"👤 Работяга: {user_link}\n"
        f"Напиток: {drink_info['emoji']} {drink_info['name']}\n\n"
        f"{msg_data['text']}"
    )
    
    kb = get_continue_keyboard(target_user_id, drink_id, level) if level < MAX_DRINKS else None
    
    await callback_query.message.edit_text(
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback_query.answer()
