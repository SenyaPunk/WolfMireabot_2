"""Команда для проверки баланса."""
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



# балансик
@router.message(Command("balance"))
async def balance_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return
    
    target_user_id = None
    target_name = None
    
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_name = user_storage.get_display_name(target_user_id)
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            
            if target_user_id:
                target_name = user_storage.get_display_name(target_user_id)
            else:
                await send_error_message(message, 
                    f"❌ Пользователь @{username} не найден в базе данных.\n"
                    "Убедитесь, что пользователь писал сообщения в этом чате."
                )
                return
        else:
            target_user_id = message.from_user.id
            target_name = user_storage.get_display_name(target_user_id)
    
    balance = economy_manager.get_balance(target_user_id)
    total_wealth = 1000 + balance + (balance * 0.3)
    user_link = get_user_link(target_user_id)
    
    await message.reply(
        f"💰 Баланс {user_link}: <b>{balance:.2f}</b> монет\n"
        f"💎 Общее состояние: <b>{total_wealth:.2f}</b>",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
