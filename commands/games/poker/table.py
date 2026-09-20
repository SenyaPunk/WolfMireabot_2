"""Отображение стола, управление раздачей и таймерами в Покере."""
import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile, InputMediaPhoto

from utils.economy_manager import EconomyManager
from utils.user_link import get_user_link
from utils.poker_evaluator import (
    format_cards,
    evaluate_7card_hand,
    card_badge,
    card_full_name,
    SUIT_SYMBOLS
)
from .helpers import (
    create_shuffled_deck,
    safe_edit_message_text,
    safe_edit_message_caption,
    safe_edit_message_media,
    safe_send_message,
    safe_delete_message,
    abort_poker_and_refund
)

logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
game_state_manager = GameStateManager()

# Таймеры хода игроков: game_key -> asyncio.Task
poker_turn_timers: Dict[str, asyncio.Task] = {}
TURN_TIMEOUT = 60
WARNING_TIMEOUT = 35


def cancel_poker_timer(game_key: str):
    if game_key in poker_turn_timers:
        task = poker_turn_timers.pop(game_key)
        if not task.done():
            task.cancel()


def get_poker_game_key(chat_id: int) -> str:
    return f"poker_game:{chat_id}"


def render_community_cards(community_cards: List[Dict[str, str]]) -> str:
    """Отображает общие карты стола только смайликами и мастями без лишних слов."""
    cards_str = []
    for c in community_cards:
        rank = c.get('rank', '?')
        suit = c.get('suit', 'S')
        icon = SUIT_SYMBOLS.get(suit, suit)
        cards_str.append(f"[{rank}{icon}]")
    
    # Дополняем до 5 закрытыми слотами
    remaining = 5 - len(community_cards)
    for _ in range(remaining):
        cards_str.append("🂠")
        
    return "  ".join(cards_str)


def format_table_text(game_state: Dict[str, Any]) -> str:
    street_names = {
        "preflop": "Префлоп (Раздача карт)",
        "flop": "Флоп (Первые 3 карты)",
        "turn": "Терн (4-я карта)",
        "river": "Ривер (Финальная 5-я карта)",
        "showdown": "Шоудаун (Вскрытие карт)"
    }
    
    street = game_state.get("street", "preflop")
    pot = game_state.get("pot", 0)
    community = game_state.get("community_cards", [])
    current_bet = game_state.get("current_bet", 0)
    current_actor_idx = game_state.get("current_actor_idx", 0)
    players = game_state.get("players", [])
    
    comm_rendered = render_community_cards(community)
    
    players_text_list = []
    for idx, p in enumerate(players):
        uid = p["user_id"]
        link = get_user_link(uid)
        bet = p.get("round_bet", 0)
        stack = p.get("stack", 0)
        
        status = ""
        if p.get("folded"):
            status = "❌ <i>Сбросил (Пас)</i>"
        elif p.get("all_in"):
            status = f"🚀 <b>ALL-IN</b> ({bet} монет в банке)"
        elif idx == current_actor_idx:
            status = f"🟢 <b>ХОДИТ</b> (ставка: {bet})"
        else:
            status = f"⏳ Ждет (ставка: {bet})"
            
        players_text_list.append(f"{idx + 1}. {link} — Фишки: <b>{stack}</b> | {status}")
        
    players_block = "\n".join(players_text_list)
    
    current_player = players[current_actor_idx] if 0 <= current_actor_idx < len(players) else None
    actor_mention = get_user_link(current_player["user_id"]) if current_player else "—"
    
    return (
        f"🐺 <b>ТЕХАССКИЙ ХОЛДЕМ • {street_names.get(street, street).upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Общий банк (на кону):</b> <code>{pot}</code> монет\n"
        f"💵 <b>Ставка для уравнивания:</b> <code>{current_bet}</code> монет\n\n"
        f"🃏 <b>Общие карты на столе:</b>\n"
        f"<b>{comm_rendered}</b>\n\n"
        f"👥 <b>Игроки за столом:</b>\n"
        f"{players_block}\n\n"
        f"👉 <b>Сейчас ходит:</b> {actor_mention} (⏱ {TURN_TIMEOUT}с)\n"
        f"💡 <i>Нажмите «👀 Посмотреть мои карты», чтобы тайно увидеть свою руку!</i>"
    )


def get_table_keyboard(game_state: Dict[str, Any]) -> InlineKeyboardMarkup:
    chat_id = game_state["chat_id"]
    current_actor_idx = game_state.get("current_actor_idx", 0)
    players = game_state.get("players", [])
    current_bet = game_state.get("current_bet", 0)
    blind = game_state.get("blind", 20)
    
    current_player = players[current_actor_idx] if 0 <= current_actor_idx < len(players) else None
    
    buttons = []
    
    # 1. Верхняя кнопка "👀 Мои карты" - доступна всем игрокам всегда!
    buttons.append([
        InlineKeyboardButton(text="👀 Посмотреть мои карты", callback_data=f"poker_show_cards:{chat_id}")
    ])
    
    # 2. Кнопки действий для текущего игрока
    if current_player and not current_player.get("folded") and not current_player.get("all_in"):
        p_bet = current_player.get("round_bet", 0)
        p_stack = current_player.get("stack", 0)
        to_call = current_bet - p_bet
        actor_id = current_player["user_id"]
        
        action_row = []
        if to_call <= 0:
            action_row.append(
                InlineKeyboardButton(text="✅ Чек", callback_data=f"poker_act:check:{chat_id}:{actor_id}")
            )
        else:
            call_cost = min(to_call, p_stack)
            action_row.append(
                InlineKeyboardButton(text=f"🪙 Колл ({call_cost})", callback_data=f"poker_act:call:{chat_id}:{actor_id}")
            )
            
        action_row.append(
            InlineKeyboardButton(text="❌ Пас (Фолд)", callback_data=f"poker_act:fold:{chat_id}:{actor_id}")
        )
        buttons.append(action_row)
        
        # 3. Кнопки рейза и олл-ина (если есть фишки)
        if p_stack > to_call:
            raise_row = []
            min_raise = max(blind, current_bet + blind)
            raise_amount = min(min_raise, p_stack + p_bet)
            
            # Стандартный рейз
            raise_row.append(
                InlineKeyboardButton(
                    text=f"🔼 Рейз до {raise_amount}",
                    callback_data=f"poker_act:raise:{raise_amount}:{chat_id}:{actor_id}"
                )
            )
            # Рейз х2
            x2_amount = min(max(current_bet * 2, blind * 2), p_stack + p_bet)
            if x2_amount > raise_amount and x2_amount < (p_stack + p_bet):
                raise_row.append(
                    InlineKeyboardButton(
                        text=f"🔼 x2 ({x2_amount})",
                        callback_data=f"poker_act:raise:{x2_amount}:{chat_id}:{actor_id}"
                    )
                )
            # All-in
            all_in_total = p_stack + p_bet
            raise_row.append(
                InlineKeyboardButton(
                    text=f"🚀 All-In ({all_in_total})",
                    callback_data=f"poker_act:allin:{chat_id}:{actor_id}"
                )
            )
            buttons.append(raise_row)

    # Вспомогательная строка
    buttons.append([
        InlineKeyboardButton(text="📖 Правила и комбинации", callback_data="poker_show_combos_photo")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def launch_poker_hand(
    bot: Bot, 
    chat_id: int, 
    old_msg_id: int, 
    players_data: List[Dict[str, Any]], 
    blind: int
):
    """Инициализация первой раздачи за столом."""
    game_key = get_poker_game_key(chat_id)
    deck = create_shuffled_deck()
    
    # Удаляем старое сообщение набора
    await safe_delete_message(bot, chat_id, old_msg_id)
    
    # Раздаем по 2 карты каждому игроку и инициализируем стеки
    sb_amount = blind // 2
    bb_amount = blind
    
    poker_players = []
    bets_record = {}
    
    for idx, p in enumerate(players_data):
        uid = p["user_id"]
        bal = economy_manager.get_balance(uid)
        hole = [deck.pop(), deck.pop()]
        
        # Защита от дублей мастей/символов
        from utils.poker_evaluator import card_str
        hole_formatted = [
            {"rank": hole[0]["rank"], "suit": hole[0]["suit"]},
            {"rank": hole[1]["rank"], "suit": hole[1]["suit"]}
        ]
        
        poker_players.append({
            "user_id": uid,
            "username": p.get("username"),
            "first_name": p.get("first_name", f"Игрок {idx+1}"),
            "hole_cards": hole_formatted,
            "stack": bal,
            "round_bet": 0,
            "total_bet": 0,
            "folded": False,
            "all_in": False
        })
        bets_record[uid] = 0

    pot = 0
    # Назначаем малый и большой блайнды
    # Игрок 0 = SB
    sb_player = poker_players[0]
    sb_actual = min(sb_amount, sb_player["stack"])
    economy_manager.remove_money(sb_player["user_id"], sb_actual)
    sb_player["stack"] -= sb_actual
    sb_player["round_bet"] = sb_actual
    sb_player["total_bet"] = sb_actual
    bets_record[sb_player["user_id"]] = sb_actual
    pot += sb_actual
    if sb_player["stack"] == 0:
        sb_player["all_in"] = True
        
    # Игрок 1 = BB
    bb_player = poker_players[1]
    bb_actual = min(bb_amount, bb_player["stack"])
    economy_manager.remove_money(bb_player["user_id"], bb_actual)
    bb_player["stack"] -= bb_actual
    bb_player["round_bet"] = bb_actual
    bb_player["total_bet"] = bb_actual
    bets_record[bb_player["user_id"]] = bb_actual
    pot += bb_actual
    if bb_player["stack"] == 0:
        bb_player["all_in"] = True
        
    current_bet = bb_actual
    
    # Очередность первого хода на Префлопе:
    # При 2 игроках (Heads-Up) SB (игрок 0) ходит первым на префлопе!
    # При 3+ игроках первым ходит игрок после BB (индекс 2)
    if len(poker_players) == 2:
        current_actor_idx = 0
    else:
        current_actor_idx = 2 % len(poker_players)
        
    game_state = {
        "chat_id": chat_id,
        "message_id": None,
        "blind": blind,
        "pot": pot,
        "street": "preflop",
        "community_cards": [],
        "deck": deck,
        "players": poker_players,
        "current_bet": current_bet,
        "current_actor_idx": current_actor_idx,
        "last_raiser_idx": 1,  # BB был последним, кто установил текущую ставку
        "acted_this_round": [],
        "started_at": time.time(),
        "bets": bets_record
    }
    
    # Рендерим изображение стола
    buf = render_poker_table_image(game_state)
    text = format_table_text(game_state)
    kb = get_table_keyboard(game_state)
    photo_file = BufferedInputFile(buf.getvalue(), filename="poker_table.png")
    
    try:
        table_msg = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_file,
            caption=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to send table photo in {chat_id}: {e}")
        table_msg = await safe_send_message(bot, chat_id, text=text, reply_markup=kb)
        
    if not table_msg:
        logger.error(f"Failed to send table message in {chat_id}")
        await abort_poker_and_refund(bot, chat_id, game_key, game_state_manager, "Ошибка создания стола")
        return
        
    game_state["message_id"] = table_msg.message_id
    game_state_manager.create_game(game_key, game_state)
    
    # Запускаем таймер первого хода
    start_turn_timer(bot, chat_id)


async def update_table_view(bot: Bot, chat_id: int, game_state: Dict[str, Any], is_showdown: bool = False) -> bool:
    """Генерирует актуальную картинку стола и обновляет медиа в Telegram."""
    message_id = game_state.get("message_id")
    if not message_id:
        return False
        
    buf = render_poker_table_image(game_state, is_showdown=is_showdown)
    caption = format_table_text(game_state)
    kb = get_table_keyboard(game_state)
    
    media = InputMediaPhoto(
        media=BufferedInputFile(buf.getvalue(), filename="poker_table.png"),
        caption=caption,
        parse_mode="HTML"
    )
    edited = await safe_edit_message_media(bot, chat_id, message_id, media=media, reply_markup=kb)
    if not edited:
        # Резервное обновление подписи, если замена картинки заблокирована
        await safe_edit_message_caption(bot, chat_id, message_id, caption=caption, reply_markup=kb)
    return edited


def start_turn_timer(bot: Bot, chat_id: int):
    """Запускает таймер 60 секунд на ход текущего игрока с предупреждением на 35 секундах."""
    game_key = get_poker_game_key(chat_id)
    cancel_poker_timer(game_key)
    
    async def _timer_coro():
        try:
            # Ждем 35 секунд до первого предупреждения
            await asyncio.sleep(WARNING_TIMEOUT)
            
            # Отправляем предупреждение, если раздача всё еще идет
            if game_state_manager.game_exists(game_key):
                game_state = game_state_manager.get_game(game_key)
                if game_state and game_state.get("players"):
                    actor_idx = game_state.get("current_actor_idx", 0)
                    players = game_state.get("players", [])
                    if 0 <= actor_idx < len(players):
                        actor = players[actor_idx]
                        if not actor.get("folded") and not actor.get("all_in"):
                            actor_link = get_user_link(actor["user_id"])
                            rem = TURN_TIMEOUT - WARNING_TIMEOUT
                            await safe_send_message(
                                bot, 
                                chat_id, 
                                f"⏱ {actor_link}, у вас осталось <b>{rem} секунд</b> на ход в покере!"
                            )
            
            # Ждем оставшиеся 25 секунд
            await asyncio.sleep(TURN_TIMEOUT - WARNING_TIMEOUT)
            
            # Авто-действие при таймауте
            from .betting import handle_timeout_action
            await handle_timeout_action(bot, chat_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in poker turn timer for {game_key}: {e}", exc_info=True)
            
    poker_turn_timers[game_key] = asyncio.create_task(_timer_coro())
