from telegram import Update
from telegram.ext import ContextTypes, CommandHandler 

async def say(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: 
    if update.message:
        logger.info(f"say command from {update.effective_user.id}")
        text = " ".join(context.args) if context.args else "Напиши что-нибудь"
        await update.message.reply_text(text)

HANDLERS = [CommandHandler("say", say)]
