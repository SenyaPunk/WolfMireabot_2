"""Команды для управления системой приветствий."""
import os
import logging
from typing import Literal
from io import BytesIO

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.fusion_brain import FusionBrainAPI
from utils.text_generator import TextGenerator

router = Router()
logger = logging.getLogger(__name__)

text_gen = TextGenerator()

fusion_api_key = os.getenv('FUSION_API_KEY')
fusion_secret_key = os.getenv('FUSION_SECRET_KEY')

if not fusion_api_key or not fusion_secret_key:
    logger.error("=" * 60)
    logger.error("ОШИБКА: Не найдены ключи Fusion Brain API!")
    logger.error("Создайте файл .env в корне проекта и добавьте:")
    logger.error("FUSION_API_KEY=ваш_ключ")
    logger.error("FUSION_SECRET_KEY=ваш_секретный_ключ")
    logger.error("=" * 60)
    fusion_api = None
else:
    fusion_api = FusionBrainAPI(
        url='https://api-key.fusionbrain.ai/',
        api_key=fusion_api_key,
        secret_key=fusion_secret_key
    )

# Планировщик задач
scheduler = AsyncIOScheduler()

TARGET_CHAT_ID = os.getenv('TARGET_CHAT_ID', '0')

# Получить промпт для генерации изображения.
def get_image_prompt(kind: Literal["morning", "evening"]) -> str:
    if kind == "morning":
        return (
            "Милый пушистый котёнок утром, мягкий тёплый свет, "
            "солнечные лучи, уют, высокое качество, иллюстрация, "
            "детальная шерсть, 4k, warm tones"
        )
    else:
        return (
            "Милый котёнок спокойно спит под пледом, лунный свет из окна, "
            "мягкие тени, уютная атмосфера, высокое качество, "
            "иллюстрация, 4k, night, dreamy"
        )

async def send_greeting_message(bot, kind: Literal["morning", "evening"]):

    if TARGET_CHAT_ID == 0:
        logger.warning("TARGET_CHAT_ID не установлен")
        return

    try:
        logger.info(f"[v0] Генерируем текст для {kind} приветствия...")
        text = text_gen.generate_greeting(kind)
        logger.info(f"[v0] Текст получен: '{text}' (длина: {len(text)} символов)")
        
        if not text or len(text.strip()) == 0:
            logger.error("[v0] Сгенерированный текст пустой!")
            text = "Доброе утро! 🌅" if kind == "morning" else "Спокойной ночи! 🌙"
        
        if len(text) > 1024:
            logger.warning(f"[v0] Текст слишком длинный ({len(text)} символов), обрезаем до 1020")
            text = text[:1020] + "..."
        
        if fusion_api:
            # Генерируем изображение
            logger.info(f"[v0] Генерируем изображение для {kind}...")
            image_prompt = get_image_prompt(kind)
            image_bytes = fusion_api.generate_image_bytes(image_prompt)
            
            if image_bytes:
                logger.info(f"[v0] Отправляем фото с caption (длина текста: {len(text)})")
                logger.info(f"[v0] Caption: {text}")
                
                # Отправляем фото с подписью
                photo = BufferedInputFile(image_bytes, filename="greeting.jpg")
                await bot.send_photo(
                    chat_id=TARGET_CHAT_ID,
                    photo=photo,
                    caption=text
                )
                logger.info(f"✅ Отправлено {kind} приветствие в чат {TARGET_CHAT_ID}")
                return
        
        logger.warning(f"[v0] Отправляем только текст без изображения")
        await bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=f"{text}\n\n(Изображение временно недоступно)"
        )
        logger.warning(f"Отправлено {kind} приветствие без изображения")
            
    except Exception as e:
        logger.error(f"Ошибка отправки приветствия: {e}", exc_info=True)

@router.message(Command("preview"))
async def preview_greeting(message: Message):
    args = message.text.split()
    kind = "morning"
    
    if len(args) > 1:
        arg = args[1].lower()
        if arg in ("evening", "night", "вечер", "ночь"):
            kind = "evening"
    
    await message.reply(
        "Готовлю для вас пост... ☕️🐾" if kind == "morning" 
        else "Готовлю уютный вечерний пост... 🌙🐾"
    )
    
    try:
        logger.info(f"[v0] Preview: генерируем текст для {kind}")
        text = text_gen.generate_greeting(kind)
        logger.info(f"[v0] Preview: текст получен - '{text}' (длина: {len(text)})")
        
        if not text or len(text.strip()) == 0:
            logger.error("[v0] Preview: текст пустой!")
            text = "Доброе утро! 🌅" if kind == "morning" else "Спокойной ночи! 🌙"
        
        if len(text) > 1024:
            logger.warning(f"[v0] Preview: текст слишком длинный, обрезаем")
            text = text[:1020] + "..."
        
        if fusion_api:
            logger.info(f"[v0] Preview: генерируем изображение")
            image_prompt = get_image_prompt(kind)
            image_bytes = fusion_api.generate_image_bytes(image_prompt)
            
            if image_bytes:
                logger.info(f"[v0] Preview: отправляем фото с caption")
                photo = BufferedInputFile(image_bytes, filename="preview.jpg")
                await message.answer_photo(photo=photo, caption=text)
                logger.info(f"[v0] Preview: успешно отправлено")
                return
        
        logger.warning(f"[v0] Preview: отправляем только текст")
        await message.answer(
            f"{text}\n\n(Изображение временно недоступно)\n\n"
            f"💡 Настройте FUSION_API_KEY и FUSION_SECRET_KEY в .env файле"
        )
    except Exception as e:
        logger.error(f"Ошибка предпросмотра: {e}", exc_info=True)
        await message.answer("Не удалось создать превью, попробуйте позже.")

@router.message(Command("schedule"))
async def show_schedule(message: Message):
    morning_time = os.getenv('MORNING_TIME', '08:00')
    evening_time = os.getenv('EVENING_TIME', '22:00')
    
    await message.answer(
        f"📅 <b>Расписание приветствий:</b>\n\n"
        f"🌅 Доброе утро: {morning_time}\n"
        f"🌙 Спокойной ночи: {evening_time}\n\n"
        f"Чат: {TARGET_CHAT_ID}\n\n"
        f"Для изменения расписания отредактируйте переменные окружения "
        f"MORNING_TIME и EVENING_TIME в формате HH:MM",
        parse_mode="HTML"
    )

@router.message(Command("config"))
async def check_config(message: Message):
    status = []
    
    # Проверка токена бота
    bot_token = os.getenv('BOT_TOKEN')
    status.append(f"🤖 BOT_TOKEN: {'✅ Настроен' if bot_token else '❌ Не найден'}")
    
    # Проверка Fusion Brain API
    fusion_key = os.getenv('FUSION_API_KEY')
    fusion_secret = os.getenv('FUSION_SECRET_KEY')
    status.append(f"🎨 FUSION_API_KEY: {'✅ Настроен' if fusion_key else '❌ Не найден'}")
    status.append(f"🔑 FUSION_SECRET_KEY: {'✅ Настроен' if fusion_secret else '❌ Не найден'}")
    
    # Проверка ID чата
    target_chat = os.getenv('TARGET_CHAT_ID', '0')
    status.append(f"💬 TARGET_CHAT_ID: {'✅ ' + target_chat if target_chat != '0' else '❌ Не настроен'}")
    
    # Проверка времени
    morning = os.getenv('MORNING_TIME', '08:00')
    evening = os.getenv('EVENING_TIME', '22:00')
    status.append(f"⏰ MORNING_TIME: {morning}")
    status.append(f"🌙 EVENING_TIME: {evening}")
    
    config_text = "<b>Конфигурация бота:</b>\n\n" + "\n".join(status)
    
    if not fusion_key or not fusion_secret:
        config_text += "\n\n⚠️ <b>Внимание!</b> Fusion Brain API не настроен.\n"
        config_text += "Изображения генерироваться не будут.\n"
        config_text += "Инструкция: см. файл SETUP.md"
    
    if target_chat == '0':
        config_text += "\n\n⚠️ <b>Внимание!</b> TARGET_CHAT_ID не настроен.\n"
        config_text += "Автоматическая отправка не будет работать."
    
    await message.answer(config_text, parse_mode="HTML")

def setup_scheduler(bot):
    morning_time = os.getenv('MORNING_TIME')
    evening_time = os.getenv('EVENING_TIME')
    
    morning_hour, morning_minute = map(int, morning_time.split(':'))
    evening_hour, evening_minute = map(int, evening_time.split(':'))
    
    scheduler.add_job(
        send_greeting_message,
        CronTrigger(hour=morning_hour, minute=morning_minute),
        args=[bot, "morning"],
        id="morning_greeting",
        replace_existing=True
    )
    
    scheduler.add_job(
        send_greeting_message,
        CronTrigger(hour=evening_hour, minute=evening_minute),
        args=[bot, "evening"],
        id="evening_greeting",
        replace_existing=True
    )
    
    logger.info(f"Планировщик настроен: утро - {morning_time}, вечер - {evening_time}")
