import asyncio
import os
import importlib
import pkgutil
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()

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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
