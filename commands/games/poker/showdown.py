"""Шоудаун (вскрытие карт), распределение банка и завершение игры в Покер."""
import asyncio
import logging
from typing import Dict, Any, List
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile, InputMediaPhoto

from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.game_state_manager import GameStateManager
from utils.user_link import get_user_link
from utils.poker_evaluator import (
    format_cards,
    evaluate_7card_hand,
    compare_hands,
    card_badge,
    card_full_name
)
from utils.poker_table_renderer import render_poker_table_image
from .table import get_poker_game_key, cancel_poker_timer, render_community_cards
from .helpers import safe_send_message, safe_delete_message, safe_edit_message_text, safe_edit_message_media

logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
slave_manager = SlaveManager()
game_state_manager = GameStateManager()


def get_endgame_keyboard(blind: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Сыграть еще раз", callback_data=f"poker_replay:{blind}"),
            InlineKeyboardButton(text="📖 Правила и комбинации", callback_data="poker_show_combos_photo")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def finish_hand_single_winner(bot: Bot, chat_id: int, winner_player: Dict[str, Any]):
    """Завершение раздачи, когда все остальные игроки сбросили карты (фолд)."""
    game_key = get_poker_game_key(chat_id)
    cancel_poker_timer(game_key)
    
    game_state = game_state_manager.get_game(game_key)
    if not game_state:
        return
        
    pot = game_state.get("pot", 0)
    blind = game_state.get("blind", 20)
    old_msg_id = game_state.get("message_id")
    
    winner_uid = winner_player["user_id"]
    winner_link = get_user_link(winner_uid)
    winner_bet = winner_player.get("total_bet", 0)
    net_win = max(0, pot - winner_bet)
    
    master_info = ""
    actual_payout = pot
    if net_win > 0:
        slave_share, master_share, owner_id = slave_manager.process_slave_earnings(winner_uid, net_win, percent=0.30)
        actual_payout = winner_bet + slave_share
        if owner_id:
            owner_link = get_user_link(owner_id)
            master_info = f"\n👑 <i>Рабовладелец {owner_link} забрал налог: {master_share} монет</i>"
            
    economy_manager.add_money(winner_uid, actual_payout)
    
    # Удаляем игру из базы
    game_state_manager.delete_game(game_key)
    
    text = (
        f"🏆 <b>ПОКЕР — ПОБЕДА БЕЗ ВСКРЫТИЯ КАРТ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"Все остальные игроки сбросили карты (Пас / вышло время хода)!\n\n"
        f"👑 <b>Победитель:</b> {winner_link}\n"
        f"💰 <b>Выигрыш:</b> <code>+{actual_payout}</code> монет (банк: {pot}){master_info}\n\n"
        f"💡 <i>Хотите сыграть еще? Жмите кнопку ниже!</i>"
    )
    kb = get_endgame_keyboard(blind)
    
    # Редактируем сообщение стола с обновленным фото
    edited = False
    if old_msg_id:
        try:
            buf = render_poker_table_image(game_state, is_showdown=False)
            media = InputMediaPhoto(
                media=BufferedInputFile(buf.getvalue(), filename="poker_winner.png"),
                caption=text,
                parse_mode="HTML"
            )
            edited = await safe_edit_message_media(bot, chat_id, old_msg_id, media=media, reply_markup=kb)
        except Exception as e:
            logger.error(f"Error editing winner photo: {e}")
            edited = await safe_edit_message_text(bot, chat_id, old_msg_id, text, reply_markup=kb)
            
    if not edited:
        await safe_send_message(bot, chat_id, text, reply_markup=kb)


async def run_showdown(bot: Bot, chat_id: int):
    """Шоудаун: вскрытие карт, вычисление лучшей комбинации и распределение банка."""
    game_key = get_poker_game_key(chat_id)
    cancel_poker_timer(game_key)
    
    game_state = game_state_manager.get_game(game_key)
    if not game_state:
        return
        
    pot = game_state.get("pot", 0)
    blind = game_state.get("blind", 20)
    community = game_state.get("community_cards", [])
    players = game_state.get("players", [])
    old_msg_id = game_state.get("message_id")
    
    # Оцениваем руки всех не сбросивших игроков
    active_evals = []
    for p in players:
        if not p.get("folded"):
            hole = p.get("hole_cards", [])
            evaluation = evaluate_7card_hand(hole + community)
            p["evaluation"] = evaluation
            active_evals.append(p)
            
    if not active_evals:
        game_state_manager.delete_game(game_key)
        return
        
    # Ищем победителя (или победителей при сплит-поте)
    best_player = active_evals[0]
    winners = [best_player]
    
    for p in active_evals[1:]:
        cmp = compare_hands(p["evaluation"], best_player["evaluation"])
        if cmp > 0:
            best_player = p
            winners = [p]
        elif cmp == 0:
            winners.append(p)
            
    # Распределяем банк между победителями
    share = pot // len(winners)
    winner_notices = []
    
    for w in winners:
        w_uid = w["user_id"]
        w_link = get_user_link(w_uid)
        w_bet = w.get("total_bet", 0)
        net_profit = max(0, share - w_bet)
        
        master_text = ""
        actual_share = share
        if net_profit > 0:
            slave_share, master_share, owner_id = slave_manager.process_slave_earnings(w_uid, net_profit, percent=0.30)
            actual_share = w_bet + slave_share
            if owner_id:
                owner_link = get_user_link(owner_id)
                master_text = f" (👑 {owner_link} налог: {master_share})"
                
        economy_manager.add_money(w_uid, actual_share)
        combo_desc = w["evaluation"]["description"]
        winner_notices.append(f"🥇 {w_link} — <b>{combo_desc}</b> (+{actual_share} монет){master_text}")
        
    # Формируем список вскрытия для всех игроков
    showdown_rows = []
    for p in players:
        p_link = get_user_link(p["user_id"])
        if p.get("folded"):
            showdown_rows.append(f"• {p_link}: <i>сбросил (Пас)</i>")
        else:
            hole = p.get("hole_cards", [])
            s1 = SUIT_SYMBOLS.get(hole[0]['suit'], hole[0]['suit'])
            s2 = SUIT_SYMBOLS.get(hole[1]['suit'], hole[1]['suit'])
            c1_str = f"[{hole[0]['rank']}{s1}]"
            c2_str = f"[{hole[1]['rank']}{s2}]"
            desc = p["evaluation"]["description"]
            showdown_rows.append(f"• {p_link}: {c1_str} {c2_str} ➔ <b>{desc}</b>")
            
    showdown_text = "\n".join(showdown_rows)
    winners_block = "\n".join(winner_notices)
    comm_rendered = render_community_cards(community)
    
    game_state_manager.delete_game(game_key)
    
    text = (
        f"🏁 <b>ПОКЕР — ИТОГИ РАЗДАЧИ (ШОУДАУН)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🃏 <b>Карты стола:</b>\n"
        f"<b>{comm_rendered}</b>\n\n"
        f"🏆 <b>ПОБЕДИТЕЛЬ:</b>\n"
        f"{winners_block}\n\n"
        f"📋 <b>Вскрытие карт игроков:</b>\n"
        f"{showdown_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Раздача завершена! Спасибо за красивую игру!</i>"
    )
    kb = get_endgame_keyboard(blind)
    
    # Редактируем сообщение стола с открытыми картами игроков на картинке
    edited = False
    if old_msg_id:
        try:
            buf = render_poker_table_image(game_state, is_showdown=True)
            media = InputMediaPhoto(
                media=BufferedInputFile(buf.getvalue(), filename="poker_showdown.png"),
                caption=text,
                parse_mode="HTML"
            )
            edited = await safe_edit_message_media(bot, chat_id, old_msg_id, media=media, reply_markup=kb)
        except Exception as e:
            logger.error(f"Error editing showdown photo: {e}")
            edited = await safe_edit_message_text(bot, chat_id, old_msg_id, text, reply_markup=kb)
            
    if not edited:
        await safe_send_message(bot, chat_id, text, reply_markup=kb)
