"""Стадия игры - ходы игроков и дилера"""
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

BUTTON_COOLDOWN = 0.5  
FIRST_WARNING_TIME = 30
AUTO_ACTION_TIME = 60  

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


def calculate_hand_value(cards: list) -> int:
    value = 0
    aces = 0
    
    for card in cards:
        rank = card['rank']
        if rank == 'A':
            aces += 1
            value += 11
        elif rank in ['J', 'Q', 'K']:
            value += 10
        else:
            value += int(rank)
    
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    
    return value


def format_card(card: dict) -> str:
    return f"{card['rank']}{card['suit']}"


def format_hand(cards: list, hide_second: bool = False) -> str:
    if not cards:
        return ""
    
    if hide_second and len(cards) > 1:
        return f"{format_card(cards[0])} 🂠"
    else:
        return " ".join([format_card(card) for card in cards])


def create_action_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🎴 Взять карту", callback_data="bj_action:hit"),
            InlineKeyboardButton(text="✋ Остановиться", callback_data="bj_action:stand")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


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


async def player_action_timeout_handler(bot: Bot, chat_id: int, game_key: str, user_id: int, playing_message_id: int):
    try:
        await asyncio.sleep(FIRST_WARNING_TIME)
        
        game_state_manager = GameStateManager()
        game_data = game_state_manager.get_game(game_key)
        
        if not game_data or game_data.get("stage") != "playing":
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
            text=f"⚠️ {user_mention}, у вас осталось <b>30 секунд</b> чтобы сделать ход!",
            parse_mode="HTML",
            reply_to_message_id=playing_message_id
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
        
        if not game_data or game_data.get("stage") != "playing":
            return
        
        players = game_data.get("players", [])
        current_index = game_data.get("current_player_index", 0)
        
        if current_index >= len(players):
            return
        
        current_player = players[current_index]
        
        if current_player["user_id"] != user_id:
            return
        
        player_actions = game_data.get("player_actions", {})
        player_actions[str(user_id)] = "stand"
        game_data["player_actions"] = player_actions
        game_data["current_player_index"] = current_index + 1
        game_state_manager.update_game(game_key, game_data)
        
        auto_stand_msg = await safe_send_message(
            bot,
            chat_id=chat_id,
            text=f"⏰ {user_mention} не сделал ход вовремя. Автоматическая остановка.",
            parse_mode="HTML"
        )
        
        if auto_stand_msg:
            if str(user_id) in game_data.get("warning_messages", {}):
                game_data["warning_messages"][str(user_id)].append(auto_stand_msg.message_id)
            else:
                if "warning_messages" not in game_data:
                    game_data["warning_messages"] = {}
                game_data["warning_messages"][str(user_id)] = [auto_stand_msg.message_id]
            game_state_manager.update_game(game_key, game_data)
        
        logger.info(f"Auto-stand for user {user_id} in game {game_key}")
        
        messages_to_delete = game_data.get("warning_messages", {}).get(str(user_id), [])
        task = asyncio.create_task(delete_messages_after_delay(bot, chat_id, messages_to_delete, 20))
        if game_key not in deletion_tasks:
            deletion_tasks[game_key] = []
        deletion_tasks[game_key].append(task)
        
        if game_data["current_player_index"] >= len(players):
            logger.info("Last player auto-stand, starting dealer play")
            cancel_player_timer(game_key)
            await dealer_play(bot, chat_id, game_key, game_state_manager)
        else:
            await show_player_action_menu(bot, chat_id, game_key, game_state_manager, is_new_player=True)
        
    except asyncio.CancelledError:
        logger.info(f"Timer cancelled for user {user_id} in game {game_key}")
    except Exception as e:
        logger.error(f"Error in player action timeout handler: {e}", exc_info=True)


async def start_playing_stage(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager):
    logger.info(f"Starting playing stage for game {game_key}")
    
    game_data = game_state_manager.get_game(game_key)
    if not game_data:
        logger.error(f"Game not found: {game_key}")
        return
    
    try:
        game_data["stage"] = "playing"
        game_data["current_player_index"] = 0
        game_data["player_actions"] = {}
        game_data["warning_messages"] = {}
        
        game_state_manager.update_game(game_key, game_data)
        
        msg = await safe_send_message(
            bot, chat_id=chat_id, text="🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n<i>Начинаем игру...</i>", parse_mode="HTML"
        )
        if not msg:
            raise RuntimeError("Failed to send start playing message")
        
        game_data["playing_message_id"] = msg.message_id
        game_state_manager.update_game(game_key, game_data)
        
        await asyncio.sleep(1)
        await show_player_action_menu(bot, chat_id, game_key, game_state_manager, is_new_player=True)
    except Exception as e:
        logger.error(f"Error in start_playing_stage for game {game_key}: {e}", exc_info=True)
        await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, f"Ошибка начала стадии ходов: {e}")


async def show_player_action_menu(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager, is_new_player: bool = False):
    try:
        game_data = game_state_manager.get_game(game_key)
        if not game_data:
            return
        
        players = game_data.get("players", [])
        current_index = game_data.get("current_player_index", 0)
        player_hands = game_data.get("player_hands", {})
        dealer_hand = game_data.get("dealer_hand", [])
        player_actions = game_data.get("player_actions", {})
        playing_message_id = game_data.get("playing_message_id")
        
        if not playing_message_id:
            logger.error(f"No playing message ID found for game {game_key}")
            return
        
        if current_index >= len(players):
            cancel_player_timer(game_key)
            await dealer_play(bot, chat_id, game_key, game_state_manager)
            return
        
        current_player = players[current_index]
        user_id = current_player["user_id"]
        user_mention = get_user_mention(user_id)
        
        current_hand = player_hands.get(str(user_id), [])
        current_hand_value = calculate_hand_value(current_hand)
        
        if len(current_hand) == 2 and current_hand_value == 21:
            player_actions[str(user_id)] = "blackjack"
            game_data["player_actions"] = player_actions
            game_data["current_player_index"] = current_index + 1
            game_state_manager.update_game(game_key, game_data)
            
            players_text = []
            for idx, player in enumerate(players, 1):
                pid = player["user_id"]
                player_link = get_user_link(pid)
                hand = player_hands.get(str(pid), [])
                hand_value = calculate_hand_value(hand)
                hand_str = format_hand(hand)
                action = player_actions.get(str(pid), "")
                
                if action == "bust":
                    status = "💥 Перебор"
                elif action == "stand":
                    status = "✋ Остановился"
                elif action == "blackjack":
                    status = "🎰 БЛЕКДЖЕК!"
                elif idx - 1 == current_index:
                    status = "⏳ Ходит"
                elif idx - 1 < current_index:
                    status = "✅ Завершил"
                else:
                    status = "⏸️ Ожидает"
                
                players_text.append(f"{idx}. {player_link}: {hand_str} (очки: {hand_value}) {status}")
            
            players_display = "\n".join(players_text)
            dealer_str = format_hand(dealer_hand, hide_second=True)
            current_hand_str = format_hand(current_hand)
            
            blackjack_text = (
                f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
                f"🏦 <b>Дилер:</b> {dealer_str}\n\n"
                f"👥 <b>Все игроки:</b>\n{players_display}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>🎰 {user_mention} получил БЛЕКДЖЕК! {current_hand_str} (21 очко)</i>"
            )
            
            await safe_edit_message_text(bot, chat_id, playing_message_id, blackjack_text, parse_mode="HTML")
            await asyncio.sleep(2.5)
            
            if game_data["current_player_index"] >= len(players):
                await dealer_play(bot, chat_id, game_key, game_state_manager)
            else:
                await show_player_action_menu(bot, chat_id, game_key, game_state_manager, is_new_player=True)
            return
        
        players_text = []
        for idx, player in enumerate(players, 1):
            pid = player["user_id"]
            player_link = get_user_link(pid)
            hand = player_hands.get(str(pid), [])
            hand_value = calculate_hand_value(hand)
            hand_str = format_hand(hand)
            action = player_actions.get(str(pid), "")
            
            if action == "bust":
                status = "💥 Перебор"
            elif action == "stand":
                status = "✋ Остановился"
            elif action == "blackjack":
                status = "🎰 БЛЕКДЖЕК!"
            elif idx - 1 == current_index:
                status = "⏳ Ходит"
            elif idx - 1 < current_index:
                status = "✅ Завершил"
            else:
                status = "⏸️ Ожидает"
            
            players_text.append(f"{idx}. {player_link}: {hand_str} (очки: {hand_value}) {status}")
        
        players_display = "\n".join(players_text)
        dealer_str = format_hand(dealer_hand, hide_second=True)
        current_hand_str = format_hand(current_hand)
        
        if is_new_player:
            transition_text = (
                f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
                f"🏦 <b>Дилер:</b> {dealer_str}\n\n"
                f"🎯 <b>Ход игрока:</b> {user_mention}\n"
                f"🎴 <b>Ваши карты:</b> {current_hand_str}\n"
                f"📊 <b>Очки:</b> {current_hand_value}\n\n"
                f"👥 <b>Все игроки:</b>\n{players_display}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>⏳ Переход к игроку {user_mention}...</i>"
            )
            await safe_edit_message_text(bot, chat_id, playing_message_id, transition_text, parse_mode="HTML")
            await asyncio.sleep(1.8)
        
        keyboard = create_action_keyboard()
        text = (
            f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
            f"🏦 <b>Дилер:</b> {dealer_str}\n\n"
            f"🎯 <b>Ход игрока:</b> {user_mention}\n"
            f"🎴 <b>Ваши карты:</b> {current_hand_str}\n"
            f"📊 <b>Очки:</b> {current_hand_value}\n\n"
            f"👥 <b>Все игроки:</b>\n{players_display}\n\n"
            f"💡 <i>Выберите действие: взять карту или остановиться</i>"
        )
        
        await safe_edit_message_text(bot, chat_id, playing_message_id, text, reply_markup=keyboard, parse_mode="HTML")
        
        if is_new_player:
            cancel_player_timer(game_key)
            timer_task = asyncio.create_task(
                player_action_timeout_handler(bot, chat_id, game_key, user_id, playing_message_id)
            )
            player_timers[game_key] = timer_task
            
    except Exception as e:
        logger.error(f"Error showing player action menu in game {game_key}: {e}", exc_info=True)


async def handle_hit_action(bot: Bot, chat_id: int, game_key: str, user_id: int, game_state_manager: GameStateManager):
    try:
        game_data = game_state_manager.get_game(game_key)
        if not game_data:
            return
        
        playing_message_id = game_data.get("playing_message_id")
        if not playing_message_id:
            return
        
        user_mention = get_user_mention(user_id)
        players = game_data.get("players", [])
        player_hands = game_data.get("player_hands", {})
        dealer_hand = game_data.get("dealer_hand", [])
        player_actions = game_data.get("player_actions", {})
        
        players_text = []
        for idx, player in enumerate(players, 1):
            pid = player["user_id"]
            player_link = get_user_link(pid)
            hand = player_hands.get(str(pid), [])
            hand_value = calculate_hand_value(hand)
            hand_str = format_hand(hand)
            action = player_actions.get(str(pid), "")
            
            if action == "bust":
                status = "💥 Перебор"
            elif action == "stand":
                status = "✋ Остановился"
            elif action == "blackjack":  
                status = "🎰 БЛЕКДЖЕК!"
            elif pid == user_id:
                status = "⏳ Ходит"
            else:
                status = "⏸️ Ожидает"
            
            players_text.append(f"{idx}. {player_link}: {hand_str} (очки: {hand_value}) {status}")
        
        players_display = "\n".join(players_text)
        dealer_str = format_hand(dealer_hand, hide_second=True)
        current_hand = player_hands.get(str(user_id), [])
        current_hand_value = calculate_hand_value(current_hand)
        current_hand_str = format_hand(current_hand)
        
        animation_text = (
            f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
            f"🏦 <b>Дилер:</b> {dealer_str}\n\n"
            f"🎯 <b>Ход игрока:</b> {user_mention}\n"
            f"🎴 <b>Ваши карты:</b> {current_hand_str}\n"
            f"📊 <b>Очки:</b> {current_hand_value}\n\n"
            f"👥 <b>Все игроки:</b>\n{players_display}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>🎴 Достаю карту для {user_mention}...</i>"
        )
        
        await safe_edit_message_text(bot, chat_id, playing_message_id, animation_text, parse_mode="HTML")
        await asyncio.sleep(1.2)  
        
        deck = game_data.get("deck", [])
        if not deck:
            logger.error(f"Deck is empty in game {game_key}")
            await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, "Закончились карты в колоде")
            return
        
        card = deck.pop()
        player_hand = player_hands.get(str(user_id), [])
        player_hand.append(card)
        player_hands[str(user_id)] = player_hand
        
        game_data["deck"] = deck
        game_data["player_hands"] = player_hands
        
        hand_value = calculate_hand_value(player_hand)
        
        if hand_value > 21:
            player_actions[str(user_id)] = "bust"
            game_data["player_actions"] = player_actions
            game_data["current_player_index"] = game_data.get("current_player_index", 0) + 1
            game_state_manager.update_game(game_key, game_data)
            
            cancel_player_timer(game_key)
            await delete_player_warning_messages(bot, chat_id, game_key, user_id, game_state_manager)
            
            players_text = []
            for idx, player in enumerate(players, 1):
                pid = player["user_id"]
                player_link = get_user_link(pid)
                hand = player_hands.get(str(pid), [])
                hand_value_display = calculate_hand_value(hand)
                hand_str = format_hand(hand)
                action = player_actions.get(str(pid), "")
                
                if action == "bust":
                    status = "💥 Перебор"
                elif action == "stand":
                    status = "✋ Остановился"
                elif action == "blackjack":  
                    status = "🎰 БЛЕКДЖЕК!"
                else:
                    status = "✅ Завершил"
                
                players_text.append(f"{idx}. {player_link}: {hand_str} (очки: {hand_value_display}) {status}")
            
            players_display = "\n".join(players_text)
            bust_text = (
                f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
                f"🏦 <b>Дилер:</b> {dealer_str}\n\n"
                f"👥 <b>Все игроки:</b>\n{players_display}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>💥 {user_mention} перебрал! (очки: {hand_value})</i>"
            )
            
            await safe_edit_message_text(bot, chat_id, playing_message_id, bust_text, parse_mode="HTML")
            await asyncio.sleep(2.0)          
            
            if game_data["current_player_index"] >= len(players):
                await dealer_play(bot, chat_id, game_key, game_state_manager)
            else:
                await show_player_action_menu(bot, chat_id, game_key, game_state_manager, is_new_player=True)
        else:
            cancel_player_timer(game_key)
            await delete_player_warning_messages(bot, chat_id, game_key, user_id, game_state_manager)
            
            timer_task = asyncio.create_task(
                player_action_timeout_handler(bot, chat_id, game_key, user_id, playing_message_id)
            )
            player_timers[game_key] = timer_task
            
            game_state_manager.update_game(game_key, game_data)
            await show_player_action_menu(bot, chat_id, game_key, game_state_manager, is_new_player=False)
            
    except Exception as e:
        logger.error(f"Error in handle_hit_action for game {game_key}: {e}", exc_info=True)


async def handle_stand_action(bot: Bot, chat_id: int, game_key: str, user_id: int, game_state_manager: GameStateManager):
    try:
        game_data = game_state_manager.get_game(game_key)
        if not game_data:
            return
        
        player_actions = game_data.get("player_actions", {})
        player_actions[str(user_id)] = "stand"
        game_data["player_actions"] = player_actions
        game_data["current_player_index"] = game_data.get("current_player_index", 0) + 1
        game_state_manager.update_game(game_key, game_data)
        
        cancel_player_timer(game_key)
        await delete_player_warning_messages(bot, chat_id, game_key, user_id, game_state_manager)
        
        players = game_data.get("players", [])
        if game_data["current_player_index"] >= len(players):
            await dealer_play(bot, chat_id, game_key, game_state_manager)
        else:
            await show_player_action_menu(bot, chat_id, game_key, game_state_manager, is_new_player=True)
    except Exception as e:
        logger.error(f"Error in handle_stand_action for game {game_key}: {e}", exc_info=True)


async def dealer_play(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager):
    logger.info(f"Starting dealer play for game {game_key}")
    
    game_data = game_state_manager.get_game(game_key)
    if not game_data:
        return
    
    try:
        playing_message_id = game_data.get("playing_message_id")
        if not playing_message_id:
            return
        
        warning_messages = game_data.get("warning_messages", {})
        for user_id_str, message_ids in warning_messages.items():
            for message_id in message_ids:
                await safe_delete_message(bot, chat_id, message_id)
        
        game_data["warning_messages"] = {}
        game_state_manager.update_game(game_key, game_data)
        
        dealer_hand = game_data.get("dealer_hand", [])
        deck = game_data.get("deck", [])
        player_hands = game_data.get("player_hands", {})
        players = game_data.get("players", [])
        player_actions = game_data.get("player_actions", {})
        
        players_text = []
        for idx, player in enumerate(players, 1):
            pid = player["user_id"]
            player_link = get_user_link(pid)
            hand = player_hands.get(str(pid), [])
            hand_value = calculate_hand_value(hand)
            hand_str = format_hand(hand)
            action = player_actions.get(str(pid), "")
            
            if action == "bust":
                status = "💥 Перебор"
            elif action == "stand":
                status = "✋ Остановился"
            elif action == "blackjack":
                status = "🎰 БЛЕКДЖЕК!"
            else:
                status = "✅ Завершил"
            
            players_text.append(f"{idx}. {player_link}: {hand_str} (очки: {hand_value}) {status}")
        
        players_display = "\n".join(players_text)
        dealer_value = calculate_hand_value(dealer_hand)
        dealer_str = format_hand(dealer_hand)
        
        transition_text = (
            f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
            f"🏦 <b>Дилер:</b> {dealer_str} (очки: {dealer_value})\n\n"
            f"👥 <b>Игроки:</b>\n{players_display}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>🏦 Переход к дилеру...</i>"
        )
        
        await safe_edit_message_text(bot, chat_id, playing_message_id, transition_text, parse_mode="HTML")
        await asyncio.sleep(1.8)
        
        while dealer_value <= 16:
            text = (
                f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
                f"🏦 <b>Дилер:</b> {dealer_str} (очки: {dealer_value})\n\n"
                f"👥 <b>Игроки:</b>\n{players_display}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>🎴 Дилер выбирает взять карту...</i>"
            )
            await safe_edit_message_text(bot, chat_id, playing_message_id, text, parse_mode="HTML")
            await asyncio.sleep(1.5)
            
            if not deck:
                logger.error(f"Deck is empty during dealer play in game {game_key}")
                break
            
            card = deck.pop()
            dealer_hand.append(card)
            dealer_value = calculate_hand_value(dealer_hand)
            dealer_str = format_hand(dealer_hand)
            
            game_data["deck"] = deck
            game_data["dealer_hand"] = dealer_hand
            game_state_manager.update_game(game_key, game_data)
            
            text = (
                f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
                f"🏦 <b>Дилер:</b> {dealer_str} (очки: {dealer_value})\n\n"
                f"👥 <b>Игроки:</b>\n{players_display}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>🎴 Дилер взял карту {format_card(card)}</i>"
            )
            await safe_edit_message_text(bot, chat_id, playing_message_id, text, parse_mode="HTML")
            await asyncio.sleep(1.8)
        
        if dealer_value > 21:
            dealer_status = "💥 Перебор"
        else:
            dealer_status = "✋ Остановился"
        
        text = (
            f"🎰 <b>БЛЕКДЖЕК - ИГРА</b>\n\n"
            f"🏦 <b>Дилер:</b> {dealer_str} (очки: {dealer_value}) {dealer_status}\n\n"
            f"👥 <b>Игроки:</b>\n{players_display}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>📊 Подсчет результатов...</i>"
        )
        await safe_edit_message_text(bot, chat_id, playing_message_id, text, parse_mode="HTML")
        await asyncio.sleep(2.5)
        await safe_delete_message(bot, chat_id, playing_message_id)
        
        logger.info(f"Dealer play finished for game {game_key}")
        from .results import show_results
        await show_results(bot, chat_id, game_key, game_state_manager)

    except Exception as e:
        logger.error(f"Error during dealer play in game {game_key}: {e}", exc_info=True)
        await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, f"Ошибка при ходах дилера: {e}")


@router.callback_query(F.data.startswith("bj_action:"))
async def action_callback(callback: CallbackQuery, bot: Bot):
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
    game_state_manager = GameStateManager()
    game_key = f"blackjack_game:{chat_id}"
    game_data = game_state_manager.get_game(game_key)
    
    if not game_data or game_data.get("stage") != "playing":
        try:
            await callback.answer("⏰ Игра уже завершена", show_alert=True)
        except Exception:
            pass
        return
    
    players = game_data.get("players", [])
    current_index = game_data.get("current_player_index", 0)
    
    if current_index >= len(players):
        try:
            await callback.answer("⏰ Ходы игроков завершены", show_alert=True)
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
    
    if action == "hit":
        try:
            await callback.answer("🎴 Берете карту...")
        except Exception:
            pass
        await handle_hit_action(bot, chat_id, game_key, user_id, game_state_manager)
    elif action == "stand":
        try:
            await callback.answer("✋ Остановились")
        except Exception:
            pass
        await handle_stand_action(bot, chat_id, game_key, user_id, game_state_manager)
    else:
        try:
            await callback.answer("❌ Неизвестное действие", show_alert=True)
        except Exception:
            pass
