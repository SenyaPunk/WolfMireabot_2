"""Команды для управления деньгами (только для админов)."""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.economy_manager import EconomyManager
from utils.admin_manager import AdminManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
admin_manager = AdminManager()
user_storage = UserStorage()


@router.message(Command("add_money"))
async def add_money_command(message: Message):
    if not admin_manager.is_admin(message.from_user.id):
        await send_error_message(message, "Только администраторы могут использовать эту команду.")
        return
    
    if message.chat.type == "private":
        await send_error_message(message, "Эта команда доступна только в групповых чатах.")
        return
    
    target_user_id = None
    target_name = None
    amount = None
    
    args = message.text.split()
    
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_name = user_storage.get_display_name(target_user_id)
        
        if len(args) > 1:
            try:
                amount = float(args[1])
            except ValueError:
                await send_error_message(message, "Неверный формат суммы. Используйте число.")
                return
        else:
            await send_error_message(message, "Укажите сумму.\nПример: /add_money 100")
            return
    else:
        if len(args) == 2:
            try:
                amount = float(args[1])
                target_user_id = message.from_user.id
                target_name = user_storage.get_display_name(target_user_id)
            except ValueError:
                await send_error_message(message, "Неверный формат суммы. Используйте число.")
                return
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
            
            target_name = user_storage.get_display_name(target_user_id)
            
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
                "• /add_money 100 - добавить себе\n"
                "• /add_money @username 100 - добавить пользователю\n"
                "• Ответить на сообщение: /add_money 100"
            )
            return
    
    if amount <= 0:
        await send_error_message(message, "Сумма должна быть положительной.")
        return
    
    new_balance = economy_manager.add_money(target_user_id, amount)
    user_link = get_user_link(target_user_id)
    
    await message.reply(
        f"✅ Добавлено <b>{amount:.2f}</b> монет пользователю {user_link}\n"
        f"💰 Новый баланс: <b>{new_balance:.2f}</b> монет",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("remove_money"))
async def remove_money_command(message: Message):
    if not admin_manager.is_admin(message.from_user.id):
        await send_error_message(message, "Только администраторы могут использовать эту команду.")
        return
    
    if message.chat.type == "private":
        await send_error_message(message, "Эта команда доступна только в групповых чатах.")
        return
    
    target_user_id = None
    target_name = None
    amount = None
    
    args = message.text.split()
    
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_name = user_storage.get_display_name(target_user_id)
        
        if len(args) > 1:
            try:
                amount = float(args[1])
            except ValueError:
                await send_error_message(message, "Неверный формат суммы. Используйте число.")
                return
        else:
            await send_error_message(message, "Укажите сумму.\nПример: /remove_money 100")
            return
    else:
        if len(args) == 2:
            try:
                amount = float(args[1])
                target_user_id = message.from_user.id
                target_name = user_storage.get_display_name(target_user_id)
            except ValueError:
                await send_error_message(message, "Неверный формат суммы. Используйте число.")
                return
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
            
            target_name = user_storage.get_display_name(target_user_id)
            
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
                "• /remove_money 100 - убрать у себя\n"
                "• /remove_money @username 100 - убрать у пользователя\n"
                "• Ответить на сообщение: /remove_money 100"
            )
            return
    
    if amount <= 0:
        await send_error_message(message, "Сумма должна быть положительной.")
        return
    
    new_balance = economy_manager.remove_money(target_user_id, amount)
    user_link = get_user_link(target_user_id)
    
    await message.reply(
        f"✅ Убрано <b>{amount:.2f}</b> монет у пользователя {user_link}\n"
        f"💰 Новый баланс: <b>{new_balance:.2f}</b> монет",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
