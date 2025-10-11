from telegram import Update
from telegram.ext import ContextTypes, CommandHandler 

import logging

logger = logging.getLogger(__name__)

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: 
    if update.message:
        logger.info(f"hello command from {update.effective_user.id}")
        await update.message.reply_text(f'Hello, {update.effective_user.first_name}!')

HANDLERS = [CommandHandler("hello", hello)]
