"""Модуль доната и внутриигровых покупок."""
import os
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, PreCheckoutQuery

from utils.donation_manager import DonationManager, DONATE_ITEMS
from utils.robokassa_service import create_robokassa_payment, verify_robokassa_payment
from utils.crystalpay_service import create_crystalpay_payment, verify_crystalpay_payment
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

donation_manager = DonationManager()
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "")


def get_donate_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора донат-пакетов."""
    buttons = [
        [
            InlineKeyboardButton(text="💰 500 очков активности - 100₽", callback_data="buy_item:coins_500"),
            InlineKeyboardButton(text="💎 1000 очков активности - 190₽", callback_data="buy_item:coins_1000")
        ],
        [
            InlineKeyboardButton(text="🏆 3000 очков активности - 550₽", callback_data="buy_item:coins_3000")
        ],
        [
            InlineKeyboardButton(text="📈 Ускоритель рейтинга - 90₽", callback_data="buy_item:casino_boost")
        ],
        [
            InlineKeyboardButton(text="🔓 Расширение игрового инвентаря - 150₽", callback_data="buy_item:unlock_slots")
        ],
        [
            InlineKeyboardButton(text="👑 Супер-лайк участника - 300₽", callback_data="buy_item:force_buy_slave")
        ],
        [
            InlineKeyboardButton(text="📜 Пользовательское соглашение и контакты", callback_data="donate_legal")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_donate_text() -> str:
    """Форматирует основной текст донатов."""
    return (
        "💳 <b>Донат Wolf MIREA</b>\n\n"
        "Очки активности используются только внутри бота для рейтингов и игр. "
        "Все покупки разовые.\n\n"
        "📋 <b>Варианты:</b>\n\n"
        "💰 <b>500 очков - 100₽</b>\n"
        "   • Начисление очков для рейтингов и игр.\n\n"
        "💎 <b>1000 очков - 190₽</b>\n"
        "   • Выгодный пакет очков рейтинга.\n\n"
        "🏆 <b>3000 очков - 550₽</b>\n"
        "   • Большой пакет очков рейтинга.\n\n"
        "📈 <b>Ускоритель рейтинга - 90₽</b>\n"
        "   • Повышает скорость получения очков активности.\n\n"
        "🔓 <b>Расширение инвентаря - 150₽</b>\n"
        "   • Открывает 100 слотов в игровом инвентаре.\n\n"
        "👑 <b>Супер-лайк участника - 300₽</b>\n"
        "   • Возможность выдать особый статус любому игроку.\n\n"
        "👇 Выберите товар:"
    )


@router.message(Command("start", "старт"))
async def start_command(message: Message, bot: Bot):
    """Обработчик команды /start."""
    if message.chat.type == "private":
        args = message.text.split()
        if len(args) > 1 and args[1] == "donate":
            await message.answer(
                text=format_donate_text(),
                reply_markup=get_donate_keyboard(),
                parse_mode="HTML"
            )
            return

        await message.answer(
            "👋 <b>Привет! Я бот Wolf MIREA!</b>\n\n"
            "🎮 Используйте команду /donate для покупки монет, бустов и уникальных возможностей!",
            parse_mode="HTML"
        )


@router.message(Command("donate", "донат"))
async def donate_command(message: Message, bot: Bot):
    """Обработчик команды /donate."""
    if message.chat.type != "private":
        bot_info = await bot.get_me()
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💬 Открыть донат в ЛС", url=f"https://t.me/{bot_info.username}?start=donate")
        ]])
        await message.reply(
            "💳 <b>Команда /donate работает только в личных сообщениях с ботом!</b>\n\n"
            "Нажмите кнопку ниже, чтобы перейти в диалог с ботом и открыть меню доната.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    await message.answer(
        text=format_donate_text(),
        reply_markup=get_donate_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("buy_item:"))
async def buy_item_callback(callback_query: CallbackQuery, bot: Bot):
    """Обработка выбора донат-товара."""
    user_id = callback_query.from_user.id
    item_id = callback_query.data.split(":")[1]

    if item_id not in DONATE_ITEMS:
        await callback_query.answer("❌ Товар не найден!", show_alert=True)
        return

    item = DONATE_ITEMS[item_id]
    order = donation_manager.create_order(user_id, item_id)
    if not order:
        await callback_query.answer("❌ Ошибка создания заказа!", show_alert=True)
        return

    order_id = order["order_id"]
    price_rub = item["price_rub"]
    title = item["title"]

    # Пробуем через Telegram Invoices если задан токен провайдера
    if PAYMENT_PROVIDER_TOKEN:
        prices = [LabeledPrice(label=title, amount=price_rub * 100)]
        try:
            await bot.send_invoice(
                chat_id=user_id,
                title=title,
                description=item["description"],
                payload=order_id,
                provider_token=PAYMENT_PROVIDER_TOKEN,
                currency="RUB",
                prices=prices,
                start_parameter=f"pay_{order_id}"
            )
            await callback_query.answer()
            return
        except Exception as e:
            logger.warning(f"Failed to send Telegram invoice, falling back to Robokassa: {e}")

    # Интеграция с CrystalPay (СБП, Карты, Электронные кошельки)
    crystal_res = create_crystalpay_payment(order_id, price_rub, title, user_id)
    payment_url = crystal_res.get("payment_url")
    invoice_id = crystal_res.get("invoice_id")

    if invoice_id:
        donation_manager.set_order_invoice_id(order_id, invoice_id)

    # Если CrystalPay вернуть ссылку не смог (например, не заданы ключи), делаем фоллбек на Robokassa
    payment_system_name = "СБП / Карты / CrystalPay"
    if not payment_url:
        robo_res = create_robokassa_payment(order_id, price_rub, title, user_id)
        payment_url = robo_res.get("payment_url")
        payment_system_name = "Robokassa"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💳 Оплатить {price_rub}₽ ({payment_system_name})", url=payment_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_pay:{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_donate_menu")]
    ])

    await callback_query.message.edit_text(
        f"💳 <b>Оформление заказа #{order_id}</b>\n\n"
        f"📦 Товар: {title}\n"
        f"💰 К оплате: {price_rub}₽\n\n"
        f"Нажмите кнопку ниже для оплаты по СБП/Карте, после чего нажмите «Проверить оплату» для получения товара.",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback_query.answer()


@router.callback_query(F.data.startswith("check_pay:"))
async def check_pay_callback(callback_query: CallbackQuery):
    """Проверка статуса оплаты CrystalPay / Robokassa."""
    order_id = callback_query.data.split(":")[1]
    order = donation_manager.get_order(order_id)

    if not order:
        await callback_query.answer("❌ Заказ не найден!", show_alert=True)
        return

    if order.get("status") == "completed":
        await callback_query.answer("✅ Этот заказ уже успешно оплачен и выдан!", show_alert=True)
        return

    # Проверяем статус в CrystalPay если есть invoice_id, иначе Robokassa
    crystalpay_id = order.get("crystalpay_id")
    is_paid = False

    if crystalpay_id:
        is_paid = verify_crystalpay_payment(crystalpay_id)
    
    if not is_paid:
        is_paid = verify_robokassa_payment(order_id)

    if is_paid:
        donation_manager.complete_order(order_id)
        item = DONATE_ITEMS.get(order["item_id"], {})
        item_title = item.get("title", "Товар")

        await callback_query.message.edit_text(
            f"🎉 <b>Успешная оплата!</b>\n\n"
            f"Товар {item_title} зачислен на ваш аккаунт. Приятной игры!",
            parse_mode="HTML"
        )
        await callback_query.answer("✅ Оплата успешно подтверждена!", show_alert=True)
    else:
        await callback_query.answer(
            "⏳ Платеж еще не поступил. Попробуйте проверить через пару секунд после завершения оплаты.",
            show_alert=True
        )


@router.callback_query(F.data == "donate_legal")
async def donate_legal_callback(callback_query: CallbackQuery):
    """Показ оферты и контактной информации."""
    legal_name = os.getenv("DONATION_LEGAL_NAME", "ИП / Самозанятый")
    legal_inn = os.getenv("DONATION_LEGAL_INN", "")
    legal_email = os.getenv("DONATION_LEGAL_EMAIL", "")
    
    text = (
        f"📜 <b>Оферта и контакты</b>\n\n"
        f"<b>Исполнитель:</b> {legal_name}\n"
        f"<b>ИНН:</b> {legal_inn}\n"
        f"<b>Email поддержки:</b> {legal_email}\n\n"
        f"1. Предмет: Приобретение виртуальных игровых очков для Telegram-бота.\n"
        f"2. Порядок оказания услуг: Товар зачисляется на аккаунт в боте сразу после подтверждения транзакции.\n"
        f"3. Возврат: Возврат средств после зачисления товара не осуществляется, так как услуга является немедленно потребляемой цифровой ценностью.\n"
        f"4. Персональные данные: Бот хранит только ваш Telegram ID для привязки игрового баланса."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_donate_menu")]
    ])
    await callback_query.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    await callback_query.answer()


@router.callback_query(F.data == "back_donate_menu")
async def back_donate_menu_callback(callback_query: CallbackQuery):
    """Возврат в главное меню доната."""
    await callback_query.message.edit_text(
        text=format_donate_text(),
        reply_markup=get_donate_keyboard(),
        parse_mode="HTML"
    )
    await callback_query.answer()


# Telegram Native Payments Handlers
@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """Подтверждение готовности платежа для Telegram Payments."""
    order_id = pre_checkout_query.invoice_payload
    order = donation_manager.get_order(order_id)
    if order:
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    else:
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Заказ не найден.")


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Обработка успешной оплаты через Telegram Payments."""
    payment_info = message.successful_payment
    order_id = payment_info.invoice_payload

    order = donation_manager.get_order(order_id)
    if order:
        donation_manager.complete_order(order_id)
        item = DONATE_ITEMS.get(order["item_id"], {})
        item_title = item.get("title", "Товар")

        await message.answer(
            f"🎉 <b>Успешная оплата!</b>\n\n"
            f"Товар {item_title} зачислен на ваш аккаунт. Приятной игры!",
            parse_mode="HTML"
        )
