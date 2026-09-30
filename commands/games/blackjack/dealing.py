"""Стадия раздачи карт"""
import asyncio
import random
import logging
from aiogram import Bot

from utils.economy_manager import EconomyManager
from utils.game_state_manager import GameStateManager
from utils.user_storage import UserStorage
from .helpers import (
    safe_edit_message_text,
    safe_send_message,
    safe_delete_message,
    abort_game_and_refund
)

logger = logging.getLogger(__name__)
economy_manager = EconomyManager()
user_storage = UserStorage()

SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
CARD_BACK = '🂠'


def get_user_mention(user_id: int) -> str:
    user_data = user_storage.get_user_info(user_id)
    name = user_data.get("first_name", f"ID{user_id}") if user_data else f"ID{user_id}"
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


def pop_card_with_boost(deck: list, user_id: int = None) -> dict:
    card = deck.pop()
    if user_id:
        try:
            from utils.donation_manager import DonationManager
            don_mgr = DonationManager()
            if don_mgr.has_casino_boost(user_id) and card['rank'] in ['2', '3', '4'] and random.random() < 0.35:
                better_idx = next((i for i, c in enumerate(deck) if c['rank'] in ['10', 'J', 'Q', 'K', 'A']), None)
                if better_idx is not None:
                    better_card = deck.pop(better_idx)
                    deck.append(card)
                    card = better_card
        except Exception as e:
            logger.warning(f"Error applying casino boost to card dealing: {e}")
    return card


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
    
    try:
        players = game_data.get("players", [])
        bets = game_data.get("bets", {})
        
        logger.info("Deducting bets from player balances")
        for player in players:
            user_id = player["user_id"]
            bet_amount = bets.get(user_id, bets.get(str(user_id), 0))
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
        
        player_names = []
        for p in players:
            username = p.get('username') or p.get('first_name') or f"ID{p['user_id']}"
            player_names.append(f"• 👤 <b>{username}</b>: <i>ожидает карту...</i>")
        players_waiting_text = "\n".join(player_names)
        
        initial_text = (
            f"🎰 <b>БЛЕКДЖЕК — РАЗДАЧА КАРТ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"• 🏦 <b>Дилер:</b> <i>ожидает...</i>\n\n"
            f"👥 <b>Игроки:</b>\n"
            f"{players_waiting_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>Статус:</b> <i>Дилер тасует колоду... 🃏</i>"
        )
        
        dealing_msg = await safe_send_message(bot, chat_id=chat_id, text=initial_text, parse_mode="HTML")
        if not dealing_msg:
            raise RuntimeError("Failed to send initial dealing message")
        
        dealing_message_id = dealing_msg.message_id
        game_data["dealing_message_id"] = dealing_message_id
        game_state_manager.update_game(game_key, game_data)
        
        await asyncio.sleep(1.8)
        num_players = len(players)
        
        if num_players <= 2:
            logger.info("Using sequential (card-by-card) dealing mode")
            
            # КРУГ 1
            for player in players:
                user_id = str(player["user_id"])
                await update_dealing_message(
                    bot, chat_id, dealing_message_id, game_data,
                    status_text="<i>Сдача первой карты игрокам...</i>",
                    current_recipient=user_id
                )
                await asyncio.sleep(1.8)
                
                card = pop_card_with_boost(deck, int(user_id))
                player_hands[user_id].append(card)
                game_data["deck"] = deck
                game_data["player_hands"] = player_hands
                game_state_manager.update_game(game_key, game_data)
                
            await update_dealing_message(
                bot, chat_id, dealing_message_id, game_data,
                status_text="<i>Сдача первой карты дилеру...</i>",
                current_recipient="dealer"
            )
            await asyncio.sleep(1.8)
            
            card = deck.pop()
            dealer_hand.append(card)
            game_data["deck"] = deck
            game_data["dealer_hand"] = dealer_hand
            game_state_manager.update_game(game_key, game_data)
            
            # КРУГ 2
            for player in players:
                user_id = str(player["user_id"])
                await update_dealing_message(
                    bot, chat_id, dealing_message_id, game_data,
                    status_text="<i>Сдача второй карты игрокам...</i>",
                    current_recipient=user_id
                )
                await asyncio.sleep(1.8)
                
                card = pop_card_with_boost(deck, int(user_id))
                player_hands[user_id].append(card)
                game_data["deck"] = deck
                game_data["player_hands"] = player_hands
                game_state_manager.update_game(game_key, game_data)
                
            await update_dealing_message(
                bot, chat_id, dealing_message_id, game_data,
                status_text="<i>Сдача второй карты дилеру...</i>",
                current_recipient="dealer",
                hide_dealer_second=True
            )
            await asyncio.sleep(1.8)
            
            card = deck.pop()
            dealer_hand.append(card)
            game_data["deck"] = deck
            game_data["dealer_hand"] = dealer_hand
            game_state_manager.update_game(game_key, game_data)
            
        else:
            logger.info("Using round-based dealing mode")
            for player in players:
                user_id = str(player["user_id"])
                card = pop_card_with_boost(deck, int(user_id))
                player_hands[user_id].append(card)
                
            game_data["deck"] = deck
            game_data["player_hands"] = player_hands
            game_state_manager.update_game(game_key, game_data)
            
            await update_dealing_message(
                bot, chat_id, dealing_message_id, game_data,
                status_text="<i>Сдача первой карты игрокам...</i>"
            )
            await asyncio.sleep(2.0)
            
            card = deck.pop()
            dealer_hand.append(card)
            game_data["deck"] = deck
            game_data["dealer_hand"] = dealer_hand
            game_state_manager.update_game(game_key, game_data)
            
            await update_dealing_message(
                bot, chat_id, dealing_message_id, game_data,
                status_text="<i>Сдача первой карты дилеру...</i>"
            )
            await asyncio.sleep(2.0)
            
            for player in players:
                user_id = str(player["user_id"])
                card = pop_card_with_boost(deck, int(user_id))
                player_hands[user_id].append(card)
                
            game_data["deck"] = deck
            game_data["player_hands"] = player_hands
            game_state_manager.update_game(game_key, game_data)
            
            await update_dealing_message(
                bot, chat_id, dealing_message_id, game_data,
                status_text="<i>Сдача второй карты игрокам...</i>"
            )
            await asyncio.sleep(2.0)
            
            card = deck.pop()
            dealer_hand.append(card)
            game_data["deck"] = deck
            game_data["dealer_hand"] = dealer_hand
            game_state_manager.update_game(game_key, game_data)
            
        await update_dealing_message(
            bot, chat_id, dealing_message_id, game_data,
            status_text="<i>Раздача завершена. Ожидание хода игроков...</i>",
            hide_dealer_second=True
        )
        await asyncio.sleep(2.2)
        await safe_delete_message(bot, chat_id, dealing_message_id)
        
        logger.info(f"Dealing stage finished for game {game_key}")
        from .playing import start_playing_stage
        await start_playing_stage(bot, chat_id, game_key, game_state_manager)

    except Exception as e:
        logger.error(f"Error during dealing stage in game {game_key}: {e}", exc_info=True)
        await abort_game_and_refund(bot, chat_id, game_key, game_state_manager, f"Ошибка во время раздачи карт: {e}")


async def update_dealing_message(
    bot: Bot, 
    chat_id: int, 
    message_id: int, 
    game_data: dict, 
    status_text: str, 
    current_recipient: str = None, 
    hide_dealer_second: bool = False
):
    players = game_data.get("players", [])
    player_hands = game_data.get("player_hands", {})
    dealer_hand = game_data.get("dealer_hand", [])
    
    players_text = []
    for player in players:
        user_id = str(player["user_id"])
        username = player.get("username", f"ID{user_id}")
        hand = player_hands.get(user_id, [])
        indicator = "👉 " if current_recipient == user_id else "• "
        
        if hand:
            hand_str = format_hand(hand)
            hand_value = calculate_hand_value(hand)
            bj_mark = " 👑 <b>[БЛЕКДЖЕК]</b>" if hand_value == 21 and len(hand) == 2 else ""
            players_text.append(f"{indicator}👤 <b>{username}</b>: {hand_str} (очки: <code>{hand_value}</code>){bj_mark}")
        else:
            players_text.append(f"{indicator}👤 <b>{username}</b>: <i>ожидает карту...</i>")
    
    players_display = "\n".join(players_text)
    dealer_indicator = "👉 " if current_recipient == "dealer" else "• "
    if dealer_hand:
        dealer_str = format_hand(dealer_hand, hide_second=hide_dealer_second)
        if hide_dealer_second and len(dealer_hand) > 1:
            dealer_value = calculate_hand_value([dealer_hand[0]])
        else:
            dealer_value = calculate_hand_value(dealer_hand)
        
        bj_mark = " 👑 <b>[БЛЕКДЖЕК]</b>" if dealer_value == 21 and len(dealer_hand) == 2 and not hide_dealer_second else ""
        dealer_display = f"{dealer_str} (очки: <code>{dealer_value}</code>){bj_mark}"
    else:
        dealer_display = "<i>ожидает карту...</i>"
    
    text = (
        f"🎰 <b>БЛЕКДЖЕК — РАЗДАЧА КАРТ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{dealer_indicator}🏦 <b>Дилер:</b> {dealer_display}\n\n"
        f"👥 <b>Игроки:</b>\n{players_display}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ <b>Статус:</b> {status_text}"
    )
    
    await safe_edit_message_text(bot, chat_id, message_id, text, parse_mode="HTML")
