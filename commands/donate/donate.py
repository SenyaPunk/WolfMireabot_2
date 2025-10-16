"""Telegram Api"""
import logging
import os
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from utils.error_handler import send_error_message
from .payment_handler import DonateManager

router = Router()
logger = logging.getLogger(__name__)

YOOMONEY_PROVIDER_TOKEN = os.getenv("YOOMONEY_PROVIDER_TOKEN")

donate_manager = DonateManager()


@router.message(Command("donate"))
async def donate_command(message: Message):
    
    if message.chat.type != "private":
        await send_error_message(message, 
            "❌ Эта команда доступна только в личных сообщениях!\n"
            "Напишите мне в ЛС",
        )
        return
    
    donate_text = (
        "💳 <b>Система донатов</b>\n\n"
        "Поддержите развитие бота и получите бонусы!\n\n"
        "📋 <b>Доступные варианты:</b>\n\n"
        "💰 <b>500 монет</b> - 100₽\n"
        "💎 <b>1000 монет</b> - 190₽ (скидка 5%)\n"
        "🏆 <b>3000 монет</b> - 550₽ (скидка 8%)\n\n"
        "🎰 <b>Буст шансов в блекджеке</b> - 90₽\n"
        "   Увеличивает ваши шансы на победу!\n\n"
        "🔓 <b>Открытие всех слотов рабства</b> - 150₽\n"
        "   Получите доступ ко всем слотам!\n\n"
        "Выберите вариант покупки:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 500 монет - 100₽", callback_data="buy_500")],
        [InlineKeyboardButton(text="💎 1000 монет - 190₽", callback_data="buy_1000")],
        [InlineKeyboardButton(text="🏆 3000 монет - 550₽", callback_data="buy_3000")],
        [InlineKeyboardButton(text="🎰 Буст блекджека - 90₽", callback_data="buy_blackjack_boost")],
        [InlineKeyboardButton(text="🔓 Разблокировка слотов - 150₽", callback_data="buy_slavery_slots")]
    ])
    
    await message.answer(
        donate_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    logger.info(f"Пользователь {message.from_user.id} открыл меню донатов")


@router.callback_query(F.data == "buy_500")
async def callback_buy_500(callback: CallbackQuery):
    await callback.answer()
    await send_invoice_from_callback(callback, "500coins")


@router.callback_query(F.data == "buy_1000")
async def callback_buy_1000(callback: CallbackQuery):
    await callback.answer()
    await send_invoice_from_callback(callback, "1000coins")


@router.callback_query(F.data == "buy_3000")
async def callback_buy_3000(callback: CallbackQuery):
    await callback.answer()
    await send_invoice_from_callback(callback, "3000coins")


@router.callback_query(F.data == "buy_blackjack_boost")
async def callback_buy_blackjack_boost(callback: CallbackQuery):
    await callback.answer()
    await send_invoice_from_callback(callback, "blackjack_boost")


@router.callback_query(F.data == "buy_slavery_slots")
async def callback_buy_slavery_slots(callback: CallbackQuery):
    await callback.answer()
    await send_invoice_from_callback(callback, "slavery_slots")


@router.message(Command("buy_500"))
async def buy_500_coins(message: Message):
    await send_invoice(message, "500coins")


@router.message(Command("buy_1000"))
async def buy_1000_coins(message: Message):
    await send_invoice(message, "1000coins")


@router.message(Command("buy_3000"))
async def buy_3000_coins(message: Message):
    await send_invoice(message, "3000coins")


@router.message(Command("buy_blackjack_boost"))
async def buy_blackjack_boost(message: Message):
    await send_invoice(message, "blackjack_boost")


@router.message(Command("buy_slavery_slots"))
async def buy_slavery_slots(message: Message):
    await send_invoice(message, "slavery_slots")


async def send_invoice(message: Message, donate_type: str):
    donate_info = donate_manager.get_donate_info(donate_type)
    
    if not donate_info:
        await message.answer("❌ Неизвестный тип доната!")
        return
    
    # в копейках
    price_in_kopecks = donate_info["amount"] * 100
    
    prices = [LabeledPrice(label=donate_info["description"], amount=price_in_kopecks)]
    
    await message.answer_invoice(
        title=donate_info["description"],
        description=f"Покупка: {donate_info['description']}. При любых проблемах обращаться к @Senya_Pnk",
        payload=donate_type,
        provider_token=YOOMONEY_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter=f"donate_{donate_type}",
    )
    
    logger.info(f"Отправлен инвойс пользователю {message.from_user.id}: {donate_type}")


async def send_invoice_from_callback(callback: CallbackQuery, donate_type: str):
    donate_info = donate_manager.get_donate_info(donate_type)
    
    if not donate_info:
        await callback.message.answer("❌ Неизвестный тип доната!")
        return
    
    # в копейках
    price_in_kopecks = donate_info["amount"] * 100
    
    prices = [LabeledPrice(label=donate_info["description"], amount=price_in_kopecks)]
    
    await callback.message.answer_invoice(
        title=donate_info["description"],
        description=f"Покупка: {donate_info['description']}",
        payload=donate_type,
        provider_token=YOOMONEY_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter=f"donate_{donate_type}",
    )
    
    logger.info(f"Отправлен инвойс пользователю {callback.from_user.id}: {donate_type}")


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    donate_type = pre_checkout_query.invoice_payload
    
    donate_info = donate_manager.get_donate_info(donate_type)
    
    if not donate_info:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Неизвестный тип доната. Пожалуйста, попробуйте снова."
        )
        logger.error(f"Отклонен платеж: неизвестный тип {donate_type}")
        return
    
    await pre_checkout_query.answer(ok=True)
    logger.info(
        f"Pre-checkout подтвержден для пользователя {pre_checkout_query.from_user.id}: "
        f"{donate_type}"
    )


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    donate_type = payment.invoice_payload
    
    logger.info(
        f"Получен успешный платеж от пользователя {user_id}: "
        f"{donate_type}, сумма: {payment.total_amount / 100} RUB"
    )
    
    result = donate_manager.process_payment(user_id, donate_type)
    
    if result is None:
        await message.answer(
            "❌ Произошла ошибка при обработке платежа!\n"
            "Пожалуйста, обратитесь к администратору."
        )
        logger.error(f"Ошибка обработки платежа для пользователя {user_id}: {donate_type}")
        return
    
    if result["type"] == "coins":
        response = (
            f"✅ <b>Платеж успешно обработан!</b>\n\n"
            f"💰 Зачислено: <b>{result['amount']} монет</b>\n"
            f"💎 Ваш баланс: <b>{result['new_balance']:.2f} монет</b>\n\n"
            f"Спасибо за поддержку! 🎉"
        )
    else:
        response = (
            f"✅ <b>Платеж успешно обработан!</b>\n\n"
            f"🎁 Активировано: <b>{result['description']}</b>\n\n"
            f"Спасибо за поддержку! 🎉"
        )
    
    await message.answer(response, parse_mode="HTML")
    
    logger.info(
        f"Успешно обработан платеж для пользователя {user_id}: "
        f"{donate_type}, результат: {result}"
    )
