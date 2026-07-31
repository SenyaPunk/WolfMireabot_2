import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from utils.economy_manager import EconomyManager

logger = logging.getLogger(__name__)
economy_manager = EconomyManager()


async def safe_edit_message_text(bot: Bot, chat_id: int, message_id: int, text: str, reply_markup=None, parse_mode="HTML") -> bool:
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
            logger.warning(f"TelegramRetryAfter in edit_message_text: waiting {e.retry_after}s (attempt {attempt + 1}/3)")
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest as e:
            err_msg = str(e).lower()
            if "message is not modified" in err_msg:
                return True
            logger.warning(f"TelegramBadRequest in edit_message_text: {e}")
            return False
        except Exception as e:
            logger.error(f"Error in edit_message_text: {e}")
            return False
    return False


async def safe_edit_message_caption(bot: Bot, chat_id: int, message_id: int, caption: str, reply_markup=None, parse_mode="HTML") -> bool:
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
            logger.warning(f"TelegramRetryAfter in edit_message_caption: waiting {e.retry_after}s (attempt {attempt + 1}/3)")
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest as e:
            err_msg = str(e).lower()
            if "message is not modified" in err_msg:
                return True
            logger.warning(f"TelegramBadRequest in edit_message_caption: {e}")
            return False
        except Exception as e:
            logger.error(f"Error in edit_message_caption: {e}")
            return False
    return False


async def safe_send_message(bot: Bot, chat_id: int, text: str, reply_markup=None, parse_mode="HTML", reply_to_message_id=None):
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
            logger.warning(f"TelegramRetryAfter in send_message: waiting {e.retry_after}s (attempt {attempt + 1}/3)")
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest as e:
            if reply_to_message_id:
                logger.warning(f"Failed to reply to message {reply_to_message_id}, sending without reply: {e}")
                reply_to_message_id = None
                continue
            logger.error(f"TelegramBadRequest in send_message: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            return None
    return None


async def safe_delete_message(bot: Bot, chat_id: int, message_id: int):
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass


async def abort_game_and_refund(bot: Bot, chat_id: int, game_key: str, game_state_manager, reason: str = "Произошла ошибка"):
    logger.error(f"Aborting game {game_key} in chat {chat_id}. Reason: {reason}")
    
    try:
        from .playing import cancel_player_timer as cancel_playing_timer
        cancel_playing_timer(game_key)
    except Exception:
        pass
        
    try:
        from .betting import cancel_player_timer as cancel_betting_timer
        cancel_betting_timer(game_key)
    except Exception:
        pass

    try:
        from .game import active_games
        active_games.pop(game_key, None)
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
            logger.error(f"Error deleting aborted game {game_key}: {e}")

    refund_text = "\n".join(refunds) if refunds else "<i>Ставки не отнимались / без ставок</i>"
    msg_text = (
        f"⚠️ <b>ОШИБКА ИГРЫ БЛЕКДЖЕК</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Игра была отменена: {reason}\n\n"
        f"💰 <b>Возвращенные ставки:</b>\n{refund_text}"
    )
    await safe_send_message(bot, chat_id, msg_text)
