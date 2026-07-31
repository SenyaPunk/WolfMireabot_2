"""Команда /drink — симуляция выпивки и пьяный режим сообщений."""
import time
import random
import logging
from typing import Dict, Tuple, Any

from aiogram import Router, F, Bot
from aiogram.filters import Command, Filter
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.cooldown_manager import CooldownManager
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

cooldown_manager = CooldownManager()

MAX_DRINKS = 5
DRINKING_COOLDOWN = 3600  # 1 час кулдаун на выпивку
DRUNK_DURATION = 300      # 5 минут пьяного режима на сообщения

# Хранилище пьяных пользователей: {(user_id, chat_id): {"until": float, "level": int, "drink_id": str, "first_name": str}}
DRUNK_USERS: Dict[Tuple[int, int], Dict[str, Any]] = {}

DRINKS = {
    "beer": {"name": "Пивасик", "emoji": "🍺", "desc": "Легкое Жигулёвское под рыбу"},
    "jager": {"name": "Ягермейстер", "emoji": "🟤", "desc": "Травяной немецкий эликсир"},
    "cognac": {"name": "Коньячок", "emoji": "🥃", "desc": "Армянский 5 звёзд за жизнь"},
    "vodka": {"name": "Водочка", "emoji": "🍸", "desc": "Столичная под соленый огурчик"},
    "absinthe": {"name": "Абсент", "emoji": "🟢", "desc": "Зеленый змей с галлюцинациями"},
    "samogon": {"name": "Самогон", "emoji": "🧪", "desc": "Ядерный первач деда Василия"}
}

DRUNK_MESSAGES = {
    1: "ммм, бля, заебись пошло...\n😊 Тепло приятно разливается по кишкам!",
    2: "аххаха, сука, уже в теме!\nМир засиял радугой, анекдоты рвут пузо!",
    3: "<b>ооо, бля щас заебато пойдет...</b>\nЯзык заплетается, стены пляшут, ноги выписывают кренделя!",
    4: "<i>бляяяя... кто, сука, крутит этот ебаный мир?!</i>\nВсё вертится как в мясорубке!",
    5: "🤢 <b>УУУУХ, БЛЯ... ВЕРТОЛЕТЫ НАХУЙ!</b>\nПолный хлам! В глазах двойной пиздец, автопилот включен!"
}


def randomize_font_styles(text: str, level: int = 1) -> str:
    """Случайно делает некоторые буквы жирными <b>, некоторые курсивом <i>, а некоторые обычными."""
    res = []
    current_style = None  # None, 'b', 'i', 'bi'

    bold_prob = 0.20 + (level * 0.04)
    italic_prob = 0.20 + (level * 0.04)

    for char in text:
        if not char.isalnum():
            if current_style == 'b':
                res.append("</b>")
            elif current_style == 'i':
                res.append("</i>")
            elif current_style == 'bi':
                res.append("</i></b>")
            current_style = None
            res.append(char)
            continue

        r = random.random()
        if r < (bold_prob * 0.35):
            new_style = 'bi'
        elif r < bold_prob:
            new_style = 'b'
        elif r < bold_prob + italic_prob:
            new_style = 'i'
        else:
            new_style = None

        if new_style != current_style:
            if current_style == 'b':
                res.append("</b>")
            elif current_style == 'i':
                res.append("</i>")
            elif current_style == 'bi':
                res.append("</i></b>")

            if new_style == 'b':
                res.append("<b>")
            elif new_style == 'i':
                res.append("<i>")
            elif new_style == 'bi':
                res.append("<b><i>")
            
            current_style = new_style

        res.append(char)

    if current_style == 'b':
        res.append("</b>")
    elif current_style == 'i':
        res.append("</i>")
    elif current_style == 'bi':
        res.append("</i></b>")

    return "".join(res)


def make_drunk_text(text: str, level: int, drink_id: str) -> str:
    if not text:
        return text

    interjections_by_level = {
        1: ["...ик!", "...бля,", "...эээ,", "*икает*", "...понимаешь?"],
        2: ["...ик!", "...сука,", "...бля,", "*ииик!*", "...нах!"],
        3: ["...сука!", "...бля ну,", "...б-братан,", "*ИИИК!*", "...понял?"],
        4: ["...пиздец,", "...эээ бля!", "*ИИК!*", "...нахуй...", "*упал*"],
        5: ["...вертолёты бля!", "...хррр...", "*грохнулся*", "...помогите...", "*ИИИК!*"]
    }

    drink_effects = {
        "beer": ["*БУРП!*", "...ик!", "...поссать надо...", "...пенное!"],
        "jager": ["...ёгерь!", "*танцует*", "...бля травка!", "...за любовь!"],
        "cognac": ["...по-мужски!", "...брат!", "...нахуй!", "...серьёзно!"],
        "vodka": ["...под огурчик!", "...за пацанов!", "...нахуй послал?!", "...эх бля!"],
        "absinthe": ["*зелёный дракон*", "...пришельцы!", "...галлюциноз!", "...змей!"],
        "samogon": ["...ПЕЧЕНЬ!", "...В ХЛАМ!", "*башка!*", "...90 градусов!"]
    }

    words = text.split()
    drunk_words = []
    insert_chance = 0.05 + (level * 0.04)

    for word in words:
        w = list(word)
        new_w = []
        for char in w:
            lower_char = char.lower()
            if lower_char in "аоеиуэыяю" and random.random() < (0.08 * level):
                char = char + (lower_char * random.randint(1, min(level, 3)))
            elif lower_char == "р" and random.random() < (0.10 * level):
                char = char + "-р"
            elif lower_char == "с" and random.random() < (0.10 * level):
                char = char + "сс"
            elif lower_char == "в" and random.random() < (0.10 * level):
                char = char + "-в"
            elif lower_char == "б" and random.random() < (0.08 * level):
                char = char + "-б"
            new_w.append(char)
            
        transformed_word = "".join(new_w)
        drunk_words.append(transformed_word)

        if random.random() < insert_chance:
            if random.random() < 0.35 and drink_id in drink_effects:
                interjection = random.choice(drink_effects[drink_id])
            else:
                interjection = random.choice(interjections_by_level.get(level, interjections_by_level[1]))
            drunk_words.append(interjection)

    raw_drunk_text = " ".join(drunk_words)

    # Применяем смесь случайного выделения жирным и курсивом
    final_text = randomize_font_styles(raw_drunk_text, level=level)
    return final_text


class DrunkUserFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        if not message.from_user or not message.text:
            return False
        if message.chat.type == "private":
            return False
        if message.text.startswith("/") or message.text.startswith("!"):
            return False
        
        key = (message.from_user.id, message.chat.id)
        if key in DRUNK_USERS:
            info = DRUNK_USERS[key]
            if time.time() <= info["until"]:
                return True
            else:
                del DRUNK_USERS[key]
        return False


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
        text=f"🍻 Выпить еще {drink_info['name']}? ({level + 1}/{MAX_DRINKS})",
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
            f"⏰ Голова полностью протрезвеет через {time_str}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return
        
    user_link = get_user_link(user.id, user.first_name)
    await message.reply(
        f"🥃 {user_link}, че нальем в глотку?",
        reply_markup=get_drink_keyboard(user.id),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("drink:"))
async def drink_callback(callback_query: CallbackQuery):
    try:
        _, target_user_id, drink_id, level = callback_query.data.split(":")
        target_user_id = int(target_user_id)
        level = int(level)
    except Exception:
        return
    
    if callback_query.from_user.id != target_user_id:
        try:
            await callback_query.answer("⚠️ Это не вашим алкоголем угощают!", show_alert=True)
        except Exception:
            pass
        return
        
    drink_info = DRINKS.get(drink_id, DRINKS["beer"])
    msg_text = DRUNK_MESSAGES.get(level, DRUNK_MESSAGES[1])
    chat_id = callback_query.message.chat.id
    
    DRUNK_USERS[(target_user_id, chat_id)] = {
        "until": time.time() + DRUNK_DURATION,
        "level": level,
        "drink_id": drink_id,
        "first_name": callback_query.from_user.first_name
    }

    if level == 1:
        cooldown_key = f"drink_cooldown:{target_user_id}:{chat_id}"
        cooldown_manager.set_cooldown(cooldown_key)
        
    user_link = get_user_link(target_user_id, callback_query.from_user.first_name)
    text = (
        f"🥴 <b>{user_link} накатил {drink_info['emoji']} {drink_info['name']}! ({level}/{MAX_DRINKS})</b>\n\n"
        f"{msg_text}"
    )
    
    kb = get_continue_keyboard(target_user_id, drink_id, level) if level < MAX_DRINKS else None
    
    try:
        await callback_query.message.edit_text(
            text=text,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        await callback_query.answer()
    except Exception as e:
        logger.error(f"Error updating drink callback message: {e}")


@router.message(DrunkUserFilter())
async def drunk_message_handler(message: Message, bot: Bot):
    key = (message.from_user.id, message.chat.id)
    info = DRUNK_USERS.get(key)
    if not info:
        return

    level = info.get("level", 1)
    drink_id = info.get("drink_id", "beer")
    user = message.from_user
    user_link = get_user_link(user.id, user.first_name)

    drunk_text = make_drunk_text(message.text, level, drink_id)

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Could not delete drunk user message: {e}")

    header = f"🥴 <b>{user_link}</b>: "
    full_text = f"{header}{drunk_text}"

    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=full_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error sending drunk message: {e}")
