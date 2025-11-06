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
from middlewares.user_tracking import UserTrackingMiddleware
from middlewares.ignore_old_updates import IgnoreOldUpdatesMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

user_storage = UserStorage()

dp.update.outer_middleware(IgnoreOldUpdatesMiddleware())
dp.update.outer_middleware(UserTrackingMiddleware(user_storage))

# Регистрируем все команды (file manager)
def register_all(package_name="commands"):
    registered_packages = set()
    
    pkg = importlib.import_module(package_name)
    for finder, name, ispkg in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        parent_pkg = '.'.join(name.split('.')[:-1])
        if parent_pkg in registered_packages:
            continue
            
        mod = importlib.import_module(name)
        if hasattr(mod, "router"):
            router = getattr(mod, "router")
            dp.include_router(router)
            if ispkg:
                registered_packages.add(name)

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
