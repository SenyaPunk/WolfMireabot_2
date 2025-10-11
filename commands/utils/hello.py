from telegram import Update
from telegram.ext import ContextTypes, CommandHandler 

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: 
    await update.message.reply_text(f'Hello, {update.effective_user.first_name}!')

HANDLERS = [CommandHandler("hello", hello)]