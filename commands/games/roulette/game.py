import asyncio
import logging
import random
import time
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile

from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.cooldown_manager import CooldownManager
from utils.user_link import get_user_link
from utils.error_handler import send_error_message
from utils.slots_generator import generate_slots_gif, SYMBOLS, SYMBOL_WEIGHTS

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
slave_manager = SlaveManager()
cooldown_manager = CooldownManager()

# Хранение текущих ставок пользователей в сессии: user_id -> int
user_bets = {}
# Хранение последних ставок для повторной игры: user_id -> int
user_last_bets = {}
# Блокировка повторных нажатий во время спина: set of user_id
active_spins = set()

# Минимальная и максимальная ставки
MIN_BET = 10
# Максимальная ставка
MAX_BET = 10000

def get_roulette_keyboard(user_id: int, current_bet: int, balance: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру выбора ставок для слотов."""
    def btn_text(amount):
        if current_bet + amount <= balance:
            return f"🪙 +{amount}"
        else:
            return f"❌ +{amount}"

    buttons = [
        [
            InlineKeyboardButton(text=btn_text(10), callback_data=f"rl_bet:add:10:{user_id}"),
            InlineKeyboardButton(text=btn_text(50), callback_data=f"rl_bet:add:50:{user_id}"),
            InlineKeyboardButton(text=btn_text(100), callback_data=f"rl_bet:add:100:{user_id}"),
            InlineKeyboardButton(text=btn_text(500), callback_data=f"rl_bet:add:500:{user_id}")
        ],
        [
            InlineKeyboardButton(text="🔄 x2", callback_data=f"rl_bet:mul:2:{user_id}"),
            InlineKeyboardButton(text="💰 Max", callback_data=f"rl_bet:max:{user_id}"),
            InlineKeyboardButton(text="🧹 Сброс", callback_data=f"rl_bet:reset:{user_id}")
        ],
        [
            InlineKeyboardButton(text="▶️ Запустить", callback_data=f"rl_spin:{user_id}"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data=f"rl_close:{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_roulette_post_keyboard(user_id: int, is_blocked: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру действий после завершения игры в слоты."""
    if is_blocked:
        buttons = [
            [
                InlineKeyboardButton(text="⏱ Кулдаун 2 часа", callback_data=f"rl_cooldown_alert:{user_id}"),
                InlineKeyboardButton(text="🎮 Меню ставок", callback_data=f"rl_menu:{user_id}")
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data=f"rl_close:{user_id}")
            ]
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton(text="🔄 Сыграть еще раз", callback_data=f"rl_retry:{user_id}"),
                InlineKeyboardButton(text="🎮 Меню ставок", callback_data=f"rl_menu:{user_id}")
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data=f"rl_close:{user_id}")
            ]
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_menu_text(user_link: str, balance: int, current_bet: int, games_left: int) -> str:
    """Форматирует текст меню ставок для игрового автомата."""
    return (
        f"🎰 <b>ИГРОВОЙ АВТОМАТ «777»</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Игрок:</b> {user_link}\n"
        f"💰 <b>Ваш баланс:</b> {balance} монет\n"
        f"💵 <b>Текущая ставка:</b> {current_bet} монет\n"
        f"🍀 <b>Игр до кулдауна:</b> {games_left} из 5\n\n"
        f"💡 <i>Настройте ставку кнопками ниже и нажмите <b>▶️ Запустить</b>!</i>\n\n"
        f"🏆 <b>Таблица выплат (для триплетов):</b>\n"
        f"• 7️⃣ 7️⃣ 7️⃣ — <b>x100.0</b> (ДЖЕКПОТ!)\n"
        f"• 🐺 🐺 🐺 — <b>x50.0</b> | 💰 💰 💰 — <b>x25.0</b>\n"
        f"• 🏆 🏆 🏆 — <b>x15.0</b> | 🪙 🪙 🪙 — <b>x10.0</b>\n"
        f"• 🎲 🎲 🎲 — <b>x8.0</b>  | 🔥 🔥 🔥 — <b>x5.0</b>\n"
        f"• 🐾 🐾 🐾 — <b>x3.0</b>\n\n"
        f"✨ <i>Дуплеты приносят от <b>x1.0</b> до <b>x3.0</b>! "
        f"Любые лапки 🐾 дают <b>x0.5</b>!</i>"
    )

def calculate_slots_win(s1: int, s2: int, s3: int) -> tuple[float, str]:
    """Рассчитывает коэффициент выигрыша и текст результата."""
    # 1. Проверяем триплеты (все 3 одинаковые)
    if s1 == s2 == s3:
        emoji, name, multiplier = SYMBOLS[s1]
        if s1 == 0:  # 777
            return multiplier, "🎰 💥 <b>МЕГА ДЖЕКПОТ! ТРИ СЕМЕРКИ!</b> 💥 🎰"
        return multiplier, f"🎉 <b>ТРИПЛЕТ! Три символа {emoji} ({name})!</b> 🎉"
            
    # 2. Проверяем дуплеты (любые 2 одинаковые)
    counts = {}
    for s in (s1, s2, s3):
        counts[s] = counts.get(s, 0) + 1
        
    if 2 in counts.values():
        dup_symbol = [k for k, v in counts.items() if v == 2][0]
        emoji, name, _ = SYMBOLS[dup_symbol]
        
        # Индивидуальные коэффициенты для топ-дуплетов
        if dup_symbol == 0:    # 7️⃣
            return 3.0, "7️⃣ <b>Две Семерки! Отличный результат!</b>"
        elif dup_symbol == 1:  # 🐺
            return 2.0, "🐺 <b>Два Волка! Отличный выигрыш!</b>"
        elif dup_symbol == 2:  # 💰
            return 1.5, "💰 <b>Два Мешка денег! Хороший плюс.</b>"
        elif dup_symbol == 3:  # 🏆
            return 1.2, "🏆 <b>Два Золотых кубка! Небольшой выигрыш.</b>"
        else:
            return 1.0, f"{emoji} <b>Два одинаковых ({name})! Возврат ставки.</b>"
            
    # 3. Проверяем утешительные лапки (лапки имеют индекс 7)
    if 7 in (s1, s2, s3):
        return 0.5, "🐾 <b>Утешительные волчьи лапки! Возвращено полставки.</b>"
        
    return 0.0, "💀 <b>Нет совпадений. Попробуйте еще раз!</b>"

@router.message(Command("рулетка", "roulette", "slots"))
async def roulette_command(message: Message):
    """Инициализация игры Слоты 777."""
    if not message.from_user:
        return
    
    user = message.from_user
    user_id = user.id
    if slave_manager.unwhip_slave(user_id):
        user_link = get_user_link(user_id, user.first_name)
        try:
            await message.answer(
                f"🕊 <b>ПОРКА ЗАВЕРШЕНА!</b>\n\n"
                f"👤 {user_link} сыграл(а) в казино — порка плеткой остановлена, и монеты больше не списываются!",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    # 1. Проверяем, идет ли спин у пользователя
    if user_id in active_spins:
        try:
            await message.delete()
        except Exception:
            pass
        warning_msg = await message.answer("🌀 Барабаны уже крутятся! Дождитесь окончания спина.")
        await asyncio.sleep(3)
        try:
            await warning_msg.delete()
        except Exception:
            pass
        return
        
    # 2. Проверяем кулдаун блокировки на 2 часа (7200 сек) после 5 игр
    remaining = cooldown_manager.check_cooldown(f"slots_block:{user_id}", 7200)
    if remaining is not None:
        try:
            await message.delete()
        except Exception:
            pass
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        time_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м {seconds}с"
        
        warning_msg = await message.answer(
            f"🚫 <b>Кулдаун Слотов!</b>\n\n"
            f"Вы сыграли 5 игр подряд. Доступ к игровому автомату заблокирован.\n"
            f"⏱ Попробуйте снова через <b>{time_str}</b>.",
            parse_mode="HTML"
        )
        await asyncio.sleep(4)
        try:
            await warning_msg.delete()
        except Exception:
            pass
        return
        
    balance = int(economy_manager.get_balance(user_id))
    
    if balance < MIN_BET:
        await send_error_message(
            message, 
            f"🚫 <b>Недостаточно средств для игры!</b>\n\n"
            f"💰 Ваш баланс: {balance} монет.\n"
            f"⚠️ Минимальная ставка составляет {MIN_BET} монет.\n"
            f"💡 Вы можете заработать монеты с помощью команды /work."
        )
        return
        
    user_bets[user_id] = MIN_BET
    
    # Получаем счетчик игр
    slots_data = cooldown_manager.get_data(f"slots_data:{user_id}")
    count = slots_data.get("count", 0)
    games_left = max(0, 5 - count)
    
    user_link = get_user_link(user_id, user.first_name)
    menu_text = format_menu_text(user_link, balance, MIN_BET, games_left)
    keyboard = get_roulette_keyboard(user_id, MIN_BET, balance)
    
    await message.answer(
        text=menu_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.callback_query(F.data.startswith("rl_bet:"))
async def roulette_bet_callback(callback_query: CallbackQuery):
    """Обработка кнопок изменения размера ставки."""
    parts = callback_query.data.split(":")
    action = parts[1]
    user_id = int(parts[-1])
    
    if callback_query.from_user.id != user_id:
        await callback_query.answer("🚫 Это не ваше меню ставок!", show_alert=True)
        return
        
    if user_id in active_spins:
        await callback_query.answer("🌀 Барабаны уже крутятся!", show_alert=True)
        return
        
    balance = int(economy_manager.get_balance(user_id))
    current_bet = user_bets.get(user_id, MIN_BET)
    
    if action == "add":
        amount = int(parts[2])
        if current_bet + amount <= balance:
            current_bet += amount
        else:
            await callback_query.answer("🚫 Недостаточно средств для увеличения ставки!", show_alert=True)
            return
    elif action == "mul":
        factor = int(parts[2])
        if current_bet * factor <= balance:
            current_bet *= factor
        else:
            current_bet = balance
    elif action == "max":
        current_bet = min(balance, MAX_BET)
    elif action == "reset":
        current_bet = 0
        
    user_bets[user_id] = current_bet
    
    slots_data = cooldown_manager.get_data(f"slots_data:{user_id}")
    count = slots_data.get("count", 0)
    games_left = max(0, 5 - count)
    
    user_link = get_user_link(user_id, callback_query.from_user.first_name)
    menu_text = format_menu_text(user_link, balance, current_bet, games_left)
    keyboard = get_roulette_keyboard(user_id, current_bet, balance)
    
    try:
        await callback_query.message.edit_text(
            text=menu_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.warning(f"Ошибка редактирования меню слотов: {e}")
        
    await callback_query.answer()

@router.callback_query(F.data.startswith("rl_close:"))
async def roulette_close_callback(callback_query: CallbackQuery):
    """Закрытие меню."""
    user_id = int(callback_query.data.split(":")[-1])
    
    if callback_query.from_user.id != user_id:
        await callback_query.answer("🚫 Вы не можете закрыть чужую игру!", show_alert=True)
        return
        
    if user_id in active_spins:
        await callback_query.answer("🌀 Нельзя закрыть игру во время вращения барабанов!", show_alert=True)
        return
        
    try:
        await callback_query.message.delete()
    except Exception:
        pass
    
    user_bets.pop(user_id, None)
    await callback_query.answer()

@router.callback_query(F.data.startswith("rl_menu:"))
async def roulette_menu_callback(callback_query: CallbackQuery):
    """Возврат в меню настроек ставок из экрана результатов."""
    user_id = int(callback_query.data.split(":")[-1])
    
    if callback_query.from_user.id != user_id:
        await callback_query.answer("🚫 Это не ваша игра!", show_alert=True)
        return
        
    if user_id in active_spins:
        await callback_query.answer("🌀 Барабаны еще крутятся!", show_alert=True)
        return
        
    # Проверяем КД перед возвратом в меню ставок
    remaining = cooldown_manager.check_cooldown(f"slots_block:{user_id}", 7200)
    if remaining is not None:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        time_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м"
        await callback_query.answer(f"🚫 Кулдаун! Доступно через {time_str}", show_alert=True)
        return
        
    balance = int(economy_manager.get_balance(user_id))
    current_bet = user_last_bets.get(user_id, MIN_BET)
    
    if current_bet > balance:
        current_bet = min(balance, MIN_BET)
        
    user_bets[user_id] = current_bet
    
    slots_data = cooldown_manager.get_data(f"slots_data:{user_id}")
    count = slots_data.get("count", 0)
    games_left = max(0, 5 - count)
    
    user_link = get_user_link(user_id, callback_query.from_user.first_name)
    menu_text = format_menu_text(user_link, balance, current_bet, games_left)
    keyboard = get_roulette_keyboard(user_id, current_bet, balance)
    
    try:
        await callback_query.message.delete()
    except Exception:
        pass
        
    await callback_query.message.answer(
        text=menu_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback_query.answer()

@router.callback_query(F.data.startswith("rl_cooldown_alert:"))
async def roulette_cooldown_alert_callback(callback_query: CallbackQuery):
    """Показывает предупреждение о кулдауне в алерте."""
    user_id = int(callback_query.data.split(":")[-1])
    if callback_query.from_user.id != user_id:
        await callback_query.answer("🚫 Это не ваша игра!", show_alert=True)
        return
        
    remaining = cooldown_manager.check_cooldown(f"slots_block:{user_id}", 7200)
    if remaining is not None:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        time_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м {seconds}с"
        await callback_query.answer(
            f"🚫 КУЛДАУН СЛОТОВ!\n\n"
            f"Вы сыграли 5 игр подряд. Следующая игра будет доступна через {time_str}.",
            show_alert=True
        )
    else:
        await callback_query.answer("Кулдаун истек, вы можете играть!")

async def run_spin_game(bot: Bot, callback_query: CallbackQuery, user_id: int, bet_amount: int):
    """Запуск раунда Слотов 777."""
    active_spins.add(user_id)
    slave_manager.unwhip_slave(user_id)
    try:
        user_last_bets[user_id] = bet_amount
        
        # Списываем ставку
        economy_manager.remove_money(user_id, bet_amount)
        
        # Инкрементируем счетчик сыгранных игр
        data_key = f"slots_data:{user_id}"
        data = cooldown_manager.get_data(data_key)
        if not data or "count" not in data:
            data = {"count": 0}
            
        data["count"] += 1
        
        # Проверяем, достигнут ли лимит в 5 игр
        is_blocked = False
        if data["count"] >= 5:
            # Устанавливаем кулдаун на 2 часа
            cooldown_manager.set_cooldown(f"slots_block:{user_id}")
            data["count"] = 0
            is_blocked = True
            
        cooldown_manager.set_data(data_key, data)
        
        # Выбираем 3 случайных символа с учетом настроенных вероятностей барабанов
        s1, s2, s3 = random.choices(range(len(SYMBOLS)), weights=SYMBOL_WEIGHTS, k=3)

        # Проверка на наличие "Буста шансов в казино"
        from utils.donation_manager import DonationManager
        don_mgr = DonationManager()
        has_casino_boost = don_mgr.has_casino_boost(user_id)
        if has_casino_boost and s1 != s2 and s2 != s3 and s1 != s3:
            # С вероятностью 45% увеличиваем шанс комбинации при бусте
            if random.random() < 0.45:
                s2 = s1
        
        # Генерируем GIF асинхронно в фоновом пуле
        try:
            gif_bytes = await asyncio.to_thread(generate_slots_gif, s1, s2, s3)
        except Exception as e:
            logger.error(f"Ошибка при генерации GIF слотов: {e}", exc_info=True)
            economy_manager.add_money(user_id, bet_amount)
            # Откатываем счетчик назад в случае ошибки
            data["count"] = max(0, data["count"] - 1)
            if is_blocked:
                cooldown_manager.delete_data(f"slots_block:{user_id}")
            cooldown_manager.set_data(data_key, data)
            await callback_query.message.answer("❌ Произошла техническая ошибка при запуске автомата. Ставка возвращена.")
            return

        animation_file = BufferedInputFile(gif_bytes, filename="slots.gif")
        user_link = get_user_link(user_id, callback_query.from_user.first_name)
        
        spin_msg = await callback_query.message.answer_animation(
            animation=animation_file,
            caption=f"🌀 {user_link} дергает за рычаг «777»!\n💵 <b>Ставка:</b> {bet_amount} монет\n\n<i>Барабаны закрутились... 🍀</i>",
            parse_mode="HTML"
        )
        
        try:
            await callback_query.message.delete()
        except Exception:
            pass
            
        await asyncio.sleep(5.2)
        
        # Рассчитываем выигрыш
        multiplier, win_text = calculate_slots_win(s1, s2, s3)
        win_amount = int(bet_amount * multiplier)
        
        net_win = max(0, win_amount - bet_amount)
        master_text = ""
        
        if net_win > 0:
            slave_share, master_share, owner_id = slave_manager.process_slave_earnings(user_id, net_win, percent=0.30)
            payout_to_player = bet_amount + slave_share
            if owner_id:
                owner_link = get_user_link(owner_id)
                master_text = f"\n👑 <b>Хозяин {owner_link} забрал (30%):</b> {master_share} монет"
        else:
            payout_to_player = win_amount

        new_balance = int(economy_manager.get_balance(user_id))
        if payout_to_player > 0:
            new_balance = int(economy_manager.add_money(user_id, payout_to_player))
            
        emoji1 = SYMBOLS[s1][0]
        emoji2 = SYMBOLS[s2][0]
        emoji3 = SYMBOLS[s3][0]
        
        cooldown_warning = "\n\n⚠️ <b>Вы сыграли 5 игр! Доступ заблокирован на 2 часа.</b>" if is_blocked else ""
        
        result_caption = (
            f"🎰 <b>РЕЗУЛЬТАТ ИГРЫ «777»</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Игрок:</b> {user_link}\n"
            f"💵 <b>Ваша ставка:</b> {bet_amount} монет\n"
            f"🎯 <b>Выпавшая комбинация:</b> [ {emoji1} | {emoji2} | {emoji3} ]\n"
            f"💰 <b>Выигрыш:</b> {win_amount} монет{master_text}\n"
            f"💳 <b>Ваш баланс:</b> {new_balance} монет\n\n"
            f"{win_text}{cooldown_warning}"
        )
        
        try:
            await spin_msg.edit_caption(
                caption=result_caption,
                reply_markup=get_roulette_post_keyboard(user_id, is_blocked),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отредактировать подпись к гифке слотов: {e}")
            await spin_msg.reply(
                text=result_caption,
                reply_markup=get_roulette_post_keyboard(user_id, is_blocked),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в спин-игре: {e}", exc_info=True)
    finally:
        active_spins.discard(user_id)

@router.callback_query(F.data.startswith("rl_spin:"))
async def roulette_spin_callback(callback_query: CallbackQuery, bot: Bot):
    """Кнопка запуска."""
    user_id = int(callback_query.data.split(":")[-1])
    
    if callback_query.from_user.id != user_id:
        await callback_query.answer("🚫 Вы не можете запустить чужую игру!", show_alert=True)
        return
        
    if user_id in active_spins:
        await callback_query.answer("🌀 Барабаны уже крутятся!", show_alert=True)
        return
        
    # Проверяем КД
    remaining = cooldown_manager.check_cooldown(f"slots_block:{user_id}", 7200)
    if remaining is not None:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        time_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м"
        await callback_query.answer(f"🚫 Кулдаун! Игра заблокирована на {time_str}.", show_alert=True)
        return
        
    bet_amount = user_bets.get(user_id, MIN_BET)
    balance = int(economy_manager.get_balance(user_id))
    
    if bet_amount < MIN_BET:
        await callback_query.answer(f"⚠️ Минимальная ставка составляет {MIN_BET} монет!", show_alert=True)
        return
        
    if bet_amount > balance:
        await callback_query.answer("🚫 Ставка превышает ваш баланс!", show_alert=True)
        return
        
    await callback_query.answer("🚀 Запуск барабанов...")
    asyncio.create_task(run_spin_game(bot, callback_query, user_id, bet_amount))

@router.callback_query(F.data.startswith("rl_retry:"))
async def roulette_retry_callback(callback_query: CallbackQuery, bot: Bot):
    """Кнопка быстрого повтора спина."""
    user_id = int(callback_query.data.split(":")[-1])
    
    if callback_query.from_user.id != user_id:
        await callback_query.answer("🚫 Вы не можете запустить чужую игру!", show_alert=True)
        return
        
    if user_id in active_spins:
        await callback_query.answer("🌀 Спин уже идет!", show_alert=True)
        return
        
    # Проверяем КД
    remaining = cooldown_manager.check_cooldown(f"slots_block:{user_id}", 7200)
    if remaining is not None:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        time_str = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м"
        await callback_query.answer(f"🚫 Кулдаун! Игра заблокирована на {time_str}.", show_alert=True)
        return
        
    bet_amount = user_last_bets.get(user_id, MIN_BET)
    balance = int(economy_manager.get_balance(user_id))
    
    if bet_amount > balance:
        await callback_query.answer("🚫 Недостаточно средств для повтора ставки! Настройте ставку заново.", show_alert=True)
        user_bets[user_id] = min(balance, MIN_BET)
        user_link = get_user_link(user_id, callback_query.from_user.first_name)
        
        slots_data = cooldown_manager.get_data(f"slots_data:{user_id}")
        count = slots_data.get("count", 0)
        games_left = max(0, 5 - count)
        
        menu_text = format_menu_text(user_link, balance, user_bets[user_id], games_left)
        keyboard = get_roulette_keyboard(user_id, user_bets[user_id], balance)
        
        try:
            await callback_query.message.delete()
        except Exception:
            pass
            
        await callback_query.message.answer(
            text=menu_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return
        
    await callback_query.answer("🚀 Крутим заново...")
    asyncio.create_task(run_spin_game(bot, callback_query, user_id, bet_amount))
