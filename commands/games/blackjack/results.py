"""Стадия подсчета результатов"""
import asyncio
import logging
from aiogram import Bot

from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.game_state_manager import GameStateManager
from utils.user_link import get_user_link
from .helpers import safe_send_message, safe_delete_message

logger = logging.getLogger(__name__)
economy_manager = EconomyManager()
slave_manager = SlaveManager()


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


def format_hand(cards: list) -> str:
    if not cards:
        return ""
    return " ".join([format_card(card) for card in cards])


def is_blackjack(cards: list) -> bool:
    if len(cards) != 2:
        return False
    return calculate_hand_value(cards) == 21


async def show_results(bot: Bot, chat_id: int, game_key: str, game_state_manager: GameStateManager):
    logger.info(f"Starting results calculation for game {game_key}")
    
    game_data = game_state_manager.get_game(game_key)
    if not game_data:
        logger.error(f"Game not found: {game_key}")
        return
    
    try:
        players = game_data.get("players", [])
        player_hands = game_data.get("player_hands", {})
        dealer_hand = game_data.get("dealer_hand", [])
        player_actions = game_data.get("player_actions", {})
        bets = game_data.get("bets", {})
        
        dealer_value = calculate_hand_value(dealer_hand)
        dealer_bust = dealer_value > 21
        dealer_blackjack = is_blackjack(dealer_hand)
        dealer_str = format_hand(dealer_hand)
        
        results = []
        
        for player in players:
            user_id = player["user_id"]
            user_id_str = str(user_id)
            player_link = get_user_link(user_id)
            
            hand = player_hands.get(user_id_str, [])
            hand_value = calculate_hand_value(hand)
            hand_str = format_hand(hand)
            bet_amount = bets.get(user_id, bets.get(user_id_str, 0))
            
            if bet_amount == 0:
                continue
            
            action = player_actions.get(user_id_str, "")
            
            if action == "bust":
                result_text = "💥 Перебор"
                payout = 0
                win_amount = 0
            elif is_blackjack(hand):
                if dealer_blackjack:
                    result_text = "🤝 Ничья (оба блекджек)"
                    payout = bet_amount  
                    win_amount = 0
                else:
                    result_text = "🎰 БЛЕКДЖЕК!"
                    payout = int(bet_amount * 2.5)
                    win_amount = payout - bet_amount
            elif dealer_bust:
                result_text = "✅ Победа"
                payout = bet_amount * 2
                win_amount = bet_amount
            else:
                if hand_value > dealer_value:
                    result_text = "✅ Победа"
                    payout = bet_amount * 2
                    win_amount = bet_amount
                elif hand_value == dealer_value:
                    result_text = "🤝 Ничья"
                    payout = bet_amount  
                    win_amount = 0
                else:
                    result_text = "❌ Проигрыш"
                    payout = 0
                    win_amount = 0
            
            master_text = ""
            if win_amount > 0:
                slave_share, master_share, owner_id = slave_manager.process_slave_earnings(user_id, win_amount, percent=0.30)
                actual_payout = bet_amount + slave_share
                if owner_id:
                    owner_link = get_user_link(owner_id)
                    master_text = f" (👑 {owner_link} забрал {master_share})"
            else:
                actual_payout = payout
            
            if actual_payout > 0:
                economy_manager.add_money(user_id, actual_payout)
                logger.info(f"Paid {actual_payout} to user {user_id} (bet: {bet_amount}, win: {win_amount})")
            
            if win_amount > 0:
                effective_win = slave_share if owner_id else win_amount
                result_line = f"• {player_link}: {hand_str} ({hand_value}) - {result_text} 💰 +{effective_win}{master_text}"
            elif win_amount == 0 and payout > 0:
                result_line = f"• {player_link}: {hand_str} ({hand_value}) - {result_text} 🔄 Возврат {bet_amount}"
            else:
                result_line = f"• {player_link}: {hand_str} ({hand_value}) - {result_text} 💸 -{bet_amount}"
            
            results.append(result_line)
        
        results_text = "\n".join(results)
        
        if dealer_bust:
            dealer_status = f"{dealer_str} ({dealer_value}) 💥 Перебор"
        elif dealer_blackjack:
            dealer_status = f"{dealer_str} ({dealer_value}) 🎰 Блекджек"
        else:
            dealer_status = f"{dealer_str} ({dealer_value})"
        
        final_text = (
            f"🏁 <b>БЛЕКДЖЕК - РЕЗУЛЬТАТЫ</b>\n\n"
            f"🏦 <b>Дилер:</b> {dealer_status}\n\n"
            f"📊 <b>Результаты игроков:</b>\n{results_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Игра завершена! Спасибо за участие!</i>"
        )
        
        await safe_send_message(bot, chat_id=chat_id, text=final_text, parse_mode="HTML")
        logger.info(f"Results message sent for game {game_key}")
    except Exception as e:
        logger.error(f"Error in show_results for game {game_key}: {e}", exc_info=True)
    finally:
        try:
            if game_state_manager.game_exists(game_key):
                game_state_manager.delete_game(game_key)
                logger.info(f"Confirmed: Game {game_key} deleted in results cleanup")
        except Exception as e:
            logger.error(f"Error deleting game {game_key} in finally: {e}", exc_info=True)
