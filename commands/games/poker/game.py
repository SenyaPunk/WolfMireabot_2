"""Стадия набора игроков в Покер (Техасский Холдем)."""
import asyncio
import time
import logging
from pathlib import Path
from typing import Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile

from utils.economy_manager import EconomyManager
from utils.admin_manager import AdminManager
from utils.user_link import get_user_link
from utils.error_handler import send_error_message
from utils.game_state_manager import GameStateManager
from .helpers import (
    safe_edit_message_caption,
    safe_edit_message_text,
    safe_send_message,
    safe_delete_message,
    abort_poker_and_refund
)

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
admin_manager = AdminManager()
game_state_manager = GameStateManager()

MIN_PLAYERS = 2
MAX_PLAYERS = 6
RECRUITMENT_TIME = 60
DEFAULT_BLIND = 20

# Хранилище активных наборов: game_key -> dict
active_poker_recruiting: Dict[str, Dict[str, Any]] = {}


def get_poker_game_key(chat_id: int) -> str:
    return f"poker_game:{chat_id}"


def format_time_remaining(seconds: float) -> str:
    secs = max(0, int(seconds))
    mins = secs // 60
    s = secs % 60
    return f"{mins:02d}:{s:02d}"


def get_recruitment_keyboard(chat_id: int, players_count: int, can_start: bool) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"🤝 Присоединиться ({players_count}/{MAX_PLAYERS})",
                callback_data=f"poker_join:{chat_id}"
            ),
            InlineKeyboardButton(
                text="🚪 Покинуть",
                callback_data=f"poker_leave:{chat_id}"
            )
        ]
    ]
    if can_start:
        buttons.append([
            InlineKeyboardButton(text="▶️ Начать досрочно", callback_data=f"poker_start_early:{chat_id}")
        ])
    buttons.append([
        InlineKeyboardButton(text="📖 Правила", callback_data="poker_show_combos_photo"),
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"poker_cancel:{chat_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_recruitment_caption(blind: int, players: List[Dict[str, Any]], remaining_time: float) -> str:
    players_lines = []
    for idx, p in enumerate(players, 1):
        uid = p["user_id"]
        bal = economy_manager.get_balance(uid)
        link = get_user_link(uid)
        players_lines.append(f"{idx}. {link} (💰 {bal})")
    
    players_text = "\n".join(players_lines) if players_lines else "<i>Пока никого нет... Ждем смельчаков!</i>"
    
    return (
        f"🃏 <b>ТЕХАССКИЙ ХОЛДЕМ — НАБОР ЗА СТОЛ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>Большой блайнд (BB):</b> {blind} монет\n"
        f"🪙 <b>Малый блайнд (SB):</b> {blind // 2} монет\n"
        f"👥 <b>Игроков:</b> {len(players)}/{MAX_PLAYERS} (минимум {MIN_PLAYERS})\n"
        f"⏱ <b>Времени на набор:</b> {format_time_remaining(remaining_time)}\n\n"
        f"👥 <b>Участники за столом:</b>\n{players_text}\n\n"
        f"💡 <i>Нажмите <b>«Присоединиться»</b>, чтобы занять место за покерным столом!</i>"
    )


async def update_recruitment_message(bot: Bot, chat_id: int, message_id: int):
    game_key = get_poker_game_key(chat_id)
    if game_key not in active_poker_recruiting:
        return
    
    data = active_poker_recruiting[game_key]
    players = data["players"]
    blind = data["blind"]
    end_time = data["end_time"]
    remaining = end_time - time.time()
    
    if remaining <= 0:
        if len(players) < MIN_PLAYERS:
            active_poker_recruiting.pop(game_key, None)
            cancel_text = (
                f"❌ <b>ПОКЕР — НАБОР ОТМЕНЕН</b>\n\n"
                f"⏰ Время набора истекло.\n"
                f"👥 Недостаточно участников: собралось {len(players)} из необходимых {MIN_PLAYERS}."
            )
            await safe_edit_message_caption(bot, chat_id, message_id, caption=cancel_text)
        else:
            await start_poker_table(bot, chat_id, message_id)
        return
    
    caption = format_recruitment_caption(blind, players, remaining)
    kb = get_recruitment_keyboard(chat_id, len(players), len(players) >= MIN_PLAYERS)
    await safe_edit_message_caption(bot, chat_id, message_id, caption=caption, reply_markup=kb)


@router.message(Command("poker", "покер"))
async def poker_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    
    if not admin_manager.is_admin(message.from_user.id):
        await send_error_message(message, "🚫 Только администраторы могут создавать стол для покера!")
        return
    
    if message.chat.type == "private":
        await send_error_message(message, "🚫 В покер можно играть только в группах и беседах!")
        return
    
    chat_id = message.chat.id
    game_key = get_poker_game_key(chat_id)
    
    # Проверка на зависшую игру
    if game_state_manager.game_exists(game_key):
        game_data = game_state_manager.get_game(game_key)
        started_at = game_data.get("started_at", 0) if isinstance(game_data, dict) else 0
        if started_at == 0 or (time.time() - started_at > 3600):
            logger.warning(f"Auto-cleaning stuck poker game {game_key}")
            await abort_poker_and_refund(bot, chat_id, game_key, game_state_manager, "Сброс зависшей сессии")
        else:
            await send_error_message(message, "🚫 В этом чате уже идет раздача покера! Дождитесь ее окончания.")
            return
            
    if game_key in active_poker_recruiting:
        await send_error_message(message, "🚫 В этом чате уже идет набор игроков в покер!")
        return
        
    # Разбор параметров ставки (блайнда)
    blind = DEFAULT_BLIND
    args = message.text.split()[1:] if message.text else []
    if args and args[0].isdigit():
        custom_blind = int(args[0])
        if 10 <= custom_blind <= 5000:
            blind = custom_blind
            if blind % 2 != 0:
                blind += 1  # Чтобы SB был целым числом
        else:
            await send_error_message(message, "⚠️ Размер блайнда должен быть от 10 до 5000 монет!")
            return
            
    user_id = message.from_user.id
    end_time = time.time() + RECRUITMENT_TIME
    
    # Создатель не добавляется автоматически - за стол может сесть любой желающий
    initial_players = []
    
    active_poker_recruiting[game_key] = {
        "chat_id": chat_id,
        "creator_id": user_id,
        "blind": blind,
        "players": initial_players,
        "end_time": end_time,
        "message_id": None
    }
    
    caption = format_recruitment_caption(blind, initial_players, RECRUITMENT_TIME)
    kb = get_recruitment_keyboard(chat_id, len(initial_players), False)
    
    # Баннер покера Волки МИРЭА
    banner_file = Path("data/assets/poker_banner.jpg")
    photo_to_send = FSInputFile(str(banner_file)) if banner_file.exists() else "https://img.freepik.com/free-photo/poker-chips-cards-green-casino-felt-table_1409-5147.jpg"
    
    try:
        sent_msg = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_to_send,
            caption=caption,
            reply_markup=kb,
            parse_mode="HTML"
        )
        active_poker_recruiting[game_key]["message_id"] = sent_msg.message_id
        
        # Фоновый монитор набора
        asyncio.create_task(_recruitment_timer_worker(bot, chat_id, sent_msg.message_id))
    except Exception as e:
        logger.error(f"Failed to start poker recruitment: {e}", exc_info=True)
        active_poker_recruiting.pop(game_key, None)
        await send_error_message(message, "Ошибка создания стола для покера.")


async def _recruitment_timer_worker(bot: Bot, chat_id: int, message_id: int):
    game_key = get_poker_game_key(chat_id)
    while game_key in active_poker_recruiting:
        await asyncio.sleep(10)
        if game_key not in active_poker_recruiting:
            break
        data = active_poker_recruiting[game_key]
        if time.time() >= data["end_time"]:
            await update_recruitment_message(bot, chat_id, message_id)
            break
        await update_recruitment_message(bot, chat_id, message_id)


@router.callback_query(F.data.startswith("poker_join:"))
async def cb_poker_join(callback: CallbackQuery, bot: Bot):
    chat_id = int(callback.data.split(":")[1])
    game_key = get_poker_game_key(chat_id)
    user_id = callback.from_user.id
    
    if game_key not in active_poker_recruiting:
        await callback.answer("❌ Набор игроков уже завершен или отменен!", show_alert=True)
        return
        
    data = active_poker_recruiting[game_key]
    players = data["players"]
    blind = data["blind"]
    
    if any(p["user_id"] == user_id for p in players):
        await callback.answer("ℹ️ Вы уже присоединились к игре!", show_alert=True)
        return
        
    if len(players) >= MAX_PLAYERS:
        await callback.answer("🚫 За столом больше нет свободных мест (максимум 6)!", show_alert=True)
        return
        
    balance = economy_manager.get_balance(user_id)
    min_required = blind * 2
    if balance < min_required:
        await callback.answer(
            f"🚫 Недостаточно средств!\nНужно минимум {min_required} монет, у вас: {balance}.", 
            show_alert=True
        )
        return
        
    players.append({
        "user_id": user_id,
        "username": callback.from_user.username,
        "first_name": callback.from_user.first_name
    })
    
    await callback.answer("✅ Вы успешно сели за покерный стол!")
    
    if len(players) >= MAX_PLAYERS:
        await start_poker_table(bot, chat_id, data["message_id"])
    else:
        await update_recruitment_message(bot, chat_id, data["message_id"])


@router.callback_query(F.data.startswith("poker_leave:"))
async def cb_poker_leave(callback: CallbackQuery, bot: Bot):
    chat_id = int(callback.data.split(":")[1])
    game_key = get_poker_game_key(chat_id)
    user_id = callback.from_user.id
    
    if game_key not in active_poker_recruiting:
        await callback.answer("❌ Игра уже началась или отменена!", show_alert=True)
        return
        
    data = active_poker_recruiting[game_key]
    players = data["players"]
    
    player_entry = next((p for p in players if p["user_id"] == user_id), None)
    if not player_entry:
        await callback.answer("ℹ️ Вас нет за этим столом.", show_alert=True)
        return
        
    players.remove(player_entry)
    await callback.answer("🚪 Вы покинули покерный стол.")
    
    if len(players) == 0:
        active_poker_recruiting.pop(game_key, None)
        await safe_delete_message(bot, chat_id, data["message_id"])
    else:
        await update_recruitment_message(bot, chat_id, data["message_id"])


@router.callback_query(F.data.startswith("poker_start_early:"))
async def cb_poker_start_early(callback: CallbackQuery, bot: Bot):
    chat_id = int(callback.data.split(":")[1])
    game_key = get_poker_game_key(chat_id)
    user_id = callback.from_user.id
    
    if game_key not in active_poker_recruiting:
        await callback.answer("❌ Набор уже завершен!", show_alert=True)
        return
        
    data = active_poker_recruiting[game_key]
    if not admin_manager.is_admin(user_id):
        await callback.answer("🚫 Начать раздачу досрочно может только администратор!", show_alert=True)
        return
        
    if len(data["players"]) < MIN_PLAYERS:
        await callback.answer(f"⚠️ Для начала нужно минимум {MIN_PLAYERS} игрока!", show_alert=True)
        return
        
    await callback.answer("▶️ Раздача начинается!")
    await start_poker_table(bot, chat_id, data["message_id"])


@router.callback_query(F.data.startswith("poker_cancel:"))
async def cb_poker_cancel(callback: CallbackQuery, bot: Bot):
    chat_id = int(callback.data.split(":")[1])
    game_key = get_poker_game_key(chat_id)
    user_id = callback.from_user.id
    
    if game_key not in active_poker_recruiting:
        await callback.answer("❌ Игра уже началась или отменена.", show_alert=True)
        return
        
    data = active_poker_recruiting[game_key]
    if not admin_manager.is_admin(user_id):
        await callback.answer("🚫 Отменить стол может только администратор!", show_alert=True)
        return
        
    active_poker_recruiting.pop(game_key, None)
    await callback.answer("❌ Стол отменен.")
    
    cancel_text = (
        f"❌ <b>СТОЛ ДЛЯ ПОКЕРА ЗАКРЫТ</b>\n\n"
        f"Администратор отменил игру."
    )
    await safe_edit_message_caption(bot, chat_id, data["message_id"], caption=cancel_text)


async def start_poker_table(bot: Bot, chat_id: int, message_id: int):
    """Инициализация стола и запуск раздачи."""
    game_key = get_poker_game_key(chat_id)
    if game_key not in active_poker_recruiting:
        return
        
    data = active_poker_recruiting.pop(game_key)
    players = data["players"]
    blind = data["blind"]
    
    # Отправляем сообщение о старте
    try:
        from .table import launch_poker_hand
        await launch_poker_hand(bot, chat_id, message_id, players, blind)
    except Exception as e:
        logger.error(f"Failed to launch poker hand: {e}", exc_info=True)
        await abort_poker_and_refund(bot, chat_id, game_key, game_state_manager, f"Ошибка запуска стола: {e}")


@router.callback_query(F.data.startswith("poker_replay:"))
async def cb_poker_replay(callback: CallbackQuery, bot: Bot):
    blind = int(callback.data.split(":")[1])
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game_key = get_poker_game_key(chat_id)
    
    if not admin_manager.is_admin(user_id):
        await callback.answer("🚫 Только администраторы могут создавать стол для покера!", show_alert=True)
        return
        
    if game_state_manager.game_exists(game_key) or game_key in active_poker_recruiting:
        await callback.answer("⚠️ Стол уже создан или идет игра!", show_alert=True)
        return
        
    bal = economy_manager.get_balance(user_id)
    if bal < blind * 2:
        await callback.answer(f"🚫 Недостаточно монет для игры (нужно {blind * 2}, у вас {bal})", show_alert=True)
        return
        
    await callback.answer("🎰 Открываем стол для новой игры...")
    
    initial_players = []
    end_time = time.time() + RECRUITMENT_TIME
    active_poker_recruiting[game_key] = {
        "chat_id": chat_id,
        "creator_id": user_id,
        "blind": blind,
        "players": initial_players,
        "end_time": end_time,
        "message_id": None
    }
    
    caption = format_recruitment_caption(blind, initial_players, RECRUITMENT_TIME)
    kb = get_recruitment_keyboard(chat_id, len(initial_players), False)
    banner_file = Path("data/assets/poker_banner.jpg")
    photo_to_send = FSInputFile(str(banner_file)) if banner_file.exists() else "https://img.freepik.com/free-photo/poker-chips-cards-green-casino-felt-table_1409-5147.jpg"
    
    try:
        sent_msg = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_to_send,
            caption=caption,
            reply_markup=kb,
            parse_mode="HTML"
        )
        active_poker_recruiting[game_key]["message_id"] = sent_msg.message_id
        asyncio.create_task(_recruitment_timer_worker(bot, chat_id, sent_msg.message_id))
    except Exception as e:
        logger.error(f"Error in poker replay: {e}", exc_info=True)
        active_poker_recruiting.pop(game_key, None)

