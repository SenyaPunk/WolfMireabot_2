"""Команды для управления администраторами."""
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from utils.admin_manager import AdminManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link

router = Router()
logger = logging.getLogger(__name__)

admin_manager = AdminManager()
user_storage = UserStorage()

# Добавить админа
@router.message(Command("add_admin"))
async def add_admin_command(message: Message):
    if not admin_manager.is_owner(message.from_user.id):
        await message.reply("❌ Только владелец бота может добавлять администраторов.")
        return
    
    if message.chat.type == "private":
        await message.reply("❌ Эта команда доступна только в групповых чатах.")
        return
    
    target_user_id = None
    target_username = None
    
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            
            if target_user_id:
                target_username = user_storage.get_display_name(target_user_id)
            else:
                await message.reply(
                    f"❌ Пользователь @{username} не найден в базе данных.\n"
                    "Убедитесь, что пользователь писал сообщения в этом чате, "
                    "или используйте команду в ответ на его сообщение."
                )
                return
        else:
            await message.reply(
                "❌ Используйте команду в ответ на сообщение пользователя или укажите @username.\n"
                "Примеры:\n"
                "• Ответьте на сообщение пользователя командой /add_admin\n"
                "• /add_admin @username"
            )
            return
    
    if target_user_id:
        if admin_manager.is_owner(target_user_id):
            await message.reply("ℹ️ Этот пользователь уже является владельцем бота.")
            return
        
        if admin_manager.add_admin(target_user_id):
            await message.reply(f"✅ Пользователь {target_username} добавлен в администраторы.")
        else:
            await message.reply(f"ℹ️ Пользователь {target_username} уже является администратором.")

# удалить админа
@router.message(Command("remove_admin"))
async def remove_admin_command(message: Message):
    if not admin_manager.is_owner(message.from_user.id):
        await message.reply("❌ Только владелец бота может удалять администраторов.")
        return
    
    if message.chat.type == "private":
        await message.reply("❌ Эта команда доступна только в групповых чатах.")
        return
    
    target_user_id = None
    target_username = None
    
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
        target_username = message.reply_to_message.from_user.username or message.reply_to_message.from_user.first_name
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            
            if target_user_id:
                target_username = user_storage.get_display_name(target_user_id)
            else:
                await message.reply(
                    f"❌ Пользователь @{username} не найден в базе данных.\n"
                    "Убедитесь, что пользователь писал сообщения в этом чате, "
                    "или используйте команду в ответ на его сообщение."
                )
                return
        else:
            await message.reply(
                "❌ Используйте команду в ответ на сообщение пользователя или укажите @username.\n"
                "Примеры:\n"
                "• Ответьте на сообщение пользователя командой /remove_admin\n"
                "• /remove_admin @username"
            )
            return
    
    if target_user_id:
        if admin_manager.is_owner(target_user_id):
            await message.reply("❌ Нельзя удалить владельца бота из администраторов.")
            return
        
        if admin_manager.remove_admin(target_user_id):
            await message.reply(f"✅ Пользователь {target_username} удален из администраторов.")
        else:
            await message.reply(f"ℹ️ Пользователь {target_username} не является администратором.")

# список админов 
@router.message(Command("list_admin"))
async def list_admin_command(message: Message):
    if not admin_manager.is_admin(message.from_user.id):
        await message.reply("❌ Только администраторы могут просматривать список администраторов.")
        return
    
    if message.chat.type == "private":
        await message.reply("❌ Эта команда доступна только в групповых чатах.")
        return
    
    admins = admin_manager.get_admins()
    
    if not admins:
        await message.reply("📋 Список администраторов пуст.")
        return
    
    admin_list = []
    for admin_id in admins:
        user_link = get_user_link(admin_id)
        admin_list.append(f"• {user_link} (ID: {admin_id})")
    
    admin_list_text = "\n".join(admin_list)
    
    owner_link = get_user_link(admin_manager.owner_id) if admin_manager.owner_id else f"ID {admin_manager.owner_id}"
    owner_text = f"👑 Владелец: {owner_link} (ID: {admin_manager.owner_id})\n\n" if admin_manager.owner_id else ""
    
    await message.reply(
        f"📋 <b>Список администраторов:</b>\n\n"
        f"{owner_text}"
        f"{admin_list_text}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
