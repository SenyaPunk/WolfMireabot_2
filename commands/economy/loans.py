"""Модуль команд для микрозаймов и работы коллекторов."""
import logging
import random
import time
from typing import Optional, Dict, List, Tuple, Any
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.economy_manager import EconomyManager
from utils.loan_manager import LoanManager, TARIFFS, COLLECTOR_RANKS, SANCTION_LEVELS, LICENSE_FEE
from utils.cooldown_manager import CooldownManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
loan_manager = LoanManager()
cooldown_manager = CooldownManager()
user_storage = UserStorage()

COLLECTOR_SEIZE_CD = 1800   # 30 минут КД на рейд/изъятие
COLLECTOR_CALL_CD = 600     # 10 минут КД на звонок/прессинг
COLLECTOR_FIGHT_CD = 3600   # 1 час КД на силовой наезд


def format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "истек"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 24:
        days = hours // 24
        rem_hours = hours % 24
        return f"{days}д {rem_hours}ч"
    elif hours > 0:
        return f"{hours}ч {minutes}м"
    else:
        return f"{minutes}м"


# =================================================================
# 1. КОМАНДЫ МИКРОЗАЙМОВ (/loan, /repay, /my_loan)
# =================================================================

def make_loan_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🔹 Лайт (100–350)", callback_data=f"loan_select:light:{user_id}"),
            InlineKeyboardButton(text="🔹 Стандарт (350–900)", callback_data=f"loan_select:standard:{user_id}")
        ],
        [
            InlineKeyboardButton(text="🔹 Премиум (900–2000)", callback_data=f"loan_select:premium:{user_id}"),
            InlineKeyboardButton(text="📊 Мой займ", callback_data=f"loan_info:{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("loan", "займ", "микрозайм", "взять_займ"))
async def loan_command(message: Message):
    user_id = message.from_user.id
    user_name = user_storage.get_display_name(user_id)
    user_link = get_user_link(user_id, user_name)

    # Проверяем аргументы: /займ [тариф] [сумма]
    args = message.text.split()
    if len(args) >= 3:
        tariff_input = args[1].lower()
        tariff_key = None
        if tariff_input in ["light", "лайт", "1"]:
            tariff_key = "light"
        elif tariff_input in ["standard", "стандарт", "2"]:
            tariff_key = "standard"
        elif tariff_input in ["premium", "премиум", "3"]:
            tariff_key = "premium"

        try:
            amount = float(args[2])
        except ValueError:
            amount = None

        if tariff_key and amount is not None:
            ok, res_text, loan_data = loan_manager.take_loan(user_id, tariff_key, amount)
            if not ok:
                await send_error_message(message, res_text)
                return

            t_name = loan_data["tariff_name"]
            debt = loan_data["debt"]
            due_str = format_duration(loan_data["due_at"] - time.time())
            await message.reply(
                f"🏦 <b>МФО «Волк-Экспресс» | Займ выдан!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Заемщик:</b> {user_link}\n"
                f"📋 <b>Тариф:</b> {t_name}\n"
                f"💵 <b>Получено на руки:</b> {amount:.2f} монет\n"
                f"📈 <b>К возврату:</b> {debt:.2f} монет (+{int(loan_data['rate']*100)}%)\n"
                f"⏳ <b>Срок погашения:</b> {due_str}\n\n"
                f"⚠️ <i>При просрочке начисляются штрафные пени, а дело передается коллекторам! Погасить: /repay</i>",
                parse_mode="HTML"
            )
            return

    # Если аргументов нет — выводим витрину тарифов
    hist = loan_manager.get_credit_history(user_id)
    active_loan = loan_manager.get_user_loan(user_id)

    status_line = "✅ Нет активных долгов"
    if active_loan:
        st = "🚨 ПРОСРОЧЕН" if active_loan.get("status") == "overdue" else "⏳ Активен"
        status_line = f"{st}: <b>{active_loan.get('debt', 0):.2f}</b> монет"

    text = (
        f"🏦 <b>МФО «Волк-Экспресс» — Быстрые Микрозаймы</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Клиент: {user_link}\n"
        f"📊 Статус: {status_line}\n"
        f"⭐ Успешно закрытых займов: <b>{hist.get('successful_loans', 0)}</b>\n\n"
        f"<b>Доступные тарифные планы:</b>\n"
        f"🔹 <b>«Лайт»</b>: 100–350 монет | Срок 36ч | Ставка 15%\n"
        f"<i>Доступен всем желающим без проверок.</i>\n\n"
        f"🔹 <b>«Стандарт»</b>: 350–900 монет | Срок 48ч | Ставка 20%\n"
        f"<i>Требуется минимум 1 закрытый займ без нареканий.</i>\n\n"
        f"🔹 <b>«Премиум»</b>: 900–2000 монет | Срок 72ч (3 дня) | Ставка 25%\n"
        f"<i>Для надежных клиентов (от 3 закрытых займов).</i>\n\n"
        f"💡 <i>Выберите тариф кнопкой ниже или укажите вручную:\n<code>/займ [лайт|стандарт|премиум] [сумма]</code></i>"
    )
    await message.reply(text, reply_markup=make_loan_keyboard(user_id), parse_mode="HTML")


@router.callback_query(F.data.startswith("loan_select:"))
async def callback_loan_select(callback: CallbackQuery):
    parts = callback.data.split(":")
    tariff_key = parts[1]
    owner_id = int(parts[2])

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Это меню открыто для другого игрока!", show_alert=True)
        return

    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        await callback.answer("Ошибка тарифа", show_alert=True)
        return

    # Предлагаем суммы (минимальная, средняя, максимальная)
    min_a = tariff["min_amount"]
    max_a = tariff["max_amount"]
    mid_a = round((min_a + max_a) / 2)

    buttons = [
        [
            InlineKeyboardButton(text=f"💵 {min_a} монет", callback_data=f"loan_take:{tariff_key}:{min_a}:{owner_id}"),
            InlineKeyboardButton(text=f"💵 {mid_a} монет", callback_data=f"loan_take:{tariff_key}:{mid_a}:{owner_id}"),
            InlineKeyboardButton(text=f"💵 {max_a} монет", callback_data=f"loan_take:{tariff_key}:{max_a}:{owner_id}")
        ],
        [InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data=f"loan_back:{owner_id}")]
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    debt_min = round(min_a * (1.0 + tariff["rate"]), 2)
    debt_max = round(max_a * (1.0 + tariff["rate"]), 2)
    await callback.message.edit_text(
        f"📋 <b>Оформление тарифа «{tariff['name']}»</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Доступная сумма: <b>{min_a} — {max_a}</b> монет\n"
        f"⏳ Срок возврата: <b>{int(tariff['duration']//3600)} часов</b>\n"
        f"📈 Процентная ставка: <b>+{int(tariff['rate']*100)}%</b>\n"
        f"💵 К возврату: от {debt_min:.2f} до {debt_max:.2f} монет\n\n"
        f"Выберите сумму для зачисления на баланс:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("loan_back:"))
async def callback_loan_back(callback: CallbackQuery):
    owner_id = int(callback.data.split(":")[1])
    if callback.from_user.id != owner_id:
        await callback.answer("❌ Это меню не для вас!", show_alert=True)
        return

    hist = loan_manager.get_credit_history(owner_id)
    active_loan = loan_manager.get_user_loan(owner_id)
    status_line = "✅ Нет активных долгов"
    if active_loan:
        st = "🚨 ПРОСРОЧЕН" if active_loan.get("status") == "overdue" else "⏳ Активен"
        status_line = f"{st}: <b>{active_loan.get('debt', 0):.2f}</b> монет"

    user_link = get_user_link(owner_id)
    text = (
        f"🏦 <b>МФО «Волк-Экспресс» — Быстрые Микрозаймы</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Клиент: {user_link}\n"
        f"📊 Статус: {status_line}\n"
        f"⭐ Успешно закрытых займов: <b>{hist.get('successful_loans', 0)}</b>\n\n"
        f"<b>Доступные тарифные планы:</b>\n"
        f"🔹 <b>«Лайт»</b>: 100–350 монет | Срок 36ч | Ставка 15%\n\n"
        f"🔹 <b>«Стандарт»</b>: 350–900 монет | Срок 48ч | Ставка 20%\n\n"
        f"🔹 <b>«Премиум»</b>: 900–2000 монет | Срок 72ч (3 дня) | Ставка 25%\n"
    )
    await callback.message.edit_text(text, reply_markup=make_loan_keyboard(owner_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("loan_take:"))
async def callback_loan_take(callback: CallbackQuery):
    parts = callback.data.split(":")
    tariff_key = parts[1]
    amount = float(parts[2])
    owner_id = int(parts[3])

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Это действие не для вас!", show_alert=True)
        return

    ok, msg, loan_data = loan_manager.take_loan(owner_id, tariff_key, amount)
    if not ok:
        await callback.answer(msg.replace("<b>", "").replace("</b>", ""), show_alert=True)
        return

    user_link = get_user_link(owner_id)
    due_str = format_duration(loan_data["due_at"] - time.time())
    await callback.message.edit_text(
        f"✅ <b>Займ успешно выдан!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Заемщик:</b> {user_link}\n"
        f"📋 <b>Тариф:</b> {loan_data['tariff_name']}\n"
        f"💵 <b>Получено:</b> {amount:.2f} монет\n"
        f"📈 <b>К возврату:</b> {loan_data['debt']:.2f} монет\n"
        f"⏳ <b>Срок погашения:</b> {due_str}\n\n"
        f"<i>Средства зачислены на ваш игровой счет. Погасить можно командой /repay</i>",
        parse_mode="HTML"
    )
    await callback.answer("Займ получен!")


@router.callback_query(F.data.startswith("loan_info:"))
async def callback_loan_info(callback: CallbackQuery):
    owner_id = int(callback.data.split(":")[1])
    if callback.from_user.id != owner_id:
        await callback.answer("❌ Это меню не для вас!", show_alert=True)
        return

    loan = loan_manager.get_user_loan(owner_id)
    hist = loan_manager.get_credit_history(owner_id)
    user_link = get_user_link(owner_id)

    if not loan:
        await callback.answer("У вас нет активных займов.", show_alert=True)
        return

    is_overdue = (loan.get("status") == "overdue") or (loan.get("due_at", 0) < time.time())
    status_label = "🚨 ПРОСРОЧЕН" if is_overdue else "⏳ Активен"
    rem_time = format_duration(loan.get("due_at", 0) - time.time())

    coll_status = "Никто"
    if loan.get("collector_contract"):
        coll_link = get_user_link(loan["collector_contract"])
        coll_status = f"В разработке у {coll_link}"

    text = (
        f"📋 <b>ИНФОРМАЦИЯ О ТЕКУЩЕМ ЗАЙМЕ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Заемщик:</b> {user_link}\n"
        f"🏷️ <b>Тариф:</b> {loan.get('tariff_name', 'Займ')}\n"
        f"💵 <b>Тело займа:</b> {loan.get('principal', 0):.2f} монет\n"
        f"💸 <b>Остаток к погашению:</b> <b>{loan.get('debt', 0):.2f}</b> монет\n"
        f"📊 <b>Статус:</b> <code>{status_label}</code>\n"
        f"⏳ <b>Срок:</b> {rem_time}\n"
        f"🕵️ <b>Коллектор:</b> {coll_status}\n\n"
        f"💡 <i>Погасить займ: <code>/repay</code></i>"
    )
    buttons = [[InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data=f"loan_back:{owner_id}")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()



@router.message(Command("repay", "погасить", "вернуть_долг", "оплатить_займ"))
async def repay_command(message: Message):
    user_id = message.from_user.id
    user_link = get_user_link(user_id)

    args = message.text.split()
    amount = None
    if len(args) > 1:
        if args[1].lower() in ["all", "все", "всё"]:
            amount = None
        else:
            try:
                amount = float(args[1])
            except ValueError:
                amount = None

    ok, res_text, paid = loan_manager.repay_loan(user_id, amount)
    if not ok:
        await send_error_message(message, res_text)
        return

    await message.reply(
        f"{res_text}\n\n"
        f"👤 Плательщик: {user_link}",
        parse_mode="HTML"
    )


@router.message(Command("my_loan", "мой_займ", "долг"))
async def my_loan_command(message: Message):
    user_id = message.from_user.id
    user_link = get_user_link(user_id)

    loan = loan_manager.get_user_loan(user_id)
    hist = loan_manager.get_credit_history(user_id)

    if not loan:
        await message.reply(
            f"ℹ️ <b>У вас нет активных займов!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Клиент: {user_link}\n"
            f"⭐ Закрыто займов вовремя: <b>{hist.get('successful_loans', 0)}</b>\n"
            f"🚨 Было просрочек: <b>{hist.get('overdue_count', 0)}</b>\n"
            f"💵 Всего взято в кредит: <b>{hist.get('total_borrowed', 0):.2f}</b> монет\n\n"
            f"Взять займ можно командой <code>/loan</code>.",
            parse_mode="HTML"
        )
        return

    is_overdue = (loan.get("status") == "overdue") or (loan.get("due_at", 0) < time.time())
    status_label = "🚨 ПРОСРОЧЕН (OVERDUE)" if is_overdue else "⏳ Активен"
    rem_time = format_duration(loan.get("due_at", 0) - time.time())

    coll_status = "Никто"
    if loan.get("collector_contract"):
        coll_link = get_user_link(loan["collector_contract"])
        coll_status = f"В разработке у {coll_link}"

    await message.reply(
        f"📋 <b>ИНФОРМАЦИЯ О ТЕКУЩЕМ ЗАЙМЕ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Заемщик:</b> {user_link}\n"
        f"🏷️ <b>Тариф:</b> {loan.get('tariff_name', 'Займ')}\n"
        f"💵 <b>Тело займа:</b> {loan.get('principal', 0):.2f} монет\n"
        f"💸 <b>Остаток к погашению:</b> <b>{loan.get('debt', 0):.2f}</b> монет\n"
        f"📊 <b>Статус:</b> <code>{status_label}</code>\n"
        f"⏳ <b>Срок:</b> {rem_time}\n"
        f"🕵️ <b>Коллектор:</b> {coll_status}\n\n"
        f"💡 <i>Погасить займ: <code>/repay</code></i>",
        parse_mode="HTML"
    )


# =================================================================
# 2. КОМАНДЫ КОЛЛЕКТОРА (/collector, /debtors, /become_collector...)
# =================================================================

@router.message(Command("collector", "коллектор"))
async def collector_dashboard(message: Message):
    user_id = message.from_user.id
    user_link = get_user_link(user_id)

    coll = loan_manager.get_collector(user_id)
    if not coll or coll.get("status") != "active":
        text = (
            f"🕵️ <b>Коллекторское агентство «Взыскание»</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Сотрудник: {user_link}\n"
            f"Статус: <b>Не трудоустроен</b>\n\n"
            f"Желаете выбивать долги из неплательщиков и зарабатывать <b>от 20% до 35%</b> комиссии?\n\n"
            f"📌 <b>Условия работы:</b>\n"
            f"• Лицензия и служебное удостоверение: <b>{LICENSE_FEE:.0f}</b> монет\n"
            f"• Отсутствие личных долгов и просрочек\n"
            f"• Санкции за халатность и беспредел: вплоть до бана на 5 дней\n\n"
            f"Для устройства введите: <code>/become_collector</code>"
        )
        await message.reply(text, parse_mode="HTML")
        return

    is_banned, rem_ban, ban_reason = loan_manager.is_collector_banned(user_id)
    rank_key = coll.get("rank", "trainee")
    rank_info = COLLECTOR_RANKS.get(rank_key, COLLECTOR_RANKS["trainee"])
    strikes = coll.get("strikes", 0)

    contract_info = "Нет активного дела"
    if coll.get("active_contract"):
        target_id = coll["active_contract"].get("debtor_id")
        target_link = get_user_link(target_id)
        rem_c = format_duration(coll["active_contract"].get("expires_at", 0) - time.time())
        contract_info = f"{target_link} (ордер истекает через {rem_c})"

    ban_info = "✅ Лицензия активна"
    if is_banned:
        ban_info = f"🚫 <b>ОТСТРАНЕН!</b> Причина: {ban_reason} (осталось: {format_duration(rem_ban)})"

    text = (
        f"💼 <b>СЛУЖЕБНОЕ УДОСТОВЕРЕНИЕ КОЛЛЕКТОРА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Сотрудник:</b> {user_link}\n"
        f"🎖️ <b>Ранг:</b> <b>{rank_info['title']}</b>\n"
        f"💰 <b>Комиссия за выбивание:</b> <b>{int(rank_info['commission']*100)}%</b> от взысканного\n"
        f"📁 <b>Закрыто дел:</b> {coll.get('contracts_closed', 0)}\n"
        f"💵 <b>Всего заработано:</b> {coll.get('total_collected', 0):.2f} монет\n"
        f"⚠️ <b>Взыскания (страйки):</b> {strikes}/3\n"
        f"🛡️ <b>Статус допуска:</b> {ban_info}\n"
        f"🎯 <b>Текущий контракт:</b> {contract_info}\n\n"
        f"<b>Служебные команды:</b>\n"
        f"• <code>/debtors</code> — биржа просроченных должников\n"
        f"• <code>/take_contract [ID]</code> — взять должника в разработку\n"
        f"• <code>/выбить</code> — изъять деньги со счетов должника (рейд)\n"
        f"• <code>/наезд</code> — силовой наезд на должника\n"
        f"• <code>/звонок_должнику</code> — телефонный террор в чате\n"
        f"• <code>/уволиться_коллектор</code> — сдать удостоверение"
    )
    await message.reply(text, parse_mode="HTML")


@router.message(Command("become_collector", "стать_коллектором"))
async def become_collector_command(message: Message):
    user_id = message.from_user.id
    ok, res_text = loan_manager.register_collector(user_id)
    if not ok:
        await send_error_message(message, res_text)
        return

    await message.reply(res_text, parse_mode="HTML")


@router.message(Command("debtors", "должники", "биржа_долгов"))
async def debtors_board_command(message: Message):
    user_id = message.from_user.id
    coll = loan_manager.get_collector(user_id)
    if not coll or coll.get("status") != "active":
        await send_error_message(message, "❌ Доступ к бирже должников открыт только для действующих коллекторов (/collector)!")
        return

    is_banned, rem_ban, _ = loan_manager.is_collector_banned(user_id)
    if is_banned:
        await send_error_message(message, f"🚫 Вы временно отстранены от работы! До конца бана: {format_duration(rem_ban)}.")
        return

    overdue_loans = loan_manager.get_all_overdue_loans()
    if not overdue_loans:
        await message.reply("🕊 <b>Биржа долгов пуста!</b>\nВсе заемщики платят вовремя, либо долги уже взысканы.", parse_mode="HTML")
        return

    lines = ["📋 <b>БИРЖА ПРОСРОЧЕННЫХ ДОЛЖНИКОВ</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"]
    buttons = []

    for debtor_id, loan in overdue_loans[:8]:  # Показываем топ-8
        debtor_name = user_storage.get_display_name(debtor_id)
        debtor_link = get_user_link(debtor_id, debtor_name)
        debt_amount = loan.get("debt", 0.0)
        is_taken = loan.get("collector_contract") is not None
        status_tag = "🔒 В работе" if is_taken else "🟢 СВОБОДЕН"

        lines.append(
            f"👤 {debtor_link} (ID: <code>{debtor_id}</code>)\n"
            f"   💸 Долг: <b>{debt_amount:.2f}</b> монет | {status_tag}\n"
        )
        if not is_taken and not coll.get("active_contract"):
            buttons.append([InlineKeyboardButton(
                text=f"📁 Взять дело {debtor_name[:12]} ({debt_amount:.0f}м)",
                callback_data=f"take_contract:{debtor_id}:{user_id}"
            )])

    lines.append("\n💡 <i>Чтобы взять дело вручную: <code>/take_contract [ID]</code></i>")
    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    await message.reply("\n".join(lines), reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("take_contract:"))
async def callback_take_contract(callback: CallbackQuery):
    parts = callback.data.split(":")
    debtor_id = int(parts[1])
    collector_id = int(parts[2])

    if callback.from_user.id != collector_id:
        await callback.answer("❌ Это действие не для вас!", show_alert=True)
        return

    ok, res_text = loan_manager.take_debt_contract(collector_id, debtor_id)
    if not ok:
        await callback.answer(res_text.replace("<b>", "").replace("</b>", ""), show_alert=True)
        return

    await callback.message.reply(res_text, parse_mode="HTML")
    await callback.answer("Контракт успешно взят!")


@router.message(Command("take_contract", "взять_контракт", "взять_дело"))
async def take_contract_command(message: Message):
    user_id = message.from_user.id
    target_id = None

    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            raw = args[1].lstrip("@")
            if raw.isdigit():
                target_id = int(raw)
            else:
                target_id = user_storage.get_user_id(raw)

    if not target_id:
        await send_error_message(message, "💡 Укажите ID должника или ответьте на его сообщение: <code>/take_contract [ID]</code>")
        return

    ok, res_text = loan_manager.take_debt_contract(user_id, target_id)
    if not ok:
        await send_error_message(message, res_text)
        return

    await message.reply(res_text, parse_mode="HTML")


# =================================================================
# 3. ИСПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ КОЛЛЕКТОРА (РЕЙД, НАЕЗД, ЗВОНОК)
# =================================================================

def _get_target_debtor(message: Message, collector_id: int) -> Optional[int]:
    """Определяет цель: либо из reply, либо из активного контракта."""
    if message.reply_to_message:
        return message.reply_to_message.from_user.id

    coll = loan_manager.get_collector(collector_id)
    if coll and coll.get("active_contract"):
        return coll["active_contract"].get("debtor_id")
    return None


@router.message(Command("collect_seize", "выбить", "рейд", "изъять"))
async def collect_seize_command(message: Message):
    collector_id = message.from_user.id
    collector_link = get_user_link(collector_id)

    is_banned, rem_ban, _ = loan_manager.is_collector_banned(collector_id)
    if is_banned:
        await send_error_message(message, f"🚫 Вы отстранены от работы! До конца бана: {format_duration(rem_ban)}.")
        return

    coll = loan_manager.get_collector(collector_id)
    if not coll or coll.get("status") != "active":
        await send_error_message(message, "❌ Вы не работаете коллектором!")
        return

    debtor_id = _get_target_debtor(message, collector_id)
    if not debtor_id:
        await send_error_message(
            message,
            "💡 <b>Как провести рейд:</b>\n"
            "• Ответьте на сообщение должника командой <code>/выбить</code>\n"
            "• Либо возьмите контракт на бирже (<code>/debtors</code>) и напишите команду в чате."
        )
        return

    if debtor_id == collector_id:
        await send_error_message(message, "❌ Вы не можете выбивать долг из самого себя!")
        return

    loan = loan_manager.get_user_loan(debtor_id)
    if not loan or (loan.get("status") != "overdue" and loan.get("due_at", 0) > time.time()):
        # Ложный наезд на невиновного!
        strikes, ban_time, sanction_desc = loan_manager.apply_sanction(
            collector_id,
            f"Беспредел: незаконный рейд на игрока {debtor_id} без просроченных задолженностей"
        )
        await message.reply(
            f"🚨 <b>ГРУБОЕ НАРУШЕНИЕ ЗАКОНА О КОЛЛЕКТОРСКОЙ ДЕЯТЕЛЬНОСТИ!</b>\n\n"
            f"У гражданина нет просроченных займов!\n\n"
            f"{sanction_desc}",
            parse_mode="HTML"
        )
        return

    # Проверка кулдауна
    cd_key = f"collector_seize:{collector_id}:{debtor_id}"
    cd_left = cooldown_manager.check_cooldown(cd_key, COLLECTOR_SEIZE_CD)
    if cd_left:
        await send_error_message(message, f"⏳ Судебные приставы оформляют документы. Повторный рейд возможен через <b>{format_duration(cd_left)}</b>.")
        return

    debtor_balance = economy_manager.get_balance(debtor_id)
    current_debt = loan.get("debt", 0.0)

    debtor_link = get_user_link(debtor_id)

    # Засчитываем действие в контракт
    if coll.get("active_contract") and coll["active_contract"].get("debtor_id") == debtor_id:
        coll["active_contract"]["actions_done"] = coll["active_contract"].get("actions_done", 0) + 1

    cooldown_manager.set_cooldown(cd_key)

    if debtor_balance <= 0.5:
        await message.reply(
            f"🏚️ <b>РЕЙД ПРОВАЛЕН: В КАРМАНАХ ПУСТО!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕵️ Коллектор: {collector_link}\n"
            f"🎯 Должник: {debtor_link}\n\n"
            f"У должника на балансе <b>0 монет</b>. Описывать нечего!\n"
            f"Попробуйте применить <code>/наезд</code> или подождать, пока он заработает монеты.",
            parse_mode="HTML"
        )
        return

    # Изъятие: изымается до 50% баланса должника, но не более суммы долга
    seize_amount = round(min(debtor_balance * 0.50, current_debt), 2)
    if seize_amount < 1.0:
        seize_amount = min(debtor_balance, current_debt)

    economy_manager.remove_money(debtor_id, seize_amount)
    collector_pay, mfi_pay, is_closed = loan_manager.process_collector_success(collector_id, debtor_id, seize_amount)

    rank_name = COLLECTOR_RANKS.get(coll.get("rank", "trainee"), {}).get("title", "Коллектор")

    res_text = (
        f"🚨 <b>УСПЕШНЫЙ РЕЙД: ИЗЪЯТИЕ СРЕДСТВ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕵️ <b>Взыскатель:</b> {collector_link} ({rank_name})\n"
        f"🎯 <b>Должник:</b> {debtor_link}\n\n"
        f"⚖️ С банковского счета должника принудительно списано: <b>{seize_amount:.2f}</b> монет!\n"
        f"💵 <b>Комиссия коллектора:</b> <b>+{collector_pay:.2f}</b> монет\n"
        f"🏦 <b>В счет долга МФО:</b> {mfi_pay:.2f} монет\n"
    )

    if is_closed:
        res_text += f"\n🎉 <b>ДОЛГ ПОЛНОСТЬЮ ЗАКРЫТ!</b> Дело сдано в архив, дело закрыто!"
    else:
        new_debt = loan.get("debt", 0.0)
        res_text += f"\n📉 <b>Остаток долга:</b> {new_debt:.2f} монет."

    await message.reply(res_text, parse_mode="HTML")


@router.message(Command("collect_fight", "наезд", "силовой_наезд"))
async def collect_fight_command(message: Message):
    collector_id = message.from_user.id
    collector_link = get_user_link(collector_id)

    is_banned, rem_ban, _ = loan_manager.is_collector_banned(collector_id)
    if is_banned:
        await send_error_message(message, f"🚫 Вы отстранены от работы! До конца бана: {format_duration(rem_ban)}.")
        return

    coll = loan_manager.get_collector(collector_id)
    if not coll or coll.get("status") != "active":
        await send_error_message(message, "❌ Вы не являетесь коллектором!")
        return

    debtor_id = _get_target_debtor(message, collector_id)
    if not debtor_id or debtor_id == collector_id:
        await send_error_message(message, "💡 Ответьте на сообщение должника командой <code>/наезд</code>")
        return

    loan = loan_manager.get_user_loan(debtor_id)
    if not loan or (loan.get("status") != "overdue" and loan.get("due_at", 0) > time.time()):
        strikes, _, sanction_desc = loan_manager.apply_sanction(
            collector_id,
            f"Беспредел: силовой наезд на добросовестного игрока {debtor_id}"
        )
        await message.reply(
            f"🚨 <b>ГРУБОЕ НАРУШЕНИЕ: НАПАДЕНИЕ НА НЕВИНОВНОГО!</b>\n\n{sanction_desc}",
            parse_mode="HTML"
        )
        return

    cd_key = f"collector_fight:{collector_id}:{debtor_id}"
    cd_left = cooldown_manager.check_cooldown(cd_key, COLLECTOR_FIGHT_CD)
    if cd_left:
        await send_error_message(message, f"⏳ Передышка между наездами. Подождите <b>{format_duration(cd_left)}</b>.")
        return

    cooldown_manager.set_cooldown(cd_key)
    debtor_link = get_user_link(debtor_id)

    if coll.get("active_contract") and coll["active_contract"].get("debtor_id") == debtor_id:
        coll["active_contract"]["actions_done"] = coll["active_contract"].get("actions_done", 0) + 1

    # Расчет вероятности успеха в зависимости от ранга
    base_chance = 0.55
    if coll.get("rank") == "enforcer":
        base_chance = 0.65
    elif coll.get("rank") == "senior":
        base_chance = 0.75
    elif coll.get("rank") == "chief":
        base_chance = 0.85

    roll = random.random()

    # 1. Должник дает жесткий отпор коллектору (15% шанс)
    if roll < 0.15:
        await message.reply(
            f"🚑 <b>ОТПОР ДОЛЖНИКА! КОЛЛЕКТОР В ТРАВМПУНКТЕ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Должник {debtor_link} достал монтировку и дал жесткий отпор!\n"
            f"Коллектор {collector_link} с позором ретировался и доставлен в больницу.\n"
            f"🤕 Действие заблокировано на 1 час.",
            parse_mode="HTML"
        )
        return

    # 2. Успешный силовой прессинг (выбивание монет)
    current_debt = loan.get("debt", 0.0)
    debtor_bal = economy_manager.get_balance(debtor_id)

    # Если у должника есть монеты — выбивается 30-70%
    if debtor_bal > 5.0:
        seize = round(min(debtor_bal * random.uniform(0.3, 0.7), current_debt), 2)
        economy_manager.remove_money(debtor_id, seize)
    else:
        # У должника нет денег, но под прессингом он занимает/находит экстренные 30-60 монет
        seize = round(min(random.uniform(30.0, 60.0), current_debt), 2)

    col_share, mfi_share, is_closed = loan_manager.process_collector_success(collector_id, debtor_id, seize)

    phrase = random.choice([
        "прижал должника к батарее и убедил внести платеж",
        "достал паяльник и доходчиво объяснил график платежей",
        "наведался в подъезд должника и провел разъяснительную беседу",
        "напомнил должнику о хрупкости его коленных чашечек"
    ])

    text = (
        f"🥊 <b>СИЛОВОЙ НАЕЗД УВЕНЧАЛСЯ УСПЕХОМ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Коллектор {collector_link} {phrase}!\n\n"
        f"🎯 Должник {debtor_link} в панике выплатил: <b>{seize:.2f}</b> монет!\n"
        f"💵 <b>Доля коллектора:</b> <b>+{col_share:.2f}</b> монет\n"
        f"🏦 <b>Погашено долга:</b> {mfi_share:.2f} монет\n"
    )
    if is_closed:
        text += "\n🎉 <b>ДОЛГ ПОЛНОСТЬЮ ЛИКВИДИРОВАН!</b> Дело закрыто!"

    await message.reply(text, parse_mode="HTML")


@router.message(Command("collect_call", "звонок_должнику", "прессинг"))
async def collect_call_command(message: Message):
    collector_id = message.from_user.id
    coll = loan_manager.get_collector(collector_id)
    if not coll or coll.get("status") != "active":
        await send_error_message(message, "❌ Только действующие коллекторы могут использовать эту команду.")
        return

    debtor_id = _get_target_debtor(message, collector_id)
    if not debtor_id or debtor_id == collector_id:
        await send_error_message(message, "💡 Ответьте на сообщение должника командой <code>/звонок_должнику</code>")
        return

    loan = loan_manager.get_user_loan(debtor_id)
    if not loan or (loan.get("status") != "overdue" and loan.get("due_at", 0) > time.time()):
        strikes, _, sanction_desc = loan_manager.apply_sanction(
            collector_id,
            f"Беспредел: незаконный звонок и давление на добросовестного игрока {debtor_id}"
        )
        await message.reply(
            f"🚨 <b>НАРУШЕНИЕ РЕГЛАМЕНТА ЗВОНКОВ!</b>\n\n{sanction_desc}",
            parse_mode="HTML"
        )
        return

    cd_key = f"collector_call:{collector_id}:{debtor_id}"
    cd_left = cooldown_manager.check_cooldown(cd_key, COLLECTOR_CALL_CD)
    if cd_left:
        await send_error_message(message, f"⏳ Телефонная линия занята. Повторный звонок через <b>{format_duration(cd_left)}</b>.")
        return

    cooldown_manager.set_cooldown(cd_key)
    if coll.get("active_contract") and coll["active_contract"].get("debtor_id") == debtor_id:
        coll["active_contract"]["actions_done"] = coll["active_contract"].get("actions_done", 0) + 1

    debtor_link = get_user_link(debtor_id)
    collector_link = get_user_link(collector_id)

    insult = random.choice([
        "Алло, гражданин! Ваши долги сами себя не вернут. Напоминаем, что мы знаем, где вы работаете!",
        "Здравствуйте! Вы забыли, что брали монеты в «Волк-Экспресс»? Проценты капают каждую минуту!",
        "Добрый вечер. Ваш кредитный рейтинг на дне, а за вашим подъездом уже наблюдают. Верните долг!",
        "Уважаемый неплательщик! Либо вы вносите платеж прямо сейчас (/repay), либо следующий визит будет с утюгом!"
    ])

    await message.reply(
        f"📞 <b>ТЕЛЕФОННЫЙ ПРЕССИНГ ДОЛЖНИКА!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕵️ <b>Коллектор:</b> {collector_link}\n"
        f"🎯 <b>Абонент:</b> {debtor_link}\n\n"
        f"📢 <i>«{insult}»</i>\n\n"
        f"💸 Текущий долг: <b>{loan.get('debt', 0):.2f}</b> монет. Срочно погасите: <code>/repay</code>",
        parse_mode="HTML"
    )


@router.message(Command("report_collector", "жалоба_коллектор", "жалоба_на_коллектора"))
async def report_collector_command(message: Message):
    """Жалоба должника на действия коллектора."""
    user_id = message.from_user.id
    if not message.reply_to_message:
        await send_error_message(
            message,
            "💡 <b>Как подать жалобу:</b>\nОтветьте на сообщение коллектора командой <code>/жалоба_коллектор</code>"
        )
        return

    target_collector_id = message.reply_to_message.from_user.id
    if target_collector_id == user_id:
        await send_error_message(message, "❌ Вы не можете жаловаться на самого себя.")
        return

    coll = loan_manager.get_collector(target_collector_id)
    if not coll:
        await send_error_message(message, "❌ Этот пользователь не зарегистрирован в коллекторском агентстве.")
        return

    # Проверяем, есть ли у подающего жалобу просроченный долг
    loan = loan_manager.get_user_loan(user_id)
    has_overdue = loan and (loan.get("status") == "overdue" or loan.get("due_at", 0) < time.time())

    if not has_overdue:
        # Коллектор наезжал на того, у кого нет долга! Удовлетворяем жалобу немедленно
        strikes, ban_time, sanction_desc = loan_manager.apply_sanction(
            target_collector_id,
            f"Обоснованная жалоба: травля добросовестного игрока {user_id}"
        )
        await message.reply(
            f"⚖️ <b>ЖАЛОБА УДОВЛЕТВОРЕНА ИНСПЕКЦИЕЙ!</b>\n\n"
            f"Установлен факт превышения полномочий и психологического давления на гражданина без долгов.\n\n"
            f"{sanction_desc}",
            parse_mode="HTML"
        )
    else:
        # У игрока есть долг — проверяем, не совершал ли коллектор действий в обход правил
        await message.reply(
            f"⚖️ <b>ЖАЛОБА ОТКЛОНЕНА!</b>\n\n"
            f"Инспекция установила: у вас имеется непогашенный просроченный долг на сумму <b>{loan.get('debt', 0):.2f}</b> монет.\n"
            f"Действия взыскателя признаны законными. Погасите задолженность командой <code>/repay</code>.",
            parse_mode="HTML"
        )


@router.message(Command("collector_leave", "уволиться_коллектор"))
async def collector_leave_command(message: Message):
    user_id = message.from_user.id
    ok, res_text = loan_manager.resign_collector(user_id)
    if not ok:
        await send_error_message(message, res_text)
        return
    await message.reply(res_text, parse_mode="HTML")
