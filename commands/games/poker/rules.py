"""Обработчики правил и комбинаций покера."""
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from utils.poker_assets import generate_poker_chart

router = Router()

RULES_TEXT = (
    "🃏 <b>Покер (Техасский Холдем)</b>\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"
    "🎯 <b>Суть:</b> Собрать лучшую комбинацию из 5 карт (2 свои тайные + 5 на столе) или выбить всех блефом.\n\n"
    "🎮 <b>Как играть:</b>\n"
    "1. <b>/poker [блайнд]</b> — сбор стола (от 2 до 6 чел). Создатель может начать досрочно.\n"
    "2. <b>Карты:</b> Бот выдает каждому по 2 карты. Жми <b>«👀 Посмотреть мои карты»</b> в любой момент — всплывающее окно покажет их только тебе.\n"
    "3. <b>Ход:</b> Игроки ходят по очереди по часовой стрелке (таймер 60 сек).\n"
    "4. <b>Стол:</b> По ходу кругов ставок открываются карты стола: 3 на флопе, 1 на терне и 1 на ривере.\n"
    "5. <b>Победа:</b> Забирает банк сильнейшая рука на вскрытии, либо тот, кто остался один, если остальные нажали пас.\n\n"
    "⚡ <b>Кнопки и термины:</b>\n"
    "• <b>Банк</b> — монеты на кону.\n"
    "• <b>Стек</b> — твои монеты за столом.\n"
    "• <b>Чек</b> — пропустить ход без доплаты (если до тебя никто не повышал).\n"
    "• <b>Колл</b> — уравнять ставку соперника.\n"
    "• <b>Рейз</b> — поднять ставку выше.\n"
    "• <b>Пас (Фолд)</b> — сбросить карты и выйти из раздачи.\n"
    "• <b>All-in</b> — пойти ва-банк на весь стек.\n\n"
    "🂠 — закрытая карта на столе.\n"
    "💡 Жми кнопку ниже, чтобы открыть шпаргалку комбинаций!"
)


def get_rules_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🃏 Фото комбинаций", callback_data="poker_show_combos_photo"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="poker_rules_close")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("poker_rules", "правила_покера"))
async def poker_rules_command(message: Message):
    """Показывает правила покера."""
    await message.answer(RULES_TEXT, reply_markup=get_rules_keyboard(), parse_mode="HTML")


@router.message(Command("combos", "комбинации", "комбы"))
async def poker_combos_command(message: Message):
    """Отправляет инфографику комбинаций покера."""
    chart_path = Path("data/assets/poker_combinations.png")
    if not chart_path.exists():
        generate_poker_chart(str(chart_path))
    
    photo = FSInputFile(str(chart_path))
    caption = (
        "🏆 <b>Комбинации карт (от старшей к младшей)</b>\n"
        "Памятка для Техасского Холдема!"
    )
    await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")


@router.callback_query(F.data == "poker_show_combos_photo")
async def cb_poker_show_combos_photo(callback: CallbackQuery):
    chart_path = Path("data/assets/poker_combinations.png")
    if not chart_path.exists():
        generate_poker_chart(str(chart_path))
    
    photo = FSInputFile(str(chart_path))
    caption = (
        "🏆 <b>Комбинации карт (от старшей к младшей)</b>\n"
        "Памятка для Техасского Холдема!"
    )
    if callback.message:
        await callback.message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "poker_rules_close")
async def cb_poker_rules_close(callback: CallbackQuery):
    if callback.message:
        try:
            await callback.message.delete()
        except Exception:
            pass
    await callback.answer()
