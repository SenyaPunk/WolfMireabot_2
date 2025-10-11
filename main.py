import asyncio
import os
import importlib
import pkgutil
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

from commands.greetings import scheduler, setup_scheduler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()


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
