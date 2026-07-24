from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

@router.message(Command("hello", "привет"))
async def hello(message: Message):
    await message.reply(f'Hello, {message.from_user.first_name}!')
