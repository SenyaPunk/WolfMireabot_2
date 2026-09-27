"""Middleware для ограничения доступа к азартным играм в выходные дни."""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from utils.casino_schedule import (
    is_casino_weekend,
    get_casino_closed_message,
    get_casino_closed_alert_text,
)

logger = logging.getLogger(__name__)

# Команды, разрешенные даже в выходные (правила, справка, статус казино)
ALLOWED_RULES_COMMANDS = {
    "poker_rules",
    "покер_правила",
    "комбинации_покера",
    "покер_комбинации",
    "casino",
    "казино",
}

# Callback-кнопки, разрешенные в выходные (просмотр правил, закрытие окон)
ALLOWED_CALLBACK_DATA = {
    "poker_show_combos_photo",
}


class CasinoScheduleMiddleware(BaseMiddleware):
    """
    Middleware, блокирующий доступ к азартным играм по понедельникам и субботам.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not is_casino_weekend():
            return await handler(event, data)

        # 1. Обработка входящих команд / сообщений
        if isinstance(event, Message):
            command = data.get("command")
            if command and command.command in ALLOWED_RULES_COMMANDS:
                return await handler(event, data)

            closed_msg = get_casino_closed_message()
            try:
                await event.reply(closed_msg, parse_mode="HTML")
            except Exception:
                try:
                    await event.answer(closed_msg, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление о закрытии казино: {e}")
            return None

        # 2. Обработка нажатий на инлайн-кнопки (CallbackQuery)
        elif isinstance(event, CallbackQuery):
            cb_data = event.data or ""
            # Разрешаем просмотр правил и закрытие сообщений
            if cb_data in ALLOWED_CALLBACK_DATA or cb_data.startswith("rl_close:"):
                return await handler(event, data)

            alert_text = get_casino_closed_alert_text()
            try:
                await event.answer(alert_text, show_alert=True)
            except Exception as e:
                logger.error(f"Не удалось ответить на callback закрытого казино: {e}")
            return None

        return await handler(event, data)
