"""Обработка ставок, действий игроков и смены улиц в Покере."""
import asyncio
import time
import logging
from typing import Dict, Any, List
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from utils.economy_manager import EconomyManager
from utils.game_state_manager import GameStateManager
from utils.user_link import get_user_link
from utils.poker_evaluator import (
    card_str,
    format_cards,
    evaluate_7card_hand
)
from .table import (
    get_poker_game_key,
    format_table_text,
    get_table_keyboard,
    start_turn_timer,
    cancel_poker_timer
)
from .helpers import safe_edit_message_text, safe_send_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
game_state_manager = GameStateManager()


@router.callback_query(F.data.startswith("poker_show_cards:"))
async def cb_poker_show_cards(callback: CallbackQuery):
    """Показывает приватные карманные карты игроку через alert popup."""
    chat_id = int(callback.data.split(":")[1])
    game_key = get_poker_game_key(chat_id)
    user_id = callback.from_user.id
    
    if not game_state_manager.game_exists(game_key):
        await callback.answer("❌ Игра уже завершена!", show_alert=True)
        return
        
    game_state = game_state_manager.get_game(game_key)
    players = game_state.get("players", [])
    
    player = next((p for p in players if p["user_id"] == user_id), None)
    if not player:
        await callback.answer("🚫 Вы не участвуете в этой раздаче.", show_alert=True)
        return
        
    if player.get("folded"):
        await callback.answer("❌ Вы сбросили карты в этой раздаче (Пас).", show_alert=True)
        return
        
    hole = player.get("hole_cards", [])
    community = game_state.get("community_cards", [])
    all_available = hole + community
    
    eval_res = evaluate_7card_hand(all_available)
    cards_display = f"[{hole[0]['rank']}{hole[0]['suit']}]  [{hole[1]['rank']}{hole[1]['suit']}]"
    
    popup_text = (
        f"🃏 ВАШИ КАРМАННЫЕ КАРТЫ:\n"
        f"{cards_display}\n\n"
        f"📊 Комбинация: {eval_res['description']}\n"
        f"💰 Ваш стек: {player['stack']} монет\n"
        f"🪙 Вложено в банк: {player['total_bet']} монет"
    )
    await callback.answer(popup_text, show_alert=True)


@router.callback_query(F.data.startswith("poker_act:"))
async def cb_poker_action(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    action = parts[1]
    
    if action == "raise":
        raise_amount = int(parts[2])
        chat_id = int(parts[3])
        target_uid = int(parts[4])
    else:
        chat_id = int(parts[2])
        target_uid = int(parts[3])
        raise_amount = 0
        
    user_id = callback.from_user.id
    game_key = get_poker_game_key(chat_id)
    
    if not game_state_manager.game_exists(game_key):
        await callback.answer("❌ Раздача уже завершена.", show_alert=True)
        return
        
    game_state = game_state_manager.get_game(game_key)
    current_actor_idx = game_state.get("current_actor_idx", 0)
    players = game_state.get("players", [])
    
    if current_actor_idx >= len(players):
        await callback.answer("Ошибка состояния игры.", show_alert=True)
        return
        
    current_player = players[current_actor_idx]
    if user_id != current_player["user_id"]:
        await callback.answer("⏳ Сейчас не ваш ход! Дождитесь своей очереди.", show_alert=True)
        return
        
    cancel_poker_timer(game_key)
    await process_player_turn(bot, chat_id, action, raise_amount)
    await callback.answer()


async def process_player_turn(bot: Bot, chat_id: int, action: str, raise_amount: int = 0):
    game_key = get_poker_game_key(chat_id)
    game_state = game_state_manager.get_game(game_key)
    if not game_state:
        return
        
    players = game_state["players"]
    actor_idx = game_state["current_actor_idx"]
    player = players[actor_idx]
    uid = player["user_id"]
    current_bet = game_state["current_bet"]
    pot = game_state["pot"]
    
    acted_list = game_state.get("acted_this_round", [])
    if uid not in acted_list:
        acted_list.append(uid)
    game_state["acted_this_round"] = acted_list
    
    action_text = ""
    
    if action == "check":
        action_text = f"✅ {player['first_name']} сыграл <b>Чек</b>."
        
    elif action == "call":
        to_call = current_bet - player["round_bet"]
        actual_call = min(to_call, player["stack"])
        if actual_call > 0:
            economy_manager.remove_money(uid, actual_call)
            player["stack"] -= actual_call
            player["round_bet"] += actual_call
            player["total_bet"] += actual_call
            game_state["pot"] += actual_call
            game_state["bets"][str(uid)] = player["total_bet"]
            
        if player["stack"] == 0:
            player["all_in"] = True
            action_text = f"🪙 {player['first_name']} уравнял ставку и пошел <b>ALL-IN</b> ({player['total_bet']})!"
        else:
            action_text = f"🪙 {player['first_name']} сделал <b>Колл</b> ({actual_call} монет)."
            
    elif action in ["raise", "allin"]:
        target_round_bet = raise_amount if action == "raise" else (player["stack"] + player["round_bet"])
        additional = target_round_bet - player["round_bet"]
        actual_add = min(additional, player["stack"])
        
        economy_manager.remove_money(uid, actual_add)
        player["stack"] -= actual_add
        player["round_bet"] += actual_add
        player["total_bet"] += actual_add
        game_state["pot"] += actual_add
        game_state["bets"][str(uid)] = player["total_bet"]
        
        if player["round_bet"] > current_bet:
            game_state["current_bet"] = player["round_bet"]
            game_state["last_raiser_idx"] = actor_idx
            
        if player["stack"] == 0:
            player["all_in"] = True
            action_text = f"🚀 {player['first_name']} пошел <b>ALL-IN</b> ({player['round_bet']} монет)!"
        else:
            action_text = f"🔼 {player['first_name']} повысил до <b>{player['round_bet']}</b> монет!"
            
    elif action == "fold":
        player["folded"] = True
        action_text = f"❌ {player['first_name']} сбросил карты (<b>Пас</b>)."
        
    # Сохраняем промежуточное состояние
    game_state_manager.update_game(game_key, game_state)
    
    # 1. Проверяем, сколько активных игроков осталось
    active_players = [p for p in players if not p.get("folded")]
    if len(active_players) == 1:
        # Все остальные сбросили карты! Досрочная победа без шоудауна
        from .showdown import finish_hand_single_winner
        await finish_hand_single_winner(bot, chat_id, active_players[0])
        return

    # 2. Проверяем завершение текущей улицы торговли
    if is_street_complete(game_state):
        await advance_street(bot, chat_id)
    else:
        # Передаем ход следующему активному игроку
        next_idx = find_next_actor(game_state, actor_idx)
        game_state["current_actor_idx"] = next_idx
        game_state_manager.update_game(game_key, game_state)
        
        # Обновляем сообщение стола
        text = format_table_text(game_state)
        kb = get_table_keyboard(game_state)
        await safe_edit_message_text(bot, chat_id, game_state["message_id"], text=text, reply_markup=kb)
        
        # Запускаем таймер следующего хода
        start_turn_timer(bot, chat_id)


def is_street_complete(game_state: Dict[str, Any]) -> bool:
    """Улица завершена, когда все активные игроки выровняли ставки и сделали ход."""
    players = game_state["players"]
    current_bet = game_state["current_bet"]
    acted_set = set(game_state.get("acted_this_round", []))
    
    # Игроки, которые всё еще могут делать ставки (не фолднули и не all-in)
    bettable_players = [p for p in players if not p.get("folded") and not p.get("all_in")]
    
    # Если остался 0 или 1 игрок с фишками (остальные All-In или Fold)
    if len(bettable_players) <= 1:
        # Проверяем, уравнял ли ставку последний игрок
        for p in bettable_players:
            if p["user_id"] not in acted_set or p["round_bet"] < current_bet:
                return False
        return True
        
    for p in bettable_players:
        if p["user_id"] not in acted_set:
            return False
        if p["round_bet"] != current_bet:
            return False
            
    return True


def find_next_actor(game_state: Dict[str, Any], start_from_idx: int) -> int:
    players = game_state["players"]
    n = len(players)
    for i in range(1, n + 1):
        idx = (start_from_idx + i) % n
        p = players[idx]
        if not p.get("folded") and not p.get("all_in"):
            return idx
    return start_from_idx


async def advance_street(bot: Bot, chat_id: int):
    """Переход к следующей улице (Флоп -> Терн -> Ривер -> Шоудаун)."""
    game_key = get_poker_game_key(chat_id)
    game_state = game_state_manager.get_game(game_key)
    if not game_state:
        return
        
    street = game_state["street"]
    deck = game_state["deck"]
    comm = game_state["community_cards"]
    players = game_state["players"]
    
    # Сбрасываем ставки раунда
    for p in players:
        p["round_bet"] = 0
    game_state["current_bet"] = 0
    game_state["acted_this_round"] = []
    
    # Проверяем, сколько игроков имеют стек > 0
    bettable_count = sum(1 for p in players if not p.get("folded") and not p.get("all_in"))
    
    if street == "preflop":
        # Сжигаем карту, выкладываем Флоп (3 карты)
        if deck: deck.pop()
        for _ in range(3):
            if deck: comm.append(deck.pop())
        game_state["street"] = "flop"
        
    elif street == "flop":
        # Сжигаем карту, выкладываем Терн (1 карту)
        if deck: deck.pop()
        if deck: comm.append(deck.pop())
        game_state["street"] = "turn"
        
    elif street == "turn":
        # Сжигаем карту, выкладываем Ривер (1 карту)
        if deck: deck.pop()
        if deck: comm.append(deck.pop())
        game_state["street"] = "river"
        
    elif street == "river":
        # Конец торгов, переход к Шоудауну
        game_state["street"] = "showdown"
        game_state_manager.update_game(game_key, game_state)
        from .showdown import run_showdown
        await run_showdown(bot, chat_id)
        return

    # Если после раздачи карт на новой улице играть некому (все All-In)
    if bettable_count <= 1:
        # Автоматически открываем оставшиеся общие карты и идем на шоудаун
        while len(comm) < 5 and deck:
            deck.pop()  # burn
            comm.append(deck.pop())
        game_state["street"] = "showdown"
        game_state_manager.update_game(game_key, game_state)
        
        # Обновим стол с открытыми картами
        text = format_table_text(game_state)
        await safe_edit_message_text(bot, chat_id, game_state["message_id"], text=text)
        await asyncio.sleep(2)
        
        from .showdown import run_showdown
        await run_showdown(bot, chat_id)
        return

    # Первый ход на постфлопе: начиная с первого активного игрока с позиции SB (индекс 0)
    first_actor = 0
    for idx, p in enumerate(players):
        if not p.get("folded") and not p.get("all_in"):
            first_actor = idx
            break
            
    game_state["current_actor_idx"] = first_actor
    game_state_manager.update_game(game_key, game_state)
    
    text = format_table_text(game_state)
    kb = get_table_keyboard(game_state)
    await safe_edit_message_text(bot, chat_id, game_state["message_id"], text=text, reply_markup=kb)
    
    start_turn_timer(bot, chat_id)


async def handle_timeout_action(bot: Bot, chat_id: int):
    """Обрабатывает истечение времени хода игрока."""
    game_key = get_poker_game_key(chat_id)
    if not game_state_manager.game_exists(game_key):
        return
        
    game_state = game_state_manager.get_game(game_key)
    current_actor_idx = game_state.get("current_actor_idx", 0)
    players = game_state.get("players", [])
    
    if current_actor_idx >= len(players):
        return
        
    current_player = players[current_actor_idx]
    if current_player.get("folded") or current_player.get("all_in"):
        return
        
    p_bet = current_player.get("round_bet", 0)
    current_bet = game_state.get("current_bet", 0)
    
    # Если ставка уравнена - авто-чек, иначе - авто-фолд
    actor_link = get_user_link(current_player["user_id"])
    if p_bet == current_bet:
        logger.info(f"Poker timeout: auto-check for {current_player['user_id']}")
        await safe_send_message(bot, chat_id, f"⏱ Время на ход вышло! {actor_link} автоматически играет <b>Чек</b>.")
        await process_player_turn(bot, chat_id, "check")
    else:
        logger.info(f"Poker timeout: auto-fold for {current_player['user_id']}")
        await safe_send_message(bot, chat_id, f"⏱ Время на ход вышло (60с)! {actor_link} сбросил карты (<b>Пас</b>).")
        await process_player_turn(bot, chat_id, "fold")
