"""Обработчики правил и комбинаций покера."""
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from utils.poker_assets import generate_poker_chart

router = Router()

RULES_TEXT = (
    "🎰 <b>ПРАВИЛА: ТЕХАССКИЙ ХОЛДЕМ</b>\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"
    "🎯 <b>Цель:</b> Собрать лучшую 5-карточную комбинацию (из 2 своих тайных карт + 5 общих на столе) "
    "или заставить всех соперников сбросить карты блефом!\n\n"
    "🔄 <b>Улицы и ход раздачи:</b>\n"
    "1️⃣ <b>Префлоп:</b> Каждый получает 2 тайные карты. Блайнды уже в банке. Раунд торговли.\n"
    "2️⃣ <b>Флоп:</b> На стол выкладываются 3 общие карты. Раунд торговли.\n"
    "3️⃣ <b>Терн:</b> На стол кладется 4-я общая карта. Раунд торговли.\n"
    "4️⃣ <b>Ривер:</b> На стол кладется 5-я общая карта. Финальная торговля.\n"
    "5️⃣ <b>Шоудаун:</b> Вскрытие карт оставшихся игроков! Банк забирает сильнейшая рука.\n\n"
    "⚡ <b>Действия игрока:</b>\n"
    "• <b>Чек</b> — пропустить ход, если ставку никто не повышал\n"
    "• <b>Колл</b> — уравнять текущую наивысшую ставку\n"
    "• <b>Рейз</b> — повысить текущую ставку\n"
    "• <b>Пас (Фолд)</b> — сбросить карты и выйти из раздачи\n\n"
    "👀 <i>Во время игры нажимайте кнопку «Мои карты», чтобы тайно смотреть свои карты всплывающим окном!</i>"
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
        "🏆 <b>ИЕРАРХИЯ ПОКЕРНЫХ КОМБИНАЦИЙ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "От высшей (Роял-флеш) к низшей (Старшая карта).\n"
        "Используйте эту памятку во время игры в Холдем!"
    )
    await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")


@router.callback_query(F.data == "poker_show_combos_photo")
async def cb_poker_show_combos_photo(callback: CallbackQuery):
    chart_path = Path("data/assets/poker_combinations.png")
    if not chart_path.exists():
        generate_poker_chart(str(chart_path))
    
    photo = FSInputFile(str(chart_path))
    caption = (
        "🏆 <b>ИЕРАРХИЯ ПОКЕРНЫХ КОМБИНАЦИЙ</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "От высшей (Роял-флеш) к низшей (Старшая карта).\n"
        "Используйте эту памятку во время игры в Холдем!"
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
