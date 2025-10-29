"""Команда /work"""
import time
import random
import logging
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.economy_manager import EconomyManager
from utils.cooldown_manager import CooldownManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
cooldown_manager = CooldownManager()
user_storage = UserStorage()

WORK_COOLDOWN = 14400  
WORK_TIME_LIMIT = 30   
REQUIRED_CLICKS = 5   
PAYMENT_DELAY = 1800   # 30 минут задержка перед выплатой


def get_work_cooldown_key(user_id: int, chat_id: int) -> str:
    return f"work_{user_id}_{chat_id}"


def get_work_session_key(user_id: int, chat_id: int) -> str:
    return f"work_session_{user_id}_{chat_id}"


def format_time_remaining(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    
    if hours > 0:
        return f"{hours} ч. {minutes} мин."
    else:
        return f"{minutes} мин."


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


def create_work_keyboard(user_id: int) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton(
        text="🔨 Работать",
        callback_data=f"work_click:{user_id}"
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


async def schedule_payment(bot: Bot, user_id: int, chat_id: int, reward: int, user_name: str):
    await asyncio.sleep(PAYMENT_DELAY)
    
    try:
        economy_manager.add_money(user_id, reward)
        
        user_link = get_user_link(user_id, user_name)
        await bot.send_message(
            chat_id,
            f"💰 <b>Зарплата получена!</b>\n\n"
            f"👤 {user_link}\n"
            f"💵 <b>Сумма:</b> {reward} монет\n\n"
            f"✅ <i>Деньги зачислены на ваш счет!</i>",
            parse_mode="HTML", 
            disable_web_page_preview=True,

        )
        
        logger.info(f"Payment of {reward} coins delivered to user {user_id} in chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to deliver payment to user {user_id}: {e}")


@router.message(Command("work"))
async def work_command(message: Message, bot: Bot):
    if not message.from_user:
        return
    
    user = message.from_user
    chat_id = message.chat.id
    
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
    
    session_key = get_work_session_key(user.id, chat_id)
    cooldown_manager.set_data(session_key, {
        "start_time": time.time(),
        "clicks": 0,
        "active": True,
        "started": False  
    })
    
    start_button = InlineKeyboardButton(
        text="▶️ Начать работать",
        callback_data=f"work_start:{user.id}"
    )
    start_keyboard = InlineKeyboardMarkup(inline_keyboard=[[start_button]])
    
    user_name = user.first_name or "Пользователь"
    
    work_msg = await message.reply(
        f"🏭 <b>Рабочая смена доступна!</b>\n\n"
        f"👤 <b>Работник:</b> {user_name}\n"
        f"🎯 <b>Задача:</b> Нажать кнопку ровно {REQUIRED_CLICKS} раз\n"
        f"⏰ <b>Время:</b> {WORK_TIME_LIMIT} секунд\n"
        f"💰 <b>Награда:</b> зависит от скорости выполнения\n"
        f"⚡ <b>Быстрее = больше монет!</b>\n"
        f"💵 <b>Выплата:</b> через 30 минут после завершения\n\n"
        f"👇 <b>Нажмите кнопку, чтобы начать!</b>",
        reply_markup=start_keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,

    )
    
    session = cooldown_manager.get_data(session_key)
    session["message_id"] = work_msg.message_id
    cooldown_manager.set_data(session_key, session)
    
    logger.info(
        f"Work command used by {user.first_name} ({user.id}) in chat {chat_id}"
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
            f"⏳ <b>Выплата через:</b> 30 минут\n\n"
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
