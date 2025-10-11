# Main файл. Импорт либ
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv
import os
import importlib
import pkgutil

load_dotenv() 

app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build() 


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