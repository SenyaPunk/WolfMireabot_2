"""
Команда /freelance (/itwork) — решение реальных айти задач и алгоритмов
"""
import time
import random
import logging
import asyncio
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.economy_manager import EconomyManager
from utils.cooldown_manager import CooldownManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message
from utils.slave_manager import SlaveManager
from utils.it_tasks_db import IT_TASKS_DB, get_tasks_by_category, get_task_by_id, generate_task_test_cases
from utils.code_sandbox import run_code_tests, validate_code_safety
from utils.telegraph_helper import create_telegraph_page
from utils.task_parser import CompanyTaskParser, AlgoTaskParser

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
cooldown_manager = CooldownManager()
user_storage = UserStorage()
slave_manager = SlaveManager()

FREELANCE_COOLDOWN = 43200  # 12 часов
TASK_TIME_LIMIT = 9000     # 2.5 часа (150 минут)


def get_freelance_cooldown_key(user_id: int, chat_id: int) -> str:
    return f"freelance_cooldown:{user_id}:{chat_id}"


def get_freelance_session_key(user_id: int) -> str:
    return f"freelance_session:{user_id}"


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


def extract_code_from_text(text: str) -> str:
    """Извлекает код из блоков ```python ... ``` или берет чистый текст."""
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            code_block = parts[i].strip()
            if code_block.startswith("python"):
                code_block = code_block[6:].strip()
            elif code_block.startswith("py"):
                code_block = code_block[2:].strip()
            return code_block
    return text.strip()


@router.message(Command("freelance", "itwork", "фриланс", "айти"))
async def freelance_command(message: Message, bot: Bot):
    if not message.from_user:
        return

    if message.chat.type == "private":
        await send_error_message(
            message,
            "🚫 <b>Эта команда работает только в группах!</b>\n\n"
            "💡 Вы можете взять фриланс-заказ в групповом чате, а отправлять готовый код решения "
            "сюда в ЛС боту через команду <code>/submit &lt;ваш_код&gt;</code>!"
        )
        return

    user = message.from_user
    chat_id = message.chat.id
    user_name = user.first_name or "Разработчик"

    cooldown_key = get_freelance_cooldown_key(user.id, chat_id)
    remaining_time = cooldown_manager.check_cooldown(cooldown_key, FREELANCE_COOLDOWN)

    if remaining_time is not None:
        await message.reply(
            f"🚫 <b>Вы уже выполняли IT-заказ!</b>\n\n"
            f"⏰ Следующий доступный заказ через <b>{format_time_remaining(remaining_time)}</b>\n"
            f"💡 <i>Отдохните или подтяните знания перед следующей таской...</i>",
            parse_mode="HTML"
        )
        return

    session_key = get_freelance_session_key(user.id)
    session = cooldown_manager.get_data(session_key)

    # Проверяем, есть ли активная задача
    if session and session.get("active", False):
        elapsed = time.time() - session.get("start_time", 0)
        time_left = TASK_TIME_LIMIT - elapsed

        if time_left > 0:
            task = get_task_by_id(session.get("task_id"))
            if task:
                import html
                starter_code_fmt = html.escape(task['starter_code'])
                diff_badge = "🔥 <code>[SENIOR HARD]</code>" if task.get("is_hard") else "⚡ <code>[MEDIUM]</code>"

                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отказаться от задачи", callback_data=f"freelance_cancel:{user.id}")]
                ])
                await message.reply(
                    f"💼 <b>У вас уже есть активный заказ [{task['company']}]!</b>\n\n"
                    f"🎯 <b>Задача:</b> {task['title']} {diff_badge}\n"
                    f"🏷️ <b>Категория:</b> <code>{task['category']}</code> | <b>Стек:</b> <code>{task['language']}</code>\n"
                    f"💰 <b>Награда:</b> <code>{task['reward']} монет</code> | ⏰ <b>Осталось времени:</b> <code>{format_time_remaining(time_left)}</code>\n\n"
                    f"📋 <b>Техническое задание:</b>\n"
                    f"{task['description']}\n\n"
                    f"🛠️ <b>Стартовый шаблон (нажмите для копирования):</b>\n"
                    f"<pre><code class=\"language-python\">{starter_code_fmt}</code></pre>\n\n"
                    f"📤 <b>Как отправить решение:</b>\n"
                    f"Отправьте готовый код <b>ответом (Reply) на это сообщение</b> или <b>в ЛС боту</b> с командой:\n"
                    f"<code>/submit &lt;ваш_код&gt;</code>",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                return

    # Выбор категории (включая новую категорию "Алгосы")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚡ Алгосы", callback_data=f"freelance_cat:Алгосы:{user.id}"),
            InlineKeyboardButton(text="⚙️ Backend", callback_data=f"freelance_cat:Backend:{user.id}")
        ],
        [
            InlineKeyboardButton(text="🎨 Frontend", callback_data=f"freelance_cat:Frontend:{user.id}"),
            InlineKeyboardButton(text="📱 Mobile", callback_data=f"freelance_cat:Mobile:{user.id}")
        ],
        [
            InlineKeyboardButton(text="🛠️ DevOps", callback_data=f"freelance_cat:DevOps:{user.id}"),
            InlineKeyboardButton(text="🎲 Любая задача", callback_data=f"freelance_cat:Any:{user.id}")
        ]
    ])

    await message.reply(
        f"💻 <b>IT-Биржа заказов и Алгоритмов!</b>\n\n"
        f"👤 <b>Разработчик:</b> {user_name}\n"
        f"⏱️ <b>Время на выполнение:</b> 2.5 часа (150 минут)\n"
        f"⚡ <b>Категория Алгосы:</b> награда ~80-160 монет (быстрые алгоритмы)\n"
        f"💼 <b>Категории IT-компаний:</b> награда ~180-380+ монет\n"
        f"🛡️ <b>Анти-чит:</b> К каждой таске генерируются 6-10 случайных динамо-тестов!\n"
        f"⌛ <b>Кулдаун:</b> 12 часов\n\n"
        f"👇 <b>Выберите направление для получения задачи:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("freelance_cat:"))
async def freelance_category_callback(callback_query: CallbackQuery, bot: Bot):
    if not callback_query.data or not callback_query.from_user or not callback_query.message:
        return

    try:
        await callback_query.answer("⏳ Генерируем уникальные тесты... Пожалуйста, подождите!", show_alert=False)
    except Exception:
        pass

    try:
        parts = callback_query.data.split(":")
        category = parts[1]
        user_id = int(parts[2])
    except (IndexError, ValueError):
        await callback_query.message.edit_text("❌ Ошибка обработки выбора.")
        return

    if callback_query.from_user.id != user_id:
        try:
            await callback_query.answer("🚫 Это не ваш фриланс-заказ!", show_alert=True)
        except Exception:
            pass
        return

    try:
        await callback_query.message.edit_text(
            "⏳ <b>Подбираем подходящий IT-заказ и генерируем динамические тесты...</b>\n\n"
            "<i>Формируем случайные стресс-тесты для защиты от хардкода. Пожалуйста, подождите пару секунд...</i>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    chat_id = callback_query.message.chat.id
    user_name = callback_query.from_user.first_name or "Разработчик"

    if category == "Алгосы":
        task = AlgoTaskParser.parse_algo_task(user_id)
    else:
        task = CompanyTaskParser.parse_company_task(category, user_id)

    # Генерируем 6-10 случайных динамических тест-кейсов для предотвращения хардкода
    dynamic_tests = generate_task_test_cases(task["id"])

    session_key = get_freelance_session_key(user_id)
    cooldown_manager.set_data(session_key, {
        "user_id": user_id,
        "chat_id": chat_id,
        "task_id": task["id"],
        "start_time": time.time(),
        "dynamic_tests": dynamic_tests,
        "active": True
    })

    telegraph_url = await asyncio.to_thread(
        create_telegraph_page,
        task["title"],
        task["company"],
        task["description"]
    )

    telegraph_section = ""
    if telegraph_url:
        telegraph_section = f"🌐 <b>Подробная спецификация (Telegraph):</b> <a href=\"{telegraph_url}\">Открыть ТЗ в статьях Telegraph</a>\n\n"

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отказаться от заказа", callback_data=f"freelance_cancel:{user_id}")]
    ])

    import html
    starter_code_fmt = html.escape(task['starter_code'])

    diff_badge = "🔥 <code>[SENIOR HARD]</code>" if task.get("is_hard") else ("⚡ <code>[ALGO]</code>" if task["category"] == "Алгосы" else "⚡ <code>[MEDIUM]</code>")

    await callback_query.message.edit_text(
        f"💼 <b>[JIRA TICKET] {task['company']}</b>\n"
        f"🎯 <b>Задача:</b> {task['title']} {diff_badge}\n"
        f"🏷️ <b>Категория:</b> <code>{task['category']}</code> | <b>Стек:</b> <code>{task['language']}</code>\n"
        f"💰 <b>Награда:</b> <code>{task['reward']} монет</code> | ⏰ <b>Лимит:</b> <code>2.5 часа</code>\n"
        f"🧪 <b>Проверка:</b> <code>{len(dynamic_tests)} случайных тестов</code> (анти-хардкод)\n\n"
        f"📋 <b>Техническое задание:</b>\n"
        f"{task['description']}\n\n"
        f"{telegraph_section}"
        f"🛠️ <b>Стартовый шаблон (нажмите для копирования):</b>\n"
        f"<pre><code class=\"language-python\">{starter_code_fmt}</code></pre>\n\n"
        f"📤 <b>Как отправить решение:</b>\n"
        f"Отправьте готовый код <b>ответом (Reply) на это сообщение</b> или <b>напишите в ЛС боту</b> с командой:\n"
        f"<code>/submit &lt;ваш_код&gt;</code>",
        reply_markup=cancel_kb,
        parse_mode="HTML",
        disable_web_page_preview=False
    )


@router.callback_query(F.data.startswith("freelance_cancel:"))
async def freelance_cancel_callback(callback_query: CallbackQuery):
    if not callback_query.data or not callback_query.from_user or not callback_query.message:
        return

    try:
        user_id = int(callback_query.data.split(":")[1])
    except (IndexError, ValueError):
        return

    if callback_query.from_user.id != user_id:
        try:
            await callback_query.answer("🚫 Это не ваш заказ!", show_alert=True)
        except Exception:
            pass
        return

    session_key = get_freelance_session_key(user_id)
    cooldown_manager.delete_data(session_key)

    await callback_query.message.edit_text(
        f"❌ <b>Фриланс-заказ отменен!</b>\n\n"
        f"💡 <i>Вы можете взять новый заказ через команду /freelance</i>",
        parse_mode="HTML"
    )


@router.message(Command("submit"))
async def submit_code_command(message: Message, bot: Bot):
    await process_code_submission(message, bot)


@router.message(F.text & (F.text.contains("def ") | F.text.contains("```")))
async def code_reply_handler(message: Message, bot: Bot):
    if message.reply_to_message and ("JIRA TICKET" in message.reply_to_message.text or "Стартовый шаблон" in message.reply_to_message.text):
        await process_code_submission(message, bot)


async def process_code_submission(message: Message, bot: Bot):
    if not message.from_user:
        return

    user = message.from_user
    session_key = get_freelance_session_key(user.id)
    session = cooldown_manager.get_data(session_key)

    if not session or not session.get("active", False):
        return

    elapsed = time.time() - session.get("start_time", 0)
    if elapsed > TASK_TIME_LIMIT:
        cooldown_manager.delete_data(session_key)
        await message.reply(
            f"⏰ <b>Время на выполнение заказа истекло!</b> (2.5 часа прошло)\n"
            f"💸 <b>Заказ аннулирован.</b> Попробуйте снова через 12 часов.",
            parse_mode="HTML"
        )
        return

    task = get_task_by_id(session.get("task_id"))
    if not task:
        await message.reply("❌ Ошибка: задача не найдена.")
        return

    raw_text = message.text or ""
    if raw_text.startswith("/submit"):
        raw_text = raw_text[7:].strip()

    code = extract_code_from_text(raw_text)
    if not code:
        await message.reply("⚠️ Не удалось извлечь код. Отправьте код функции в ```python ... ``` или после команды /submit.")
        return

    status_msg = await message.reply("🧪 <b>Запуск 6-10 случайных тестов в песочнице...</b>", parse_mode="HTML")

    # Достаем динамо-тесты сессии
    dynamic_tests = session.get("dynamic_tests")
    if not dynamic_tests:
        dynamic_tests = generate_task_test_cases(task["id"])

    # Запуск тестов песочницы
    test_result = await run_code_tests(code, task["entry_point"], dynamic_tests, elapsed_time_sec=elapsed)

    if test_result["success"]:
        cooldown_manager.delete_data(session_key)

        chat_id = session.get("chat_id", message.chat.id)
        cooldown_key = get_freelance_cooldown_key(user.id, chat_id)
        cooldown_manager.set_cooldown(cooldown_key)

        base_reward = task["reward"]
        user_name = user.first_name or "Разработчик"

        slave_share, master_share, owner_id = slave_manager.process_slave_earnings(user.id, base_reward, percent=0.30)
        economy_manager.add_money(user.id, slave_share)

        user_link = get_user_link(user.id, user_name)

        tax_info = ""
        if owner_id and master_share > 0:
            owner_link = get_user_link(owner_id)
            tax_info = f"\n👑 <b>Налог хозяину {owner_link}:</b> {master_share} монет (30%)"

        await status_msg.edit_text(
            f"🎉 <b>ЗАКАЗ УСПЕШНО ВЫПОЛНЕН!</b>\n\n"
            f"👤 <b>Разработчик:</b> {user_link}\n"
            f"🏢 <b>Заказчик:</b> {task['company']}\n"
            f"⏱️ <b>Затрачено времени:</b> {format_time_remaining(elapsed)}\n\n"
            f"🧪 <b>Результаты стресс-тестирования ({test_result['passed']}/{test_result['total']}):</b>\n"
            f"{test_result['details']}\n\n"
            f"💵 <b>Получено:</b> {slave_share} монет{tax_info}\n"
            f"✅ <i>Деньги зачислены на ваш баланс! Следующий заказ через 12 часов.</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

        logger.info(f"Freelance task {task['id']} completed by {user.id}, reward: {slave_share}")

    else:
        await status_msg.edit_text(
            f"❌ <b>Стресс-тесты не пройдены ({test_result['passed']}/{test_result['total']})!</b>\n\n"
            f"{test_result['details']}\n\n"
            f"⏰ <b>Осталось времени на исправление:</b> {format_time_remaining(TASK_TIME_LIMIT - elapsed)}\n"
            f"💡 <i>Исправьте ошибки и отправьте код повторно! Попытки не ограничены.</i>",
            parse_mode="HTML"
        )
