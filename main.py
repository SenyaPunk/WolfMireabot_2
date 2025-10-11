# Main файл. Импорт либ
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from dotenv import load_dotenv

import os
import pkgutil
import logging
import importlib

load_dotenv() 

app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build() 

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)

# Регестрируем все команды
def register_all(package_name="commands"): 
    pkg = importlib.import_module(package_name)
    for finder, name, ispkg in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."): 
        mod = importlib.import_module(name) 
        if hasattr(mod, "HANDLERS"): 
            for h in getattr(mod, "HANDLERS"): 
                app.add_handler(h)

register_all("commands")
    

app.run_polling()
