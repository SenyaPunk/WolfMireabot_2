import asyncio
import os
import importlib
import pkgutil
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram import F
from aiogram.types import Message

from commands.greetings import scheduler, setup_scheduler
from utils.user_storage import UserStorage

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

user_storage = UserStorage()

# Игнор команд в лс 
@dp.message(F.chat.type == "private")
async def handle_private_messages(message: Message):
    if message.text and message.text.startswith('/'):
        command = message.text.split()[0].split('@')[0]
        if command != '/hello':
            return

# Сохранять информацию о пользователях из всех сообщений.
@dp.message()
async def track_users(message: Message):
    if message.from_user:
        user_storage.add_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )

# Регистрируем все команды (file manager)
def register_all(package_name="commands"):
    pkg = importlib.import_module(package_name)
    for finder, name, ispkg in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        mod = importlib.import_module(name)
        if hasattr(mod, "router"):
            router = getattr(mod, "router")
            dp.include_router(router)

register_all("commands")

async def main():
    setup_scheduler(bot)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
