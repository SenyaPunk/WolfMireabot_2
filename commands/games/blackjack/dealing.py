"""Стадия раздачи карт"""
import asyncio
import random
import logging
from aiogram import Bot

from utils.economy_manager import EconomyManager
from utils.game_state_manager import GameStateManager
from utils.user_storage import UserStorage

logger = logging.getLogger(__name__)
economy_manager = EconomyManager()
user_storage = UserStorage()

# Карточные масти и значения
SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

CARD_BACK = '🂠'  # Закрытая карта


def get_user_mention(user_id: int) -> str:
    user_data = user_storage.get_user(user_id)
    name = user_data.get("first_name", f"ID{user_id}")
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def create_deck() -> list:
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append({'rank': rank, 'suit': suit})
    random.shuffle(deck)
    return deck


def card_value(rank: str) -> int:
    if rank in ['J', 'Q', 'K']:
        return 10
    elif rank == 'A':
        return 11  
    else:
        return int(rank)


def calculate_hand_value(cards: list) -> int:
    value = 0
    aces = 0
    
    for card in cards:
        rank = card['rank']
        if rank == 'A':
            aces += 1
            value += 11
        else:
            value += card_value(rank)
    
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
        return f"{format_card(cards[0])} {CARD_BACK}"
    else:
        return " ".join([format_card(card) for card in cards])


async def start_dealing_stage(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager):
    logger.info(f"Starting dealing stage for game {game_key}")
    
    game_data = game_state_manager.get_game(game_key)
    
    if not game_data:
        logger.error(f"Game not found: {game_key}")
        return
    
    players = game_data.get("players", [])
    bets = game_data.get("bets", {})
    
    logger.info(f"Deducting bets from player balances")
    for player in players:
        user_id = player["user_id"]
        bet_amount = bets.get(str(user_id), 0)
        if bet_amount > 0:
            economy_manager.remove_money(user_id, bet_amount)
            logger.info(f"Deducted {bet_amount} from user {user_id}")
    
    deck = create_deck()
    
    player_hands = {str(player["user_id"]): [] for player in players}
    dealer_hand = []
    
    game_data["stage"] = "dealing"
    game_data["deck"] = deck
    game_data["player_hands"] = player_hands
    game_data["dealer_hand"] = dealer_hand
    game_state_manager.update_game(game_key, game_data)
    
    dealing_msg = await bot.send_message(
        chat_id=chat_id,
        text="🎴 <b>РАЗДАЧА КАРТ</b>\n\n<i>Дилер раздает карты...</i>",
        parse_mode="HTML"
    )
    
    dealing_message_id = dealing_msg.message_id
    game_data["dealing_message_id"] = dealing_message_id
    game_state_manager.update_game(game_key, game_data)
    
    await asyncio.sleep(1.5)
    
    for player in players:
        user_id = str(player["user_id"])
        card = deck.pop()
        player_hands[user_id].append(card)
        
        game_data["deck"] = deck
        game_data["player_hands"] = player_hands
        game_state_manager.update_game(game_key, game_data)
        
        await update_dealing_message(bot, chat_id, dealing_message_id, game_data)
        await asyncio.sleep(1.2)
    
    card = deck.pop()
    dealer_hand.append(card)
    game_data["deck"] = deck
    game_data["dealer_hand"] = dealer_hand
    game_state_manager.update_game(game_key, game_data)
    
    await update_dealing_message(bot, chat_id, dealing_message_id, game_data)
    await asyncio.sleep(1.2)
    
    for player in players:
        user_id = str(player["user_id"])
        card = deck.pop()
        player_hands[user_id].append(card)
        
        game_data["deck"] = deck
        game_data["player_hands"] = player_hands
        game_state_manager.update_game(game_key, game_data)
        
        await update_dealing_message(bot, chat_id, dealing_message_id, game_data)
        await asyncio.sleep(1.2)
    
    card = deck.pop()
    dealer_hand.append(card)
    game_data["deck"] = deck
    game_data["dealer_hand"] = dealer_hand
    game_state_manager.update_game(game_key, game_data)
    
    await update_dealing_message(bot, chat_id, dealing_message_id, game_data, final=True)
    await asyncio.sleep(2)
    
    try:
        await bot.delete_message(chat_id=chat_id, message_id=dealing_message_id)
    except Exception as e:
        logger.error(f"Error deleting dealing message: {e}")
    
    logger.info(f"Dealing stage finished for game {game_key}")
    
    from .playing import start_playing_stage
    await start_playing_stage(bot, chat_id, game_key, game_state_manager)


async def update_dealing_message(bot: Bot, chat_id: int, message_id: int, game_data: dict, final: bool = False):
    players = game_data.get("players", [])
    player_hands = game_data.get("player_hands", {})
    dealer_hand = game_data.get("dealer_hand", [])
    
    players_text = []
    for player in players:
        user_id = str(player["user_id"])
        username = player.get("username", f"ID{user_id}")
        hand = player_hands.get(user_id, [])
        
        if hand:
            hand_str = format_hand(hand)
            hand_value = calculate_hand_value(hand)
            players_text.append(f"• {username}: {hand_str} (очки: {hand_value})")
        else:
            players_text.append(f"• {username}: <i>ожидает...</i>")
    
    players_display = "\n".join(players_text)
    
    if dealer_hand:
        if final:
            dealer_str = format_hand(dealer_hand, hide_second=True)
            dealer_display = f"{dealer_str}"
        else:
            # В процессе раздачи показываем все карты
            dealer_str = format_hand(dealer_hand)
            dealer_display = f"{dealer_str}"
    else:
        dealer_display = "<i>ожидает...</i>"
    
    if final:
        text = (
            f"🎰 <b>БЛЕКДЖЕК - РАЗДАЧА ЗАВЕРШЕНА</b>\n\n"
            f"🏦 <b>Дилер:</b> {dealer_display}\n\n"
            f"👥 <b>Игроки:</b>\n{players_display}"
        )
    else:
        text = (
            f"🎴 <b>РАЗДАЧА КАРТ</b>\n\n"
            f"🏦 <b>Дилер:</b> {dealer_display}\n\n"
            f"👥 <b>Игроки:</b>\n{players_display}\n\n"
            f"<i>Дилер раздает карты...</i>"
        )
    
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error updating dealing message: {e}")
