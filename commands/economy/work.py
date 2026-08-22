"""Команда /work"""
import time
import random
import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.cooldown_manager import CooldownManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
slave_manager = SlaveManager()
cooldown_manager = CooldownManager()
user_storage = UserStorage()

WORK_COOLDOWN = 14400  
WORK_TIME_LIMIT = 30   
REQUIRED_CLICKS = 4   
PAYMENT_DELAY = 300  

REACTION_TIMEOUT = 30  
REACTION_MIN_WAIT = 3  
REACTION_MAX_WAIT = 10  

MEMORY_SHOW_TIME = 5  
MEMORY_TIMEOUT = 40
MEMORY_SEQUENCE_LENGTH = 5

MEMORY_EMOJIS = ["🍎", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🫐", "🍒", "🍑", "🥝", "🍍"]

def get_work_cooldown_key(user_id: int, chat_id: int) -> str:
    return f"work_cooldown:{user_id}:{chat_id}"


def get_work_session_key(user_id: int, chat_id: int) -> str:
    return f"work_session:{user_id}:{chat_id}"


def format_time_remaining(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}ч {minutes}м {secs}с"
    elif minutes > 0:
        return f"{minutes}м {secs}с"
    else:
        return f"{secs}с"


def create_work_keyboard(user_id: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        text="🔨 Работать",
        callback_data=f"work_click:{user_id}"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]]) 


def get_random_work_type() -> str:
    return random.choice(['reaction', 'clicks', 'memory']) 

def calculate_reaction_reward(reaction_time: float) -> int:
    if reaction_time <= 0.5:
        return random.randint(80, 100)
    elif reaction_time <= 0.8:
        return random.randint(60, 80)
    elif reaction_time <= 1.2:
        return random.randint(40, 60)
    elif reaction_time <= 2.0:
        return random.randint(25, 45)
    elif reaction_time <= 3.0:
        return random.randint(15, 30)
    else:
        return random.randint(5, 15)

def calculate_reward(completion_time: float) -> int:
    if completion_time <= 4:
        return random.randint(60, 80)
    elif completion_time <= 7:
        return random.randint(30, 60)
    elif completion_time <= 10:
        return random.randint(20, 40)
    elif completion_time <= 15:
        return random.randint(10, 30)
    elif completion_time <= 20:
        return random.randint(5, 20)
    else:
        return random.randint(1, 10)

def calculate_memory_reward(completion_time: float) -> int:
    if completion_time <= 10:
        return random.randint(70, 90)
    elif completion_time <= 15:
        return random.randint(50, 70)
    elif completion_time <= 20:
        return random.randint(35, 55)
    elif completion_time <= 30:
        return random.randint(20, 40)
    elif completion_time <= 40:
        return random.randint(10, 25)
    else:
        return random.randint(5, 15)

async def schedule_payment(bot: Bot, user_id: int, chat_id: int, reward: int, user_name: str):
    await asyncio.sleep(PAYMENT_DELAY)
    
    try:
        from utils.slave_manager import SlaveManager
        slave_manager = SlaveManager()
        
        # Обрабатываем отчисления хозяину (30%), если пользователь находится в рабстве
        slave_share, master_share, owner_id = slave_manager.process_slave_earnings(user_id, reward, percent=0.30)
        economy_manager.add_money(user_id, slave_share)
        
        user_link = get_user_link(user_id, user_name)
        
        if owner_id and master_share > 0:
            owner_link = get_user_link(owner_id)
            await bot.send_message(
                chat_id,
                f"💰 <b>Зарплата получена!</b>\n\n"
                f"👤 {user_link}\n"
                f"💵 <b>Чистый доход:</b> {slave_share} монет\n"
                f"👑 <b>Налог хозяину {owner_link}:</b> {master_share} монет (30%)\n\n"
                f"✅ <i>Деньги зачислены на ваш счет!</i>",
                parse_mode="HTML", 
                disable_web_page_preview=True,
            )
        else:
            await bot.send_message(
                chat_id,
                f"💰 <b>Зарплата получена!</b>\n\n"
                f"👤 {user_link}\n"
                f"💵 <b>Сумма:</b> {reward} монет\n\n"
                f"✅ <i>Деньги зачислены на ваш счет!</i>",
                parse_mode="HTML", 
                disable_web_page_preview=True,
            )
        
        logger.info(f"Payment of {slave_share} (tax: {master_share}) coins delivered to user {user_id} in chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to deliver payment to user {user_id}: {e}")

@router.message(Command("work", "работать"))
async def work_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    
    user = message.from_user
    chat_id = message.chat.id
    
    # Снимаем состояние порки, если пользователь был отхлестан
    slave_manager.unwhip_slave(user.id)
    
    if message.chat.type == "private":
        await send_error_message(message, "🚫 Эта команда работает только в группах!")
        return
    
    cooldown_key = get_work_cooldown_key(user.id, chat_id)
    remaining_time = cooldown_manager.check_cooldown(cooldown_key, WORK_COOLDOWN)
    
    if remaining_time is not None:
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete user message: {e}")
        
        warning_msg = await message.answer(
            f"🚫 <b>Вы уже работали недавно!</b>\n\n"
            f"⏰ Следующая смена через {format_time_remaining(remaining_time)}\n"
            f"💡 <i>Нужно отдохнуть между сменами...</i>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        
        await asyncio.sleep(3)
        try:
            await warning_msg.delete()
        except Exception as e:
            logger.warning(f"Failed to delete warning message: {e}")
        
        return
    
    cooldown_manager.set_cooldown(cooldown_key)
    
    work_type = get_random_work_type()
    
    session_key = get_work_session_key(user.id, chat_id)
    cooldown_manager.set_data(session_key, {
        "start_time": time.time(),
        "clicks": 0,
        "active": True,
        "started": False,
        "work_type": work_type
    })
    
    start_button = InlineKeyboardButton(
        text="▶️ Начать работать",
        callback_data=f"work_start:{user.id}"
    )
    start_keyboard = InlineKeyboardMarkup(inline_keyboard=[[start_button]])
    
    user_name = user.first_name or "Пользователь"
    
    if work_type == 'clicks':
        work_msg = await message.reply(
            f"🏭 <b>Рабочая смена доступна!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"🎯 <b>Задача:</b> Нажать кнопку ровно {REQUIRED_CLICKS} раз\n"
            f"⏰ <b>Время:</b> {WORK_TIME_LIMIT} секунд\n"
            f"💰 <b>Награда:</b> зависит от скорости выполнения\n"
            f"⚡ <b>Быстрее = больше монет!</b>\n"
            f"💵 <b>Выплата:</b> через 5 минут после завершения\n\n"
            f"👇 <b>Нажмите кнопку, чтобы начать!</b>",
            reply_markup=start_keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    elif work_type == 'reaction':
        work_msg = await message.reply(
            f"🎯 <b>Тест на реакцию!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"🎯 <b>Задача:</b> Нажать кнопку, когда загорится зеленый свет\n"
            f"🔴 <b>Правила:</b>\n"
            f"  • Сначала будет гореть красный свет\n"
            f"  • Дождитесь зеленого света\n"
            f"  • Нажмите кнопку как можно быстрее!\n"
            f"⚠️ <b>Внимание:</b> Если нажмете на красный - проиграете!\n"
            f"💰 <b>Награда:</b> зависит от скорости реакции\n"
            f"⚡ <b>Быстрее = больше монет!</b>\n"
            f"💵 <b>Выплата:</b> через 5 минут после завершения\n\n"
            f"👇 <b>Нажмите кнопку, чтобы начать!</b>",
            reply_markup=start_keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    else:
        work_msg = await message.reply(
            f"🧠 <b>Тест на память!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"🎯 <b>Задача:</b> Запомнить последовательность смайликов\n"
            f"📋 <b>Правила:</b>\n"
            f"  • Вам покажут {MEMORY_SEQUENCE_LENGTH} смайликов на {MEMORY_SHOW_TIME} секунд\n"
            f"  • Запомните их порядок!\n"
            f"  • Затем воссоздайте последовательность\n"
            f"  • Есть кнопка сброса, если ошиблись\n"
            f"⚠️ <b>Внимание:</b> Одна ошибка - и награды не будет!\n"
            f"💰 <b>Награда:</b> зависит от скорости выполнения\n"
            f"⚡ <b>Быстрее = больше монет!</b>\n"
            f"💵 <b>Выплата:</b> через 5 минут после завершения\n\n"
            f"👇 <b>Нажмите кнопку, чтобы начать!</b>",
            reply_markup=start_keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    
    session = cooldown_manager.get_data(session_key)
    session["message_id"] = work_msg.message_id
    cooldown_manager.set_data(session_key, session)
    
    logger.info(
        f"Work command ({work_type}) used by {user.first_name} ({user.id}) in chat {chat_id}"
    )

@router.callback_query(F.data.startswith("work_start:"))
async def work_start_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    await callback.answer()
    
    try:
        _, user_id_str = callback.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка обработки команды.")
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("🚫 Это не ваша работа!", show_alert=True)
        return
    
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_name = user.first_name or "Пользователь"
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if not session or not session.get("active", False):
        await callback.answer("⏰ Рабочая смена уже завершена!", show_alert=True)
        return
    
    if session.get("started", False):
        await callback.answer("⚠️ Работа уже начата!", show_alert=True)
        return
    
    session["started"] = True
    session["start_time"] = time.time()
    cooldown_manager.set_data(session_key, session)
    
    work_type = session.get("work_type", "clicks")
    
    if work_type == 'clicks':
        keyboard = create_work_keyboard(user_id)
        
        await callback.message.edit_text(
            f"🔥 <b>Работа началась!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"📊 <b>Прогресс:</b> 0/{REQUIRED_CLICKS}\n"
            f"⏰ <b>Время:</b> {WORK_TIME_LIMIT} секунд\n"
            f"⏱️ <b>Отсчет времени начался!</b>\n\n"
            f"🎯 <b>Нажимайте кнопку!</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        asyncio.create_task(check_work_timeout(bot, user_id, chat_id, user_name, callback.message.message_id))
    
    elif work_type == 'reaction':
        red_button = InlineKeyboardButton(
            text="🔴🔴🔴 ЖДИТЕ 🔴🔴🔴",
            callback_data=f"reaction_red:{user_id}"
        )
        red_keyboard = InlineKeyboardMarkup(inline_keyboard=[[red_button]])
        
        await callback.message.edit_text(
            f"🔴 <b>КРАСНЫЙ СВЕТ!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"⏰ <b>Ждите зеленый свет...</b>\n\n"
            f"⚠️ <b>НЕ НАЖИМАЙТЕ СЕЙЧАС!</b>",
            reply_markup=red_keyboard,
            parse_mode="HTML"
        )
        
        wait_time = random.uniform(REACTION_MIN_WAIT, REACTION_MAX_WAIT)
        asyncio.create_task(switch_to_green_light(bot, user_id, chat_id, user_name, callback.message.message_id, wait_time))
        
        asyncio.create_task(check_reaction_timeout(bot, user_id, chat_id, user_name, callback.message.message_id))
    
    else:
        sequence = random.sample(MEMORY_EMOJIS, MEMORY_SEQUENCE_LENGTH)
        session["memory_sequence"] = sequence
        session["memory_input"] = []
        session["memory_phase"] = "memorizing"
        cooldown_manager.set_data(session_key, session)
        
        sequence_text = " ".join(sequence)
        
        # Вместо автоскрытия даем пользователю кнопку готовности, чтобы медленный интернет не съедал время просмотра
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Я запомнил(а), готов вводить!", callback_data=f"memory_ready:{user_id}")]
        ])
        
        await callback.message.edit_text(
            f"🧠 <b>ЗАПОМИНАЙТЕ!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"📋 <b>Последовательность:</b>\n"
            f"<code>{sequence_text}</code>\n\n"
            f"👀 <b>Запомните порядок смайликов и нажмите кнопку ниже, когда будете готовы!</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        asyncio.create_task(check_memory_timeout(bot, user_id, chat_id, user_name, callback.message.message_id))

@router.callback_query(F.data.startswith("memory_ready:"))
async def memory_ready_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
        
    await callback.answer()
    
    try:
        _, user_id_str = callback.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка обработки команды.")
        return
        
    if callback.from_user.id != user_id:
        await callback.answer("🚫 Это не ваша работа!", show_alert=True)
        return
        
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_name = user.first_name or "Пользователь"
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if not session or not session.get("active", False):
        await callback.answer("⏰ Рабочая смена уже завершена!", show_alert=True)
        return
        
    if session.get("memory_phase") != "memorizing":
        return
        
    session["memory_phase"] = "input"
    session["input_start_time"] = time.time()
    cooldown_manager.set_data(session_key, session)
    
    sequence = session.get("memory_sequence", [])
    shuffled_emojis = sequence.copy()
    random.shuffle(shuffled_emojis)
    session["shuffled_emojis"] = shuffled_emojis
    cooldown_manager.set_data(session_key, session)
    
    row1 = [InlineKeyboardButton(text=emoji, callback_data=f"memory_emoji:{user_id}:{emoji}") for emoji in shuffled_emojis[:3]]
    row2 = [InlineKeyboardButton(text=emoji, callback_data=f"memory_emoji:{user_id}:{emoji}") for emoji in shuffled_emojis[3:6]]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[row1, row2])
    
    try:
        await callback.message.edit_text(
            text=f"🧠 <b>ВОССОЗДАЙТЕ ПОСЛЕДОВАТЕЛЬНОСТЬ!</b>\n\n"
                 f"👤 <b>Работник:</b> {user_name}\n"
                 f"📋 <b>Ваш ввод:</b> <code>[ ]</code>\n"
                 f"📊 <b>Прогресс:</b> 0/{MEMORY_SEQUENCE_LENGTH}\n\n"
                 f"🎯 <b>Нажимайте смайлики в правильном порядке!</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to show memory input keyboard: {e}")

async def check_memory_timeout(bot: Bot, user_id: int, chat_id: int, user_name: str, message_id: int):
    await asyncio.sleep(MEMORY_TIMEOUT)
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if session and session.get("active", False):
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⏰ <b>Время вышло!</b>\n\n"
                     f"❌ {user_name} не успел(а) выполнить задание\n"
                     f"💸 <b>Награда не выплачена</b>\n\n"
                     f"💡 <i>В следующий раз будьте быстрее!</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning(f"Failed to update memory timeout message: {e}")

@router.callback_query(F.data.startswith("memory_emoji:"))
async def memory_emoji_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    await callback.answer()
    
    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        emoji = parts[2]
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка обработки команды.")
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("🚫 Это не ваша работа!", show_alert=True)
        return
    
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_name = user.first_name or "Пользователь"
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if not session or not session.get("active", False):
        await callback.answer("⏰ Рабочая смена уже завершена!", show_alert=True)
        return
    
    if session.get("memory_phase") != "input":
        await callback.answer("⚠️ Сейчас нельзя нажимать кнопки!", show_alert=True)
        return
    
    memory_input = session.get("memory_input", [])
    memory_sequence = session.get("memory_sequence", [])
    
    memory_input.append(emoji)
    session["memory_input"] = memory_input
    cooldown_manager.set_data(session_key, session)
    
    current_position = len(memory_input)
    
    if memory_input[current_position - 1] != memory_sequence[current_position - 1]:
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        
        correct_sequence = " ".join(memory_sequence)
        user_sequence = " ".join(memory_input)
        
        await callback.message.edit_text(
            f"❌ <b>Работа провалена!</b>\n\n"
            f"👤 {user_name} ошибся в последовательности!\n"
            f"📋 <b>Правильно:</b> <code>{correct_sequence}</code>\n"
            f"📋 <b>Ваш ввод:</b> <code>{user_sequence}</code>\n"
            f"💸 <b>Награда не выплачена</b>\n\n"
            f"💡 <i>В следующий раз будьте внимательнее!</i>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        
        logger.info(f"Memory game failed by {user_name} ({user_id}) in chat {chat_id}")
        return
    
    if current_position == MEMORY_SEQUENCE_LENGTH:
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        
        input_start_time = session.get("input_start_time", time.time())
        completion_time = time.time() - input_start_time
        
        reward = calculate_memory_reward(completion_time)
        
        correct_sequence = " ".join(memory_sequence)
        
        if completion_time <= 15:
            performance = "🔥 Невероятная память!"
        elif completion_time <= 25:
            performance = "⚡ Отличная работа!"
        elif completion_time <= 35:
            performance = "👍 Хорошо!"
        else:
            performance = "🐌 Можно быстрее!"
        
        await callback.message.edit_text(
            f"✅ <b>Работа выполнена!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"📋 <b>Последовательность:</b> <code>{correct_sequence}</code>\n"
            f"⏱️ <b>Время выполнения:</b> {completion_time:.1f} сек.\n"
            f"💰 <b>Награда:</b> {reward} монет\n"
            f"⏳ <b>Выплата через:</b> 5 минут\n\n"
            f"{performance}",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        
        asyncio.create_task(schedule_payment(bot, user_id, chat_id, reward, user_name))
        
        logger.info(
            f"Memory game completed by {user.first_name} ({user_id}) in chat {chat_id}, "
            f"time: {completion_time:.1f}s, reward: {reward}, payment scheduled"
        )
    else:
        shuffled_emojis = session.get("shuffled_emojis", [])
        input_text = " ".join(memory_input)
        
        row1 = [InlineKeyboardButton(text=emoji, callback_data=f"memory_emoji:{user_id}:{emoji}") for emoji in shuffled_emojis[:3]]
        row2 = [InlineKeyboardButton(text=emoji, callback_data=f"memory_emoji:{user_id}:{emoji}") for emoji in shuffled_emojis[3:6]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[row1, row2])
        
        await callback.message.edit_text(
            f"🧠 <b>ВОССОЗДАЙТЕ ПОСЛЕДОВАТЕЛЬНОСТЬ!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"📋 <b>Ваш ввод:</b> <code>{input_text}</code>\n"
            f"📊 <b>Прогресс:</b> {current_position}/{MEMORY_SEQUENCE_LENGTH}\n\n"
            f"🎯 <b>Продолжайте!</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("memory_reset:"))
async def memory_reset_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    await callback.answer("🔄 Функция сброса отключена!", show_alert=True)

async def switch_to_green_light(bot: Bot, user_id: int, chat_id: int, user_name: str, message_id: int, wait_time: float):
    await asyncio.sleep(wait_time)
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if not session or not session.get("active", False):
        return
    
    green_button = InlineKeyboardButton(
        text="🟢🟢🟢 НАЖМИ! 🟢🟢🟢",
        callback_data=f"reaction_green:{user_id}"
    )
    green_keyboard = InlineKeyboardMarkup(inline_keyboard=[[green_button]])
    
    t_before = time.time()
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🟢 <b>ЗЕЛЕНЫЙ СВЕТ!</b>\n\n"
                 f"👤 <b>Работник:</b> {user_name}\n"
                 f"⚡ <b>НАЖИМАЙТЕ БЫСТРЕЕ!</b>\n\n"
                 f"🎯 <b>Чем быстрее - тем больше награда!</b>",
            reply_markup=green_keyboard,
            parse_mode="HTML"
        )
        t_after = time.time()
        api_duration = t_after - t_before
        
        # Математический учет задержки Telegram:
        # t_after фиксирует точное время завершения редактирования на серверах Telegram.
        # Задержка клиентской сети (доставка сообщения + передача callback) оценивается как:
        # tg_latency_offset = base_rtt (0.35s) + 0.5 * api_duration
        tg_latency_offset = 0.35 + (0.5 * api_duration)
        
        session["green_light_time"] = t_after
        session["tg_latency_offset"] = tg_latency_offset
        cooldown_manager.set_data(session_key, session)
    except Exception as e:
        logger.warning(f"Failed to switch to green light: {e}")

async def check_reaction_timeout(bot: Bot, user_id: int, chat_id: int, user_name: str, message_id: int):
    await asyncio.sleep(REACTION_TIMEOUT)
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if session and session.get("active", False):
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⏰ <b>Время вышло!</b>\n\n"
                     f"❌ {user_name} не нажал(а) на кнопку вовремя\n"
                     f"💸 <b>Награда не выплачена</b>\n\n"
                     f"💡 <i>В следующий раз будьте внимательнее!</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning(f"Failed to update timeout message: {e}")

async def check_work_timeout(bot: Bot, user_id: int, chat_id: int, user_name: str, message_id: int):
    await asyncio.sleep(WORK_TIME_LIMIT)
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if session and session.get("active", False):
        clicks = session.get("clicks", 0)
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⏰ <b>Время вышло!</b>\n\n"
                     f"❌ {user_name} не успел(а) выполнить работу\n"
                     f"📊 Нажато: {clicks}/{REQUIRED_CLICKS}\n"
                     f"💸 <b>Награда не выплачена</b>\n\n"
                     f"💡 <i>В следующий раз постарайтесь быть быстрее!</i>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning(f"Failed to update timeout message: {e}")

@router.callback_query(F.data.startswith("reaction_red:"))
async def reaction_red_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    await callback.answer("🔴 Слишком рано! Дождитесь зеленого света!", show_alert=True)
    
    try:
        _, user_id_str = callback.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        return
    
    if callback.from_user.id != user_id:
        return
    
    chat_id = callback.message.chat.id
    user_name = callback.from_user.first_name or "Пользователь"
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if not session or not session.get("active", False):
        return
    
    # Mark as failed
    session["active"] = False
    cooldown_manager.set_data(session_key, session)
    
    await callback.message.edit_text(
        f"❌ <b>Работа провалена!</b>\n\n"
        f"👤 {user_name} нажал(а) слишком рано!\n"
        f"🔴 <b>Нужно было дождаться зеленого света</b>\n"
        f"💸 <b>Награда не выплачена</b>\n\n"
        f"💡 <i>В следующий раз будьте терпеливее!</i>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    
    logger.info(f"Reaction test failed (early click) by {user_name} ({user_id}) in chat {chat_id}")

@router.callback_query(F.data.startswith("reaction_green:"))
async def reaction_green_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    await callback.answer()
    
    try:
        _, user_id_str = callback.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка обработки команды.")
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("🚫 Это не ваша работа!", show_alert=True)
        return
    
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_name = user.first_name or "Пользователь"
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if not session or not session.get("active", False):
        await callback.answer("⏰ Рабочая смена уже завершена!", show_alert=True)
        return
    
    green_light_time = session.get("green_light_time")
    if not green_light_time:
        await callback.answer("⚠️ Ошибка: зеленый свет еще не загорелся!", show_alert=True)
        return
    
    current_time = time.time()
    raw_reaction_time = current_time - green_light_time
    tg_latency_offset = session.get("tg_latency_offset", 0.35)
    
    # Чистая скорость реакции пользователя после математического вычета задержки сети
    reaction_time = max(0.10, raw_reaction_time - tg_latency_offset)
    
    session["active"] = False
    cooldown_manager.set_data(session_key, session)
    
    reward = calculate_reaction_reward(reaction_time)
    
    if reaction_time <= 0.5:
        performance = "🔥 Невероятная реакция!"
    elif reaction_time <= 1.0:
        performance = "⚡ Отличная реакция!"
    elif reaction_time <= 2.0:
        performance = "👍 Хорошая реакция!"
    else:
        performance = "🐌 Можно быстрее!"
    
    await callback.message.edit_text(
        f"✅ <b>Работа выполнена!</b>\n\n"
        f"👤 <b>Работник:</b> {user_name}\n"
        f"⏱️ <b>Время реакции:</b> {reaction_time:.3f} сек. <i>(с учетом задержки TG)</i>\n"
        f"💰 <b>Награда:</b> {reward} монет\n"
        f"⏳ <b>Выплата через:</b> 5 минут\n\n"
        f"{performance}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    
    asyncio.create_task(schedule_payment(bot, user_id, chat_id, reward, user_name))
    
    logger.info(
        f"Reaction test completed by {user.first_name} ({user_id}) in chat {chat_id}, "
        f"reaction time: {reaction_time:.3f}s, reward: {reward}, payment scheduled"
    )

@router.callback_query(F.data.startswith("work_click:"))
async def work_click_callback(callback: CallbackQuery, bot: Bot):
    if not callback.data or not callback.from_user or not callback.message:
        return
    
    await callback.answer()
    
    try:
        _, user_id_str = callback.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await callback.message.edit_text("❌ Ошибка обработки команды.")
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("🚫 Это не ваша работа!", show_alert=True)
        return
    
    chat_id = callback.message.chat.id
    user = callback.from_user
    user_name = user.first_name or "Пользователь"
    
    session_key = get_work_session_key(user_id, chat_id)
    session = cooldown_manager.get_data(session_key)
    
    if not session.get("active", False):
        await callback.answer("⏰ Рабочая смена уже завершена!", show_alert=True)
        return
    
    if not session.get("started", False):
        await callback.answer("⚠️ Сначала нажмите 'Начать работать'!", show_alert=True)
        return
    
    clicks = session.get("clicks", 0) + 1
    start_time = session.get("start_time", 0)
    current_time = time.time()
    elapsed = current_time - start_time
    remaining_time = max(0, WORK_TIME_LIMIT - elapsed)
    
    session["clicks"] = clicks
    cooldown_manager.set_data(session_key, session)
    
    if remaining_time <= 0:
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        await callback.message.edit_text(
            f"⏰ <b>Время вышло!</b>\n\n"
            f"❌ {user_name} не успел(а) выполнить работу\n"
            f"📊 Нажато: {clicks}/{REQUIRED_CLICKS}\n"
            f"💸 <b>Награда не выплачена</b>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    
    if clicks == REQUIRED_CLICKS:
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        
        reward = calculate_reward(elapsed)
        
        await callback.message.edit_text(
            f"✅ <b>Работа выполнена!</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"📊 <b>Результат:</b> {clicks}/{REQUIRED_CLICKS} ✅\n"
            f"⏱️ <b>Время:</b> {elapsed:.1f} сек.\n"
            f"💰 <b>Награда:</b> {reward} монет\n"
            f"⏳ <b>Выплата через:</b> 5 минут\n\n"
            f"⚡ <i>{'Отличная скорость!' if elapsed <= 7 else 'Можно быстрее!'}</i>\n",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        
        asyncio.create_task(schedule_payment(bot, user_id, chat_id, reward, user_name))
        
        logger.info(
            f"Work completed by {user.first_name} ({user_id}) in chat {chat_id}, "
            f"time: {elapsed:.1f}s, reward: {reward}, payment scheduled"
        )
        
    elif clicks > REQUIRED_CLICKS:
        session["active"] = False
        cooldown_manager.set_data(session_key, session)
        
        await callback.message.edit_text(
            f"❌ <b>Работа провалена!</b>\n\n"
            f"👤 {user_name} нажал(а) слишком много раз\n"
            f"📊 Нажато: {clicks}/{REQUIRED_CLICKS} ❌\n"
            f"💸 <b>Награда не выплачена</b>\n\n"
            f"💡 <i>Нужно было нажать ровно {REQUIRED_CLICKS} раз!</i>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        
    else:
        keyboard = create_work_keyboard(user_id)
        await callback.message.edit_text(
            f"🔨 <b>Работа в процессе...</b>\n\n"
            f"👤 <b>Работник:</b> {user_name}\n"
            f"📊 <b>Прогресс:</b> {clicks}/{REQUIRED_CLICKS}\n"
            f"⏰ <b>Осталось времени:</b> {int(remaining_time)} сек.\n\n"
            f"🎯 <b>Продолжайте нажимать!</b>",
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
