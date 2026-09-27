"""Команда /casino, /казино для информации о расписании и статусе казино."""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.casino_schedule import get_casino_status_text

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("casino", "казино"))
async def casino_status_command(message: Message):
    """Показывает статус работы казино и расписание выходных дней."""
    text = get_casino_status_text()
    await message.reply(text, parse_mode="HTML")
