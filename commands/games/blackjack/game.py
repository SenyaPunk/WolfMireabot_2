"""Стадия начала игры (набор)"""
import asyncio
import time
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.admin_manager import AdminManager
from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message
from utils.game_state_manager import GameStateManager
from .betting import start_betting_stage
from .helpers import (
    safe_edit_message_caption,
    safe_edit_message_text,
    safe_send_message,
    safe_delete_message,
    abort_game_and_refund
)

router = Router()
logger = logging.getLogger(__name__)

slave_manager = SlaveManager()

admin_manager = AdminManager()
economy_manager = EconomyManager()
user_storage = UserStorage()
game_state_manager = GameStateManager()

MIN_BALANCE = 20
MIN_PLAYERS = 2
MAX_PLAYERS = 5
RECRUITMENT_TIME = 60  

active_games = {}


def get_game_key(chat_id: int) -> str:
    return f"blackjack_game:{chat_id}"


def format_time_remaining(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    
    if minutes > 0:
        return f"{minutes:02d}:{secs:02d}"
    else:
        return f"00:{secs:02d}"


async def update_recruitment_message(bot: Bot, chat_id: int, message_id: int):
    game_key = get_game_key(chat_id)
    
    if game_key not in active_games:
        return
    
    game_data = active_games[game_key]
    players = game_data.get("players", [])
    end_time = game_data.get("end_time", 0)
    
    remaining_time = max(0, end_time - time.time())
    
    if remaining_time <= 0:
        if len(players) < MIN_PLAYERS:
            active_games.pop(game_key, None)
            
            cancelled_caption = (
                f"❌ <b>БЛЕКДЖЕК - ОТМЕНЕН</b>\n\n"
                f"⏰ Время набора истекло\n"
                f"👥 Недостаточно игроков: {len(players)}/{MIN_PLAYERS}\n\n"
                f"💡 <i>Для начала игры нужно минимум {MIN_PLAYERS} игрока</i>"
            )
            edited = await safe_edit_message_caption(
                bot, chat_id, message_id, caption=cancelled_caption, parse_mode="HTML"
            )
            if not edited:
                await safe_edit_message_text(
                    bot, chat_id, message_id, text=cancelled_caption, parse_mode="HTML"
                )
        else:
            await start_blackjack_game(bot, chat_id, message_id)
        return
    
    player_list = []
    for idx, player_data in enumerate(players, 1):
        user_id = player_data["user_id"]
        balance = economy_manager.get_balance(user_id)
        user_link = get_user_link(user_id)
        player_list.append(f"{idx}. {user_link} (баланс: {balance} монет)")
    
    players_text = "\n".join(player_list) if player_list else "<i>Пока никого нет...</i>"
    
    join_button = InlineKeyboardButton(
        text=f"Присоединиться к игре {len(players)}/{MAX_PLAYERS}",
        callback_data=f"blackjack_join:{chat_id}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[join_button]])
    
    caption = (
        f"🎰 <b>БЛЕКДЖЕК - НАБОР ИГРОКОВ</b>\n\n"
        f"⏰ <b>Время на запись:</b> {format_time_remaining(remaining_time)}\n"
        f"👥 <b>Игроков:</b> {len(players)}/{MAX_PLAYERS}\n"
        f"🎯 <b>Минимум для начала:</b> {MIN_PLAYERS} игрока\n"
        f"💰 <b>Минимальный баланс:</b> {MIN_BALANCE} монет\n\n"
        f"📋 <b>Правила:</b>\n"
        f"• Стандартная колода карт (52 карты)\n"
        f"• Цель: набрать 21 очко или близко к этому путем нажатием на Взять карту. Если вы превысите 21 очко - вы проиграете (перебор)\n"
        f"• Туз = 1 или 11, фигуры = 10\n"
        f"• Больше 21 = проигрыш\n\n"
        f"⚡ <b>Команды админа:</b>\n"
        f"• /блекджек+30сек - добавить 30 секунд\n"
        f"• /блекджек_начать - начать досрочно\n\n"
        f"👥 <b>Игроки:</b>\n{players_text}"
    )
    
    edited = await safe_edit_message_caption(
        bot, chat_id, message_id, caption=caption, reply_markup=keyboard, parse_mode="HTML"
    )
    if not edited:
        await safe_edit_message_text(
            bot, chat_id, message_id, text=caption, reply_markup=keyboard, parse_mode="HTML"
        )


async def recruitment_timer(bot: Bot, chat_id: int, message_id: int):
    game_key = get_game_key(chat_id)
    
    while game_key in active_games:
        try:
            game_data = active_games[game_key]
            end_time = game_data.get("end_time", 0)
            remaining_time = max(0, end_time - time.time())
            
            if remaining_time <= 0:
                await update_recruitment_message(bot, chat_id, message_id)
                break
            
            await update_recruitment_message(bot, chat_id, message_id)
            
            if remaining_time > 10:
                await asyncio.sleep(10)
            else:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in recruitment_timer for chat {chat_id}: {e}", exc_info=True)
            active_games.pop(game_key, None)
            break


async def start_blackjack_game(bot: Bot, chat_id: int, message_id: int):
    game_key = get_game_key(chat_id)
    
    if game_key not in active_games:
        return
    
    game_data = active_games.get(game_key, {})
    players = game_data.get("players", [])
    
    game_state = {
        "players": players,
        "chat_id": chat_id,
        "stage": "starting",
        "started_at": time.time()
    }
    
    game_state_manager.create_game(game_key, game_state)
    active_games.pop(game_key, None)
    
    logger.info(f"Blackjack game started in chat {chat_id} with {len(players)} players")
    
    try:
        await start_betting_stage(bot, chat_id, game_key, game_state_manager)
    except Exception as e:
        logger.error(f"Failed to start betting stage in chat {chat_id}: {e}", exc_info=True)
        await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, f"Ошибка начала приема ставок: {e}")


@router.message(Command("blackjack", "блекджек"))
async def blackjack_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    
    if not admin_manager.is_admin(message.from_user.id):
        await send_error_message(message, "🚫 Только администраторы могут начинать игру в блекджек!")
        return
    
    if message.chat.type == "private":
        await send_error_message(message, "🚫 Эта команда работает только в группах!")
        return
    
    chat_id = message.chat.id
    game_key = get_game_key(chat_id)
    
    # Проверяем, есть ли застрявшая старая игра в game_state_manager
    if game_state_manager.game_exists(game_key):
        game_data = game_state_manager.get_game(game_key)
        started_at = game_data.get("started_at", 0) if isinstance(game_data, dict) else 0
        if started_at == 0 or (time.time() - started_at > 300):
            logger.warning(f"Auto-cleaning stuck game {game_key} in chat {chat_id}")
            await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, "Сброс зависшей старой сессии")
        else:
            await send_error_message(message, "🚫 В этом чате уже идет игра! Дождитесь ее завершения.")
            return

    if game_key in active_games:
        await send_error_message(message, "🚫 В этом чате уже идет набор игроков! Дождитесь завершения набора.")
        return
    
    end_time = time.time() + RECRUITMENT_TIME
    active_games[game_key] = {
        "players": [],
        "end_time": end_time,
        "chat_id": chat_id
    }
    
    join_button = InlineKeyboardButton(
        text=f"Присоединиться к игре 0/{MAX_PLAYERS}",
        callback_data=f"blackjack_join:{chat_id}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[join_button]])
    
    photo_url = "https://img.dni.ru/binaries/game/16/list.jpg"

    try:
        recruitment_msg = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=(
                f"🎰 <b>БЛЕКДЖЕК - НАБОР ИГРОКОВ</b>\n\n"
                f"⏰ <b>Время на запись:</b> {format_time_remaining(RECRUITMENT_TIME)}\n"
                f"👥 <b>Игроков:</b> 0/{MAX_PLAYERS}\n"
                f"🎯 <b>Минимум для начала:</b> {MIN_PLAYERS} игрока\n"
                f"💰 <b>Минимальный баланс:</b> {MIN_BALANCE} монет\n\n"
                f"📋 <b>Правила:</b>\n"
                f"• Стандартная колода карт (52 карты)\n"
                f"• Цель: набрать 21 очко или близко к этому путем нажатием на Взять карту. "
                f"Если вы превысите 21 очко - вы проиграете (перебор)\n"
                f"• Туз = 1 или 11, фигуры = 10\n"
                f"• Больше 21 = проигрыш\n\n"
                f"⚡ <b>Команды админа:</b>\n"
                f"• /блекджек+30сек - добавить 30 секунд\n"
                f"• /блекджек_начать - начать досрочно\n\n"
                f"👥 <b>Игроки:</b>\n<i>Пока никого нет...</i>"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        active_games[game_key]["message_id"] = recruitment_msg.message_id
        asyncio.create_task(recruitment_timer(bot, chat_id, recruitment_msg.message_id))
        logger.info(f"Blackjack recruitment started by {message.from_user.first_name} ({message.from_user.id}) in chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send recruitment message for blackjack in chat {chat_id}: {e}", exc_info=True)
        active_games.pop(game_key, None)
        await send_error_message(message, "❌ Произошла ошибка при запуске набора в Блекджек.")


@router.message(Command("blackjack+30sec", "блекджек+30сек"))
async def blackjack_add_time_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    
    if not admin_manager.is_admin(message.from_user.id):
        await send_error_message(message, "🚫 Только администраторы могут использовать эту команду!")
        return
    
    if message.chat.type == "private":
        await send_error_message(message, "🚫 Эта команда работает только в группах!")
        return
    
    chat_id = message.chat.id
    game_key = get_game_key(chat_id)
    
    if game_key not in active_games:
        await send_error_message(message, "🚫 В этом чате нет активного набора игроков!")
        return
    
    active_games[game_key]["end_time"] += 30
    
    await safe_delete_message(bot, chat_id, message.message_id)
    
    notification = await safe_send_message(
        bot, chat_id,
        f"⏰ <b>+30 секунд добавлено!</b>\n\n"
        f"👤 Администратор {message.from_user.first_name} добавил время",
        parse_mode="HTML"
    )
    
    if notification:
        await asyncio.sleep(3)
        await safe_delete_message(bot, chat_id, notification.message_id)
    
    logger.info(f"30 seconds added to blackjack recruitment by {message.from_user.first_name} ({message.from_user.id}) in chat {chat_id}")


@router.message(Command("blackjack_start", "блекджек_начать"))
async def blackjack_start_early_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    
    if not admin_manager.is_admin(message.from_user.id):
        await send_error_message(message, "🚫 Только администраторы могут использовать эту команду!")
        return
    
    if message.chat.type == "private":
        await send_error_message(message, "🚫 Эта команда работает только в группах!")
        return
    
    chat_id = message.chat.id
    game_key = get_game_key(chat_id)
    
    if game_key not in active_games:
        await send_error_message(message, "🚫 В этом чате нет активного набора игроков!")
        return
    
    game_data = active_games[game_key]
    players = game_data.get("players", [])
    
    if len(players) < MIN_PLAYERS:
        await send_error_message(
            message,
            f"🚫 Недостаточно игроков для начала игры!\n\n"
            f"👥 Сейчас: {len(players)}/{MIN_PLAYERS}\n"
            f"💡 Нужно минимум {MIN_PLAYERS} игрока"
        )
        return
    
    await safe_delete_message(bot, chat_id, message.message_id)
    
    message_id = game_data.get("message_id")
    if message_id:
        await start_blackjack_game(bot, chat_id, message_id)
    
    logger.info(f"Blackjack game started early by {message.from_user.first_name} ({message.from_user.id}) in chat {chat_id}")


@router.callback_query(F.data.startswith("blackjack_join:"))
async def blackjack_join_callback(callback: CallbackQuery, bot: Bot):
    """Присоединиться к игре"""
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    try:
        await callback.answer()
    except Exception:
        pass
    
    try:
        _, chat_id_str = callback.data.split(":")
        chat_id = int(chat_id_str)
    except (ValueError, IndexError):
        try:
            await callback.answer("❌ Ошибка обработки команды.", show_alert=True)
        except Exception:
            pass
        return
    
    user = callback.from_user
    user_id = user.id
    slave_manager.unwhip_slave(user_id)
    
    game_key = get_game_key(chat_id)
    
    if game_key not in active_games:
        try:
            await callback.answer("⏰ Набор игроков уже завершен!", show_alert=True)
        except Exception:
            pass
        return
    
    game_data = active_games[game_key]
    players = game_data.get("players", [])
    
    if len(players) >= MAX_PLAYERS:
        try:
            await callback.answer("🚫 Игра уже заполнена!", show_alert=True)
        except Exception:
            pass
        return
    
    if any(p["user_id"] == user_id for p in players):
        try:
            await callback.answer("ℹ️ Вы уже в игре!", show_alert=True)
        except Exception:
            pass
        return
    
    balance = economy_manager.get_balance(user_id)
    if balance < MIN_BALANCE:
        try:
            await callback.answer(
                f"🚫 Недостаточно монет!\n\n"
                f"💰 Ваш баланс: {balance} монет\n"
                f"💵 Нужно: {MIN_BALANCE} монет",
                show_alert=True
            )
        except Exception:
            pass
        return
    
    players.append({
        "user_id": user_id,
        "username": user.username or user.first_name
    })
    
    active_games[game_key]["players"] = players
    logger.info(f"Player {user.first_name} ({user_id}) joined blackjack in chat {chat_id}")
    
    try:
        await callback.answer(f"✅ Вы присоединились к игре! ({len(players)}/{MAX_PLAYERS})", show_alert=True)
    except Exception:
        pass
    
    message_id = game_data.get("message_id")
    if message_id:
        await update_recruitment_message(bot, chat_id, message_id)


@router.message(Command("blackjack_reset", "блекджек_сброс"))
async def blackjack_reset_command(message: Message, bot: Bot):
    """Принудительный сброс зависшей игры блекджек администратором."""
    if not message.from_user or not admin_manager.is_admin(message.from_user.id):
        await send_error_message(message, "🚫 Только администраторы могут сбрасывать игру!")
        return
        
    chat_id = message.chat.id
    game_key = get_game_key(chat_id)
    
    await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, "Принудительный сброс администратором")
    await message.reply("✅ Сессия игры Блекджек в этом чате успешно сброшена! Все заблокированные ставки возвращены.")
