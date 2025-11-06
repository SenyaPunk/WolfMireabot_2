from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from typing import Callable, Dict, Any, Awaitable
import logging

logger = logging.getLogger(__name__)

class UserTrackingMiddleware(BaseMiddleware):
    """Middleware для отслеживания пользователей на уровне всех обновлений."""
    
    def __init__(self, user_storage):
        self.user_storage = user_storage
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Update) and event.message:
            message = event.message
            if message.from_user and message.chat.type in ["group", "supergroup"]:
                self.user_storage.add_user(
                    user_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name
                )
                logger.debug(f"Отслежен пользователь: {message.from_user.id} (@{message.from_user.username})")
        
        return await handler(event, data)
