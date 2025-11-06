from datetime import datetime
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update
import logging

logger = logging.getLogger(__name__)

class IgnoreOldUpdatesMiddleware(BaseMiddleware):
    
    def __init__(self):
        super().__init__()
        self.bot_start_time = int(datetime.now().timestamp())
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        update_time = None
        
        if event.message:
            update_time = event.message.date.timestamp()
        elif event.callback_query:
            update_time = event.callback_query.message.date.timestamp()
        elif event.edited_message:
            update_time = event.edited_message.edit_date.timestamp()
        
        if update_time and update_time < self.bot_start_time:
            logger.debug(f"Ignoring old update from {update_time} (bot started at {self.bot_start_time})")
            return  
        
        return await handler(event, data)
