"""Модуль команд для оформления судебного банкротства и списания долгов."""
import logging
import random
import time
from typing import Optional, Dict, List, Any
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from utils.bankruptcy_manager import (
    BankruptcyManager,
    MIN_DEBT_FOR_BANKRUPTCY,
    MAX_BALANCE_FOR_BANKRUPTCY,
    SERVICE_SHIFTS_TOTAL,
    SERVICE_COOLDOWN,
    SERVICE_PAY_PER_SHIFT
)
from utils.loan_manager import LoanManager
from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

bankruptcy_mgr = BankruptcyManager()
loan_mgr = LoanManager()
economy_mgr = EconomyManager()
slave_mgr = SlaveManager()
user_storage = UserStorage()


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
# 1. ГЛАВНАЯ КОМАНДА /bankrupt
# =================================================================

@router.message(Command("bankrupt", "банкротство", "банкрот"))
async def bankrupt_command(message: Message):
    user_id = message.from_user.id
    user_name = user_storage.get_display_name(user_id)
    user_link = get_user_link(user_id, user_name)

    active_case = bankruptcy_mgr.get_case(user_id)

    # 1. Если уже идет активное судебное дело
    if active_case:
        status = active_case.get("status")
        initial_debt = active_case.get("initial_debt", 0.0)
        rem_debt = active_case.get("remaining_debt", initial_debt)

        if status == "awaiting_choice":
            text = (
                f"⚖️ <b>ВОЛЧИЙ АРБИТРАЖНЫЙ СУД | ДЕЛО #{user_id}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Должник:</b> {user_link}\n"
                f"📉 <b>Сумма к списанию:</b> <b>{initial_debt:.2f}</b> монет\n"
                f"🛡️ <i>Судебный иммунитет от коллекторов: АКТИВЕН</i>\n\n"
                f"Опись имущества завершена. Выберите <b>путь реабилитации стаи</b>:\n\n"
                f"1️⃣ <b>🧹 Общественные работы</b> — {SERVICE_SHIFTS_TOTAL} смен (раз в 15 мин). За каждую смену списание долга и +{SERVICE_PAY_PER_SHIFT:.0f}м на еду.\n"
                f"2️⃣ <b>🔨 Долговой аукцион</b> — выставление лота в чат. Олигарх может выкупить вас в рабство за {active_case['auction_data']['buyout_price']:.0f}м, а долг МФО сгорит.\n"
                f"3️⃣ <b>🎲 Судебный поединок</b> — испытание волчьих костей против Пристава Лютого (3 раунда). Победа = мгновенное списание 100% долга!"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧹 Выбрать Общественные работы", callback_data=f"bankrupt_path:service:{user_id}")],
                [InlineKeyboardButton(text="🔨 Выставиться на Долговой аукцион", callback_data=f"bankrupt_path:auction:{user_id}")],
                [InlineKeyboardButton(text="🎲 Бросить вызов Приставу Лютому", callback_data=f"bankrupt_path:duel:{user_id}")],
            ])
            await message.reply(text, reply_markup=kb, parse_mode="HTML")
            return

        elif status == "service":
            s_data = active_case["service_data"]
            shifts_done = s_data.get("shifts_done", 0)
            shifts_needed = s_data.get("shifts_needed", SERVICE_SHIFTS_TOTAL)
            now = time.time()
            last_shift = s_data.get("last_shift_at", 0.0)
            cd_rem = max(0.0, SERVICE_COOLDOWN - (now - last_shift))

            cd_str = f"⏳ До смены: <b>{int(cd_rem // 60)}м {int(cd_rem % 60)}с</b>" if cd_rem > 0 else "🟢 <b>Смена готова к началу!</b>"

            text = (
                f"🧹 <b>ИСПРАВИТЕЛЬНЫЕ РАБОТЫ | ДЕЛО #{user_id}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Штрафник:</b> {user_link}\n"
                f"📊 <b>Прогресс:</b> <b>{shifts_done}</b> из <b>{shifts_needed}</b> смен\n"
                f"📉 <b>Остаток долга:</b> {rem_debt:.2f} монет\n"
                f"💵 <b>Получено на питание:</b> +{s_data.get('total_earned_pocket', 0.0):.2f} монет\n"
                f"{cd_str}\n\n"
                f"<i>Выполните все смены для полного аннулирования долга. Команда: /clean</i>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧹 Выйти на смену (/clean)", callback_data=f"bankrupt_shift:{user_id}")]
            ])
            await message.reply(text, reply_markup=kb, parse_mode="HTML")
            return

        elif status == "auction":
            a_data = active_case["auction_data"]
            buyout_price = a_data["buyout_price"]
            text = (
                f"🔨 <b>ДОЛГОВОЙ АУКЦИОН КАТОРЖНИКА!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Должник:</b> {user_link}\n"
                f"💸 <b>Сумма долга МФО:</b> {initial_debt:.2f} монет\n"
                f"🏷️ <b>Цена выкупа олигархом:</b> <b>{buyout_price:.2f}</b> монет\n\n"
                f"<i>Любой игрок чата может выкупить вас в рабство! При выкупе все ваши кредиты аннулируются судом.</i>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💰 Выкупить каторжника за {buyout_price:.0f}м", callback_data=f"bankrupt_buyout:{user_id}")]
            ])
            await message.reply(text, reply_markup=kb, parse_mode="HTML")
            return

        elif status == "duel":
            d_data = active_case["duel_data"]
            rounds = d_data.get("rounds_played", 0)
            text = (
                f"🎲 <b>СУДЕБНЫЙ ПОЕДИНОК С ПРИСТАВОМ ЛЮТЫМ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Подсудимый:</b> {user_link}\n"
                f"⚔️ <b>Счет (Игрок : Пристав):</b> <b>{d_data.get('player_score', 0)} : {d_data.get('bailiff_score', 0)}</b>\n"
                f"🎯 <b>Сыграно раундов:</b> {rounds} из 3\n\n"
                f"<i>Бросайте кости стаи! Победитель раунда определяется старшей суммой 2d6.</i>"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲 Бросить кости стаи (2d6)!", callback_data=f"bankrupt_duel_roll:{user_id}")]
            ])
            await message.reply(text, reply_markup=kb, parse_mode="HTML")
            return

    # 2. Если дела нет, проверяем возможность подачи
    can, reason = bankruptcy_mgr.can_declare_bankruptcy(user_id)
    total_debt = loan_mgr.get_total_debt(user_id)
    overdue_debt = loan_mgr.get_total_overdue_debt(user_id)
    balance = economy_mgr.get_balance(user_id)

    has_imm, rem_imm = bankruptcy_mgr.has_immunity(user_id)
    imm_str = f"🛡️ Судебный иммунитет: ещё {format_duration(rem_imm)}\n" if has_imm else ""

    if not can:
        await message.reply(
            f"⚖️ <b>ВОЛЧИЙ АРБИТРАЖНЫЙ СУД | БАНКРОТСТВО</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Гражданин:</b> {user_link}\n"
            f"💰 <b>Ваш баланс:</b> {balance:.2f} монет\n"
            f"💳 <b>Общий долг:</b> {total_debt:.2f} монет (просрочено: {overdue_debt:.2f}м)\n"
            f"{imm_str}\n"
            f"<b>Критерии для возбуждения дела:</b>\n"
            f"• Просроченный долг: от <b>{MIN_DEBT_FOR_BANKRUPTCY:.0f}</b> монет\n"
            f"• Баланс на руках: не более <b>{MAX_BALANCE_FOR_BANKRUPTCY:.0f}</b> монет\n"
            f"• Отсутствие судебного моратория (раз в 21 день)\n\n"
            f"⚠️ <b>Вердикт секретаря суда:</b>\n{reason}",
            parse_mode="HTML"
        )
        return

    # Если всё подходит — выводим кнопку подачи
    text = (
        f"⚖️ <b>ВОЛЧИЙ АРБИТРАЖНЫЙ СУД | ПОДАЧА ЗАЯВЛЕНИЯ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Заявитель:</b> {user_link}\n"
        f"💳 <b>Сумма долга:</b> <b>{total_debt:.2f}</b> монет\n"
        f"💰 <b>Остаток в кармане:</b> {balance:.2f} монет\n\n"
        f"Вы признаны <b>критически несостоятельным должником</b> стаи.\n"
        f"Подача заявления запустит процедуру банкротства:\n"
        f"• 🚨 Коллекторы получат запрет на наезды и изъятия (судебный иммунитет).\n"
        f"• 📦 Баланс ({balance:.2f}м) конфискуется в Государственную Казну.\n"
        f"• 📜 Вам будет предложен выбор реабилитации (исправительные работы, аукцион или судебный поединок).\n\n"
        f"Желаете запустить официальное банкротство?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚖️ Начать процедуру банкротства", callback_data=f"bankrupt_declare:{user_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"bankrupt_cancel:{user_id}")]
    ])
    await message.reply(text, reply_markup=kb, parse_mode="HTML")


# =================================================================
# 2. ОБРАБОТЧИКИ CALLBACK: СТАРТ И ВЫБОР ПУТИ
# =================================================================

@router.callback_query(F.data.startswith("bankrupt_declare:"))
async def callback_declare_bankruptcy(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это заседание не для вас!", show_alert=True)
        return

    ok, res_text, case_data = bankruptcy_mgr.declare_bankruptcy(user_id)
    if not ok:
        await callback.answer(res_text, show_alert=True)
        return

    user_link = get_user_link(user_id, callback.from_user.full_name)
    initial_debt = case_data["initial_debt"]
    confiscated = case_data["confiscated_money"]
    auction_price = case_data["auction_data"]["buyout_price"]

    text = (
        f"⚖️ <b>СУДЕБНЫЙ ПРОЦЕСС ВОЗБУЖДЕН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Должник:</b> {user_link}\n"
        f"📉 <b>Зафиксированный долг:</b> <b>{initial_debt:.2f}</b> монет\n"
        f"🏛️ <b>Конфисковано в Казну:</b> {confiscated:.2f} монет\n"
        f"🛡️ <b>Судебный иммунитет:</b> ВВЕДЁН! Коллекторы отстранены.\n\n"
        f"Выберите <b>способ закрытия дела</b>:\n\n"
        f"1️⃣ <b>🧹 Исправительные работы:</b> {SERVICE_SHIFTS_TOTAL} смен по 15 минут. Гарантированное списание + 25м на карман за смену.\n"
        f"2️⃣ <b>🔨 Долговой аукцион:</b> лот выкупа за {auction_price:.0f} монет в чате. Спонсор спасает вас от долга.\n"
        f"3️⃣ <b>🎲 Судебный поединок:</b> 3 раунда на костях против Пристава Лютого. Победа = мгновенное списание 100%!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 1. Исправительные работы", callback_data=f"bankrupt_path:service:{user_id}")],
        [InlineKeyboardButton(text="🔨 2. Выставиться на аукцион", callback_data=f"bankrupt_path:auction:{user_id}")],
        [InlineKeyboardButton(text="🎲 3. Судебный поединок", callback_data=f"bankrupt_path:duel:{user_id}")],
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("Дело о банкротстве официально открыто!")


@router.callback_query(F.data.startswith("bankrupt_cancel:"))
async def callback_cancel_bankruptcy(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это действие не для вас!", show_alert=True)
        return
    await callback.message.edit_text("❌ Подача заявления о банкротстве отменена.", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("bankrupt_path:"))
async def callback_choose_path(callback: CallbackQuery):
    parts = callback.data.split(":")
    path = parts[1]
    user_id = int(parts[2])

    if callback.from_user.id != user_id:
        await callback.answer("❌ Это действие не для вас!", show_alert=True)
        return

    ok, res_text = bankruptcy_mgr.choose_path(user_id, path)
    if not ok:
        await callback.answer(res_text, show_alert=True)
        return

    case = bankruptcy_mgr.get_case(user_id)
    user_link = get_user_link(user_id, callback.from_user.full_name)

    if path == "service":
        text = (
            f"🧹 <b>ВЫБРАНЫ ОБЩЕСТВЕННЫЕ РАБОТЫ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Штрафник:</b> {user_link}\n"
            f"📊 <b>Требуется отработать:</b> {SERVICE_SHIFTS_TOTAL} смен\n"
            f"⏳ <b>Кулдаун между сменами:</b> 15 минут\n"
            f"💵 <b>Оплата на руки:</b> +{SERVICE_PAY_PER_SHIFT:.0f} монет за каждую смену\n\n"
            f"Первая смена уже доступна! Нажмите кнопку ниже или введите <code>/clean</code>."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Выйти на смену прямо сейчас!", callback_data=f"bankrupt_shift:{user_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer("Путь исправительных работ утвержден!")

    elif path == "auction":
        buyout_price = case["auction_data"]["buyout_price"]
        debt = case["initial_debt"]
        text = (
            f"🔨 <b>ВЫСТАВЛЕНИЕ НА ДОЛГОВОЙ АУКЦИОН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📢 <b>Внимание стаи!</b> Должник {user_link} выставлен на торги!\n\n"
            f"💸 <b>Аннулируемый долг:</b> <b>{debt:.2f}</b> монет\n"
            f"🏷️ <b>Цена выкупа каторжника:</b> <b>{buyout_price:.2f}</b> монет\n\n"
            f"<i>Любой состоятельный волк может выкупить каторжника в рабство. Средства пойдут в Казну, а долг должника перед МФО будет навсегда прощен!</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Выкупить каторжника ({buyout_price:.0f}м)", callback_data=f"bankrupt_buyout:{user_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer("Лот выставлен на аукцион!")

    elif path == "duel":
        text = (
            f"🎲 <b>СУДЕБНЫЙ ПОЕДИНОК НАЗНАЧЕН!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Подсудимый:</b> {user_link}\n"
            f"⚖️ <b>Оппонент:</b> Старший судебный пристав «Лютый»\n\n"
            f"<b>Правила испытания стаи:</b>\n"
            f"• 3 раунда бросков волчьих костей (2d6 против 2d6).\n"
            f"• Побеждает набравший большее число очков.\n"
            f"• <b>Победа в поединке:</b> немедленное списание 100% долга ({case['initial_debt']:.2f}м)!\n"
            f"• <b>Поражение:</b> списание 60% долга, оставшиеся 40% — отработка всего 4 легких смен."
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Раунд 1: Бросить кости!", callback_data=f"bankrupt_duel_roll:{user_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer("Испытание началось!")


# =================================================================
# 3. ИСПРАВИТЕЛЬНЫЕ РАБОТЫ (/clean, /штрафбат)
# =================================================================

@router.message(Command("clean", "штрафбат", "исправительные_работы", "месить_глину"))
async def clean_command(message: Message):
    user_id = message.from_user.id
    ok, res_text, finished = bankruptcy_mgr.perform_service_shift(user_id)
    if not ok:
        await send_error_message(message, res_text)
        return

    await message.reply(res_text, parse_mode="HTML")


@router.callback_query(F.data.startswith("bankrupt_shift:"))
async def callback_service_shift(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это не ваша смена!", show_alert=True)
        return

    ok, res_text, finished = bankruptcy_mgr.perform_service_shift(user_id)
    if not ok:
        await callback.answer(res_text.replace("<b>", "").replace("</b>", ""), show_alert=True)
        return

    if finished:
        await callback.message.edit_text(res_text, parse_mode="HTML")
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧹 Выйти на следующую смену (/clean)", callback_data=f"bankrupt_shift:{user_id}")]
        ])
        await callback.message.edit_text(res_text, reply_markup=kb, parse_mode="HTML")

    await callback.answer("Смена засчитана!")


# =================================================================
# 4. ВЫКУП НА ДОЛГОВОМ АУКЦИОНЕ
# =================================================================

@router.callback_query(F.data.startswith("bankrupt_buyout:"))
async def callback_buyout_bankrupt(callback: CallbackQuery):
    bankrupt_id = int(callback.data.split(":")[1])
    buyer_id = callback.from_user.id

    ok, res_text = bankruptcy_mgr.buyout_bankrupt(buyer_id, bankrupt_id)
    if not ok:
        await callback.answer(res_text.replace("<b>", "").replace("</b>", ""), show_alert=True)
        return

    bankrupt_name = user_storage.get_display_name(bankrupt_id)
    bankrupt_link = get_user_link(bankrupt_id, bankrupt_name)
    buyer_link = get_user_link(buyer_id, callback.from_user.full_name)

    announcement = (
        f"🔨 <b>АУКЦИОН КАТОРЖНИКОВ ЗАВЕРШЕН!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Покупатель:</b> {buyer_link}\n"
        f"⛓️ <b>Приобретенный каторжник:</b> {bankrupt_link}\n\n"
        f"🎉 <b>РЕШЕНИЕ СУДА:</b> Все долги заемщика перед МФО «Волк-Экспресс» <b>полностью аннулированы</b>!\n"
        f"🛡️ Бывший должник получает судебный иммунитет от коллекторов на 7 дней."
    )
    await callback.message.edit_text(announcement, parse_mode="HTML")
    await callback.answer("Сделка оформлена!")


# =================================================================
# 5. СУДЕБНЫЙ ПОЕДИНОК (ДУЭЛЬ НА КОСТЯХ)
# =================================================================

@router.callback_query(F.data.startswith("bankrupt_duel_roll:"))
async def callback_duel_roll(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это не ваш судебный процесс!", show_alert=True)
        return

    ok, res_text, payload = bankruptcy_mgr.play_duel_round(user_id)
    if not ok:
        await callback.answer(res_text, show_alert=True)
        return

    round_num = payload["round"]
    p_dice = payload["player_dice"]
    b_dice = payload["bailiff_dice"]
    p_score = payload["player_score"]
    b_score = payload["bailiff_score"]
    winner = payload["round_winner"]

    w_text = "🎉 Вы выиграли этот раунд!" if winner == "player" else ("💀 Пристав Лютый забрал раунд!" if winner == "bailiff" else "🤝 Ничья в раунде!")

    user_link = get_user_link(user_id, callback.from_user.full_name)

    if not payload["is_finished"]:
        text = (
            f"🎲 <b>СУДЕБНЫЙ ПОЕДИНОК | РАУНД {round_num}/3</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 {user_link}: {p_dice}\n"
            f"⚖️ Пристав Лютый: {b_dice}\n\n"
            f"{w_text}\n"
            f"📊 <b>Текущий счет:</b> {p_score} : {b_score}\n\n"
            f"<i>Приготовьтесь к следующему броску!</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🎲 Раунд {round_num + 1}: Бросить кости!", callback_data=f"bankrupt_duel_roll:{user_id}")]
        ])
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        # Финал
        outcome = payload["final_outcome"]
        if outcome == "victory":
            text = (
                f"🏆 <b>ТРИУМФ В СУДЕБНОМ ПОЕДИНКЕ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {user_link}: {p_dice}\n"
                f"⚖️ Пристав Лютый: {b_dice}\n\n"
                f"🔥 <b>Итоговый счет:</b> <b>{p_score} : {b_score} в вашу пользу!</b>\n\n"
                f"⚖️ <b>ВЕРДИКТ АРБИТРАЖНОГО СУДА:</b>\n"
                f"За проявленное бесстрашие и волчью доблесть суд постановляет:\n"
                f"✨ <b>СПИСАТЬ 100% ВАШИХ ДОЛГОВ И ПЕНИ!</b>\n"
                f"🛡️ Вам выдан судебный иммунитет от коллекторов на 7 дней.\n"
                f"🕊 Вы абсолютно свободный волк!"
            )
            await callback.message.edit_text(text, parse_mode="HTML")
        else:
            text = (
                f"⚖️ <b>СУДЕБНЫЙ ПОЕДИНОК ЗАВЕРШЕН</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {user_link}: {p_dice}\n"
                f"⚖️ Пристав Лютый: {b_dice}\n\n"
                f"📉 <b>Итоговый счет:</b> {p_score} : {b_score} (победа пристава)\n\n"
                f"Суд проявил волчье снисхождение:\n"
                f"• 📉 <b>Списано 60% вашего долга</b> решением судьи!\n"
                f"• 🧹 На остаток долга вам назначено всего <b>4 исправительные смены</b>.\n"
                f"• 🛡️ Судебный иммунитет от коллекторов продолжает действовать!\n\n"
                f"Выполните смены командой <code>/clean</code>."
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🧹 Выйти на смену (/clean)", callback_data=f"bankrupt_shift:{user_id}")]
            ])
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    await callback.answer()
