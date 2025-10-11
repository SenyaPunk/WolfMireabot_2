from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("say"))
async def say(message: Message):
    text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "Напиши что-нибудь"
    await message.reply(text)
