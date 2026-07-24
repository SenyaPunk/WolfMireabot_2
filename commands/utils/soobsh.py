"""Команда /сообщ для отправки сообщения в целевой чат из ЛС бота."""
import os
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("msg", "сообщ"))
async def send_target_message(message: Message):
    if message.chat.type != "private":
        await message.reply("Эта команда доступна только в личных сообщениях с ботом.")
        return

    target_chat_id = os.getenv("TARGET_CHAT_ID") or os.getenv("TARGET_ID")
    if not target_chat_id:
        await message.answer("❌ Ошибка: в файле .env не найден ID целевого чата (TARGET_CHAT_ID / TARGET_ID).")
        return

    try:
        try:
            chat_id = int(target_chat_id)
        except ValueError:
            chat_id = target_chat_id

        await message.bot.send_message(
            chat_id=chat_id,
            text="сеню добавить яиц хватит?"
        )
        await message.answer("Сообщение успешно отправлено")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в чат {target_chat_id}: {e}")
        await message.answer(f"❌ Не удалось отправить сообщение: {e}")
