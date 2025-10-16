"""Команда для отображения топа пользователей."""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.economy_manager import EconomyManager
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()


@router.message(Command("top"))
async def top_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return
    
    top_users = economy_manager.get_top_users(limit=10)
    
    if not top_users:
        await message.reply("📊 Топ пользователей пуст. Никто еще не заработал монеты!")
        return
    
    top_list = []
    for index, (user_id, balance) in enumerate(top_users, start=1):
        user_link = get_user_link(user_id)
        
        # Добавляем медали для топ-3
        if index == 1:
            medal = "🥇"
        elif index == 2:
            medal = "🥈"
        elif index == 3:
            medal = "🥉"
        else:
            medal = f"{index}."
        
        top_list.append(f"{medal} {user_link} — <b>{balance:.2f}</b> монет")
    
    top_text = "\n".join(top_list)
    
    await message.reply(
        f"📊 <b>Топ пользователей по балансу:</b>\n\n{top_text}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
