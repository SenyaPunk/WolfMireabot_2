"""Утилита для обработки ошибочных сообщений с автоудалением."""
import asyncio
import logging
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)


async def send_error_message(
    message: Message,
    error_text: str,
    delete_delay: int = 5,
    delete_user_message: bool = True
) -> None:
    # Удаляем сообщение пользователя
    if delete_user_message:
        try:
            await message.delete()
        except TelegramBadRequest as e:
            logger.warning(f"Не удалось удалить сообщение пользователя: {e}")
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения пользователя: {e}")
    
    # Отправляем сообщение об ошибке
    try:
        error_msg = await message.answer(error_text, parse_mode="HTML")
        
        # Ждем указанное время и удаляем сообщение об ошибке
        await asyncio.sleep(delete_delay)
        await error_msg.delete()
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось удалить сообщение об ошибке: {e}")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения об ошибке: {e}")
