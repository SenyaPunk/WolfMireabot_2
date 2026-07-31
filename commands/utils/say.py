import os
import logging
import datetime
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("say", "скажи"))
async def say(message: Message):
    text_raw = message.text or message.caption or ""
    args = text_raw.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.reply("❌ Укажите текст. Пример: <code>/say Привет</code>", parse_mode="HTML")
        return

    text = args[1].strip()

    if message.chat.type == "private":
        target_chat_id = os.getenv("TARGET_CHAT_ID") or os.getenv("TARGET_ID")
        if not target_chat_id:
            await message.answer("❌ Ошибка: в файле .env не найден ID целевого чата (TARGET_CHAT_ID / TARGET_ID).")
            return

        try:
            try:
                chat_id = int(target_chat_id)
            except ValueError:
                chat_id = target_chat_id

            await message.bot.send_message(
                chat_id=chat_id,
                text=text
            )

            user_info = f"ID: {message.from_user.id}, Username: @{message.from_user.username or 'None'}, Name: {message.from_user.full_name}"
            logger.info(f"ANON SAY from {user_info}: {text}")

            try:
                os.makedirs("data", exist_ok=True)
                with open("data/anon_messages.log", "a", encoding="utf-8") as f:
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{now}] [SAY] {user_info} -> {text}\n")
            except Exception as log_err:
                logger.error(f"Не удалось записать логи анонимок: {log_err}")

            await message.answer("✅ Сообщение успешно отправлено в целевой чат!")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения в чат {target_chat_id}: {e}")
            await message.answer(f"❌ Не удалось отправить сообщение: {e}")
    else:
        await message.reply(text)
