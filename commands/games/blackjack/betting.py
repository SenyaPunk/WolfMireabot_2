"""Стадия принятия ставок"""
import asyncio
import time
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.economy_manager import EconomyManager
from utils.game_state_manager import GameStateManager
from utils.user_link import get_user_link
from utils.user_storage import UserStorage
from .helpers import (
    safe_edit_message_text,
    safe_send_message,
    safe_delete_message,
    abort_game_and_refund
)

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
user_storage = UserStorage()

BET_AMOUNTS = [10, 25, 50, 100]
BUTTON_COOLDOWN = 0.5  
FIRST_WARNING_TIME = 30  
AUTO_BET_TIME = 60  
MIN_AUTO_BET = 10  

button_cooldowns = {}
player_timers = {}
deletion_tasks = {}


def get_user_mention(user_id: int) -> str:
    user_info = user_storage.get_user_info(user_id)
    
    if user_info:
        if user_info.get('first_name'):
            link_text = user_info['first_name']
            if user_info.get('last_name'):
                link_text += f" {user_info['last_name']}"
        else:
            link_text = f"ID: {user_id}"
    else:
        link_text = f"ID: {user_id}"
    
    return f'<a href="tg://user?id={user_id}">{link_text}</a>'


def check_button_cooldown(user_id: int) -> bool:
    current_time = time.time()
    last_press = button_cooldowns.get(user_id, 0)
    
    if current_time - last_press < BUTTON_COOLDOWN:
        return False
    
    button_cooldowns[user_id] = current_time
    return True


def create_betting_keyboard(current_bet: int, balance: int, has_bet: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    coin_row = []
    
    for amount in BET_AMOUNTS:
        can_bet = (current_bet + amount) <= balance
        emoji = '🪙' if can_bet else '❌'
        button_text = f"{emoji} {amount}"
        
        button = InlineKeyboardButton(
            text=button_text,
            callback_data=f"bj_bet:{amount}" if can_bet else "bj_bet:disabled"
        )
        coin_row.append(button)
    
    buttons.append(coin_row)
    
    if has_bet:
        control_row = [
            InlineKeyboardButton(text="🔄 Сбросить", callback_data="bj_bet:reset"),
            InlineKeyboardButton(text="✅ Принять", callback_data="bj_bet:accept")
        ]
        buttons.append(control_row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def player_timeout_handler(bot: Bot, chat_id: int, game_key: str, user_id: int, betting_message_id: int):
    try:
        await asyncio.sleep(FIRST_WARNING_TIME)
        
        game_state_manager = GameStateManager()
        game_data = game_state_manager.get_game(game_key)
        
        if not game_data or game_data.get("stage") != "betting":
            return
        
        players = game_data.get("players", [])
        current_index = game_data.get("current_player_index", 0)
        
        if current_index >= len(players):
            return
        
        current_player = players[current_index]
        
        if current_player["user_id"] != user_id:
            return
        
        user_mention = get_user_mention(user_id)
        warning_msg = await safe_send_message(
            bot,
            chat_id=chat_id,
            text=f"⚠️ {user_mention}, у вас осталось <b>30 секунд</b> чтобы сделать ставку!",
            parse_mode="HTML",
            reply_to_message_id=betting_message_id
        )
        
        if warning_msg:
            warning_message_id = warning_msg.message_id
            if "warning_messages" not in game_data:
                game_data["warning_messages"] = {}
            game_data["warning_messages"][str(user_id)] = [warning_message_id]
            game_state_manager.update_game(game_key, game_data)
        
        logger.info(f"Sent warning to user {user_id} in game {game_key}")
        
        await asyncio.sleep(FIRST_WARNING_TIME)
        
        game_data = game_state_manager.get_game(game_key)
        
        if not game_data or game_data.get("stage") != "betting":
            return
        
        players = game_data.get("players", [])
        current_index = game_data.get("current_player_index", 0)
        
        if current_index >= len(players):
            return
        
        current_player = players[current_index]
        
        if current_player["user_id"] != user_id:
            return
        
        balance = economy_manager.get_balance(user_id)
        
        if balance < MIN_AUTO_BET:
            skip_msg = await safe_send_message(
                bot,
                chat_id=chat_id,
                text=f"⏭️ {user_mention} пропущен (недостаточно средств для минимальной ставки)",
                parse_mode="HTML"
            )
            
            if skip_msg:
                if str(user_id) in game_data.get("warning_messages", {}):
                    game_data["warning_messages"][str(user_id)].append(skip_msg.message_id)
                else:
                    if "warning_messages" not in game_data:
                        game_data["warning_messages"] = {}
                    game_data["warning_messages"][str(user_id)] = [skip_msg.message_id]
            
            game_data["current_player_index"] = current_index + 1
            game_state_manager.update_game(game_key, game_data)
            
            await safe_delete_message(bot, chat_id, betting_message_id)
            
            messages_to_delete = game_data.get("warning_messages", {}).get(str(user_id), [])
            task = asyncio.create_task(delete_messages_after_delay(bot, chat_id, messages_to_delete, 20))
            if game_key not in deletion_tasks:
                deletion_tasks[game_key] = []
            deletion_tasks[game_key].append(task)
            
            if game_data["current_player_index"] >= len(players):
                cancel_player_timer(game_key)
                await finish_betting_stage(bot, chat_id, game_key, game_state_manager)
            else:
                await show_betting_message(bot, chat_id, game_key, game_state_manager, is_new_player=True)
        else:
            bets = game_data.get("bets", {})
            bets[str(user_id)] = MIN_AUTO_BET
            game_data["bets"] = bets
            game_data["current_bet"] = 0
            
            game_data["current_player_index"] = current_index + 1
            game_state_manager.update_game(game_key, game_data)
            
            auto_bet_msg = await safe_send_message(
                bot,
                chat_id=chat_id,
                text=f"⏰ {user_mention} не сделал ставку вовремя. Автоматическая ставка: <b>{MIN_AUTO_BET} монет</b>",
                parse_mode="HTML"
            )
            
            if auto_bet_msg:
                if str(user_id) in game_data.get("warning_messages", {}):
                    game_data["warning_messages"][str(user_id)].append(auto_bet_msg.message_id)
                else:
                    if "warning_messages" not in game_data:
                        game_data["warning_messages"] = {}
                    game_data["warning_messages"][str(user_id)] = [auto_bet_msg.message_id]
                game_state_manager.update_game(game_key, game_data)
            
            await safe_delete_message(bot, chat_id, betting_message_id)
            
            messages_to_delete = game_data.get("warning_messages", {}).get(str(user_id), [])
            task = asyncio.create_task(delete_messages_after_delay(bot, chat_id, messages_to_delete, 20))
            if game_key not in deletion_tasks:
                deletion_tasks[game_key] = []
            deletion_tasks[game_key].append(task)
            
            if game_data["current_player_index"] >= len(players):
                cancel_player_timer(game_key)
                await finish_betting_stage(bot, chat_id, game_key, game_state_manager)
            else:
                await show_betting_message(bot, chat_id, game_key, game_state_manager, is_new_player=True)
        
    except asyncio.CancelledError:
        logger.info(f"Timer cancelled for user {user_id} in game {game_key}")
    except Exception as e:
        logger.error(f"Error in player timeout handler: {e}", exc_info=True)


async def delete_messages_after_delay(bot: Bot, chat_id: int, message_ids: list, delay: int):
    try:
        await asyncio.sleep(delay)
        for message_id in message_ids:
            await safe_delete_message(bot, chat_id, message_id)
    except Exception as e:
        logger.error(f"Error in delete_messages_after_delay: {e}")


def cancel_player_timer(game_key: str):
    if game_key in player_timers:
        timer_task = player_timers[game_key]
        if not timer_task.done():
            timer_task.cancel()
        del player_timers[game_key]


async def start_betting_stage(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager):
    try:
        game_data = game_state_manager.get_game(game_key)
        
        if not game_data:
            logger.error(f"Game not found: {game_key}")
            return
        
        game_data["stage"] = "betting"
        game_data["current_player_index"] = 0
        game_data["bets"] = {}
        game_data["current_bet"] = 0
        
        game_state_manager.update_game(game_key, game_data)
        await show_betting_message(bot, chat_id, game_key, game_state_manager, is_new_player=True)
    except Exception as e:
        logger.error(f"Error starting betting stage for game {game_key}: {e}", exc_info=True)
        await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, f"Ошибка в стадии ставок: {e}")


async def show_betting_message(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager, is_new_player: bool = False):
    try:
        game_data = game_state_manager.get_game(game_key)
        
        if not game_data:
            return
        
        players = game_data.get("players", [])
        current_index = game_data.get("current_player_index", 0)
        current_bet = game_data.get("current_bet", 0)
        bets = game_data.get("bets", {})
        
        if current_index >= len(players):
            cancel_player_timer(game_key)
            await finish_betting_stage(bot, chat_id, game_key, game_state_manager)
            return
        
        current_player = players[current_index]
        user_id = current_player["user_id"]
        balance = economy_manager.get_balance(user_id)
        
        user_mention = get_user_mention(user_id)
        
        bets_list = []
        for idx, player in enumerate(players, 1):
            pid = player["user_id"]
            player_link = get_user_link(pid)
            
            if str(pid) in bets:
                bet_amount = bets[str(pid)]
                bets_list.append(f"{idx}. {player_link} - {bet_amount} монет ✅")
            elif idx - 1 < current_index:
                bets_list.append(f"{idx}. {player_link} - пропущен ⏭️")
            elif idx - 1 == current_index:
                bets_list.append(f"{idx}. {user_mention} - делает ставку... ⏳")
            else:
                bets_list.append(f"{idx}. {player_link} - ожидает ⏸️")
        
        bets_text = "\n".join(bets_list)
        has_bet = current_bet > 0
        keyboard = create_betting_keyboard(current_bet, balance, has_bet)
        
        text = (
            f"💰 <b>БЛЕКДЖЕК - ПРИЕМ СТАВОК</b>\n\n"
            f"🎯 <b>Ход игрока:</b> {user_mention}\n"
            f"💵 <b>Баланс:</b> {balance} монет\n"
            f"🎲 <b>Текущая ставка:</b> {current_bet} монет\n\n"
            f"📊 <b>Ставки игроков:</b>\n{bets_text}\n\n"
            f"💡 <i>Выберите сумму ставки или нажмите 'Принять' для подтверждения</i>"
        )
        
        old_betting_message_id = game_data.get("betting_message_id")
        
        if is_new_player:
            if old_betting_message_id:
                await safe_delete_message(bot, chat_id, old_betting_message_id)
            
            msg = await safe_send_message(
                bot, chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML"
            )
            if msg:
                betting_message_id = msg.message_id
                game_data["betting_message_id"] = betting_message_id
                game_state_manager.update_game(game_key, game_data)
                
                cancel_player_timer(game_key)
                timer_task = asyncio.create_task(
                    player_timeout_handler(bot, chat_id, game_key, user_id, betting_message_id)
                )
                player_timers[game_key] = timer_task
        else:
            if old_betting_message_id:
                edited = await safe_edit_message_text(
                    bot, chat_id=chat_id, message_id=old_betting_message_id, text=text, reply_markup=keyboard, parse_mode="HTML"
                )
                if not edited:
                    await safe_delete_message(bot, chat_id, old_betting_message_id)
                    msg = await safe_send_message(
                        bot, chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML"
                    )
                    if msg:
                        game_data["betting_message_id"] = msg.message_id
                        game_state_manager.update_game(game_key, game_data)
            else:
                msg = await safe_send_message(
                    bot, chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML"
                )
                if msg:
                    game_data["betting_message_id"] = msg.message_id
                    game_state_manager.update_game(game_key, game_data)
    except Exception as e:
        logger.error(f"Error showing betting message for game {game_key}: {e}", exc_info=True)


async def delete_player_warning_messages(bot: Bot, chat_id: int, game_key: str, user_id: int, game_state_manager: GameStateManager):
    game_data = game_state_manager.get_game(game_key)
    if not game_data:
        return
    
    warning_messages = game_data.get("warning_messages", {})
    user_warnings = warning_messages.get(str(user_id), [])
    
    for message_id in user_warnings:
        await safe_delete_message(bot, chat_id, message_id)
    
    if str(user_id) in warning_messages:
        del warning_messages[str(user_id)]
        game_data["warning_messages"] = warning_messages
        game_state_manager.update_game(game_key, game_data)


async def finish_betting_stage(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager):
    try:
        logger.info(f"finish_betting_stage called for game {game_key}")
        game_data = game_state_manager.get_game(game_key)
        
        if not game_data:
            logger.error(f"Game data not found for {game_key}")
            return
        
        warning_messages = game_data.get("warning_messages", {})
        for user_id_str, message_ids in warning_messages.items():
            for message_id in message_ids:
                await safe_delete_message(bot, chat_id, message_id)
        
        game_data["warning_messages"] = {}
        game_state_manager.update_game(game_key, game_data)
        
        from .dealing import start_dealing_stage
        await start_dealing_stage(bot, chat_id, game_key, game_state_manager)
    except Exception as e:
        logger.error(f"Error finishing betting stage for game {game_key}: {e}", exc_info=True)
        await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, f"Ошибка при переходе к раздаче: {e}")


@router.callback_query(F.data.startswith("bj_bet:"))
async def betting_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if not check_button_cooldown(user_id):
        try:
            await callback.answer("⏳ Подождите немного перед следующим нажатием", show_alert=False)
        except Exception:
            pass
        return
    
    action = callback.data.split(":")[1]
    
    if action == "disabled":
        try:
            await callback.answer("❌ Недостаточно средств для этой ставки", show_alert=True)
        except Exception:
            pass
        return
    
    game_state_manager = GameStateManager()
    game_key = f"blackjack_game:{chat_id}"
    game_data = game_state_manager.get_game(game_key)
    
    if not game_data or game_data.get("stage") != "betting":
        try:
            await callback.answer("⏰ Прием ставок уже завершен", show_alert=True)
        except Exception:
            pass
        return
    
    players = game_data.get("players", [])
    current_index = game_data.get("current_player_index", 0)
    
    if current_index >= len(players):
        try:
            await callback.answer("⏰ Прием ставок завершен", show_alert=True)
        except Exception:
            pass
        return
    
    current_player = players[current_index]
    
    if current_player["user_id"] != user_id:
        try:
            await callback.answer("⏸️ Сейчас не ваш ход", show_alert=True)
        except Exception:
            pass
        return
    
    current_bet = game_data.get("current_bet", 0)
    balance = economy_manager.get_balance(user_id)
    
    if action == "reset":
        game_data["current_bet"] = 0
        game_state_manager.update_game(game_key, game_data)
        try:
            await callback.answer("🔄 Ставка сброшена")
        except Exception:
            pass
        await show_betting_message(bot, chat_id, game_key, game_state_manager, is_new_player=False)
        
    elif action == "accept":
        if current_bet == 0:
            try:
                await callback.answer("❌ Сначала сделайте ставку!", show_alert=True)
            except Exception:
                pass
            return
        
        cancel_player_timer(game_key)
        await delete_player_warning_messages(bot, chat_id, game_key, user_id, game_state_manager)
        
        bets = game_data.get("bets", {})
        bets[str(user_id)] = current_bet
        game_data["bets"] = bets
        game_data["current_bet"] = 0
        game_data["current_player_index"] = current_index + 1
        
        game_state_manager.update_game(game_key, game_data)
        
        try:
            await callback.answer(f"✅ Ставка {current_bet} монет принята!")
        except Exception:
            pass
        
        await show_betting_message(bot, chat_id, game_key, game_state_manager, is_new_player=True)
        
    else:
        try:
            bet_amount = int(action)
            
            if bet_amount not in BET_AMOUNTS:
                try:
                    await callback.answer("❌ Неверная сумма ставки", show_alert=True)
                except Exception:
                    pass
                return
            
            new_bet = current_bet + bet_amount
            
            if new_bet > balance:
                try:
                    await callback.answer("❌ Недостаточно средств!", show_alert=True)
                except Exception:
                    pass
                return
            
            game_data["current_bet"] = new_bet
            game_state_manager.update_game(game_key, game_data)
            
            try:
                await callback.answer(f"💰 +{bet_amount} монет (всего: {new_bet})")
            except Exception:
                pass
            await show_betting_message(bot, chat_id, game_key, game_state_manager, is_new_player=False)
            
        except ValueError:
            try:
                await callback.answer("❌ Ошибка обработки ставки", show_alert=True)
            except Exception:
                pass
