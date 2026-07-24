"""Команда для проверки баланса."""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
slave_manager = SlaveManager()
user_storage = UserStorage()



# балансик
@router.message(Command("balance", "баланс"))
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
    total_wealth = slave_manager.get_user_price(target_user_id)
    user_link = get_user_link(target_user_id)
    
    owner_id = slave_manager.get_owner(target_user_id)
    slaves = slave_manager.get_slaves_of(target_user_id)
    max_slaves = slave_manager.get_max_slaves(target_user_id)

    status_lines = []
    if owner_id:
        owner_link = get_user_link(owner_id)
        purchase_price = slave_manager.get_purchase_price(target_user_id) or 0.0
        status_lines.append(f"👑 <b>Хозяин:</b> {owner_link} (выкуп: <b>{purchase_price:.2f}</b> монет)")
    else:
        status_lines.append("🕊 <b>Статус:</b> Свободен")

    if slaves:
        status_lines.append(f"⛓️ <b>Рабы:</b> {len(slaves)}/{max_slaves} чел.")

    status_str = "\n".join(status_lines)

    await message.reply(
        f"💰 Баланс {user_link}: <b>{balance:.2f}</b> монет\n"
        f"💎 Стоимость: <b>{total_wealth:.2f}</b> монет\n"
        f"{status_str}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

