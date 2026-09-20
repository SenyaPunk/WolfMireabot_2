"""Вспомогательные функции для покерного модуля."""
import asyncio
import logging
import random
from typing import List, Dict, Any, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from utils.economy_manager import EconomyManager

logger = logging.getLogger(__name__)
economy_manager = EconomyManager()

SUITS = ['S', 'H', 'D', 'C']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']


def create_shuffled_deck() -> List[Dict[str, str]]:
    """Создает и перемешивает стандартную 52-карточную колоду."""
    deck = [{'rank': r, 'suit': s} for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


async def safe_edit_message_text(
    bot: Bot, 
    chat_id: int, 
    message_id: int, 
    text: str, 
    reply_markup=None, 
    parse_mode="HTML"
) -> bool:
    for attempt in range(3):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            return True
        except TelegramRetryAfter as e:
            logger.warning(f"RetryAfter in poker edit_message_text: {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err:
                return True
            logger.warning(f"TelegramBadRequest in poker edit_message_text: {e}")
            return False
        except Exception as e:
            logger.error(f"Error in poker edit_message_text: {e}")
            return False
    return False


async def safe_edit_message_caption(
    bot: Bot, 
    chat_id: int, 
    message_id: int, 
    caption: str, 
    reply_markup=None, 
    parse_mode="HTML"
) -> bool:
    for attempt in range(3):
        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return True
        except TelegramRetryAfter as e:
            logger.warning(f"RetryAfter in poker edit_message_caption: {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err:
                return True
            logger.warning(f"TelegramBadRequest in poker edit_message_caption: {e}")
            return False
        except Exception as e:
            logger.error(f"Error in poker edit_message_caption: {e}")
            return False
    return False


async def safe_send_message(
    bot: Bot, 
    chat_id: int, 
    text: str, 
    reply_markup=None, 
    parse_mode="HTML", 
    reply_to_message_id: Optional[int] = None
):
    for attempt in range(3):
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                reply_to_message_id=reply_to_message_id,
                disable_web_page_preview=True
            )
        except TelegramRetryAfter as e:
            logger.warning(f"RetryAfter in poker send_message: {e.retry_after}s")
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest as e:
            if reply_to_message_id:
                reply_to_message_id = None
                continue
            logger.error(f"TelegramBadRequest in poker send_message: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in poker send_message: {e}")
            return None
    return None


async def safe_delete_message(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def abort_poker_and_refund(
    bot: Bot, 
    chat_id: int, 
    game_key: str, 
    game_state_manager, 
    reason: str = "Произошла ошибка"
):
    """Отменяет игру в покер, возвращает ставки и очищает таймеры."""
    logger.error(f"Aborting poker game {game_key} in chat {chat_id}. Reason: {reason}")
    
    try:
        from .betting import cancel_poker_timer
        cancel_poker_timer(game_key)
    except Exception:
        pass

    try:
        from .game import active_poker_recruiting
        active_poker_recruiting.pop(game_key, None)
    except Exception:
        pass

    refunds = []
    if game_state_manager.game_exists(game_key):
        game_data = game_state_manager.get_game(game_key)
        if game_data:
            bets = game_data.get("bets", {})
            for player in game_data.get("players", []):
                uid = player.get("user_id") if isinstance(player, dict) else player
                if not uid:
                    continue
                bet_amount = bets.get(uid, bets.get(str(uid), 0))
                if bet_amount > 0:
                    economy_manager.add_money(uid, bet_amount)
                    uname = player.get("username") or player.get("first_name") or f"ID{uid}" if isinstance(player, dict) else f"ID{uid}"
                    refunds.append(f"• 👤 <b>{uname}</b>: {bet_amount} монет")
        
        try:
            game_state_manager.delete_game(game_key)
        except Exception as e:
            logger.error(f"Error deleting aborted poker game {game_key}: {e}")

    refund_text = "\n".join(refunds) if refunds else "<i>Ставки не вносились / возвращены</i>"
    msg_text = (
        f"⚠️ <b>ИГРА В ПОКЕР ОТМЕНЕНА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Причина: {reason}\n\n"
        f"💰 <b>Возврат ставок:</b>\n{refund_text}"
    )
    await safe_send_message(bot, chat_id, msg_text)
