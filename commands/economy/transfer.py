"""Команда для перевода денег между пользователями."""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.economy_manager import EconomyManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
user_storage = UserStorage()


@router.message(Command("transfer"))
async def transfer_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "Эта команда доступна только в групповых чатах.")
        return
    
    sender_id = message.from_user.id
    target_user_id = None
    amount = None
    
    args = message.text.split()
    
    # Ответ на сообщение + сумма
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        
        if len(args) > 1:
            try:
                amount = float(args[1])
            except ValueError:
                await send_error_message(message, "Неверный формат суммы. Используйте число.")
                return
        else:
            await send_error_message(
                message,
                "Укажите сумму для перевода.\nПример: /transfer 100"
            )
            return
    # @username + сумма
    elif len(args) >= 3:
        username = args[1].lstrip('@')
        target_user_id = user_storage.get_user_id(username)
        
        if not target_user_id:
            await send_error_message(
                message,
                f"Пользователь @{username} не найден в базе данных.\n"
                "Убедитесь, что пользователь писал сообщения в этом чате."
            )
            return
        
        try:
            amount = float(args[2])
        except ValueError:
            await send_error_message(message, "Неверный формат суммы. Используйте число.")
            return
    else:
        await send_error_message(
            message,
            "Неверный формат команды.\n\n"
            "Примеры использования:\n"
            "• /transfer @username 100 - перевести пользователю\n"
            "• Ответить на сообщение: /transfer 100"
        )
        return
    
    if target_user_id == sender_id:
        await send_error_message(message, "Вы не можете перевести деньги самому себе.")
        return
    
    if amount <= 0:
        await send_error_message(message, "Сумма перевода должна быть положительной.")
        return
    
    sender_balance = economy_manager.get_balance(sender_id)
    if sender_balance < amount:
        sender_link = get_user_link(sender_id)
        await message.reply(
            f"❌ {sender_link}, у вас недостаточно средств для перевода.\n"
            f"💰 Ваш баланс: <b>{sender_balance:.2f}</b> монет\n"
            f"💸 Требуется: <b>{amount:.2f}</b> монет",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return
    
    economy_manager.remove_money(sender_id, amount)
    economy_manager.add_money(target_user_id, amount)
    
    sender_link = get_user_link(sender_id)
    recipient_link = get_user_link(target_user_id)
    
    new_sender_balance = economy_manager.get_balance(sender_id)
    new_recipient_balance = economy_manager.get_balance(target_user_id)
    
    await message.reply(
        f"✅ Перевод выполнен успешно!\n\n"
        f"💸 {sender_link} → {recipient_link}\n"
        f"💰 Сумма: <b>{amount:.2f}</b> монет\n\n"
        f"Новые балансы:\n"
        f"• {sender_link}: <b>{new_sender_balance:.2f}</b> монет\n"
        f"• {recipient_link}: <b>{new_recipient_balance:.2f}</b> монет",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    
    logger.info(f"Перевод: {sender_id} → {target_user_id}, сумма: {amount}")
