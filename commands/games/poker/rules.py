"""Обработчики правил и комбинаций покера."""
from pathlib import Path
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from utils.poker_assets import generate_poker_chart

router = Router()

RULES_TEXT = (
    "🎰 <b>ПРАВИЛА И ТЕРМИНОЛОГИЯ: ТЕХАССКИЙ ХОЛДЕМ</b>\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"
    "🎯 <b>Цель игры:</b> Собрать сильнейшую комбинацию из 5 карт (используя 2 свои тайные карты на руках + 5 общих на столе) "
    "или заставить соперников сбросить карты блефом!\n\n"
    "🃏 <b>КАРТЫ И МАСТИ (ЧТО ОЗНАЧАЮТ):</b>\n"
    "• ♠ <b>Пики</b> | ♥ <b>Черви</b> | ♦ <b>Бубны</b> | ♣ <b>Крести</b>\n"
    "• <b>A</b> = <b>Туз</b> (самая старшая карта, либо 1 в стрите A-2-3-4-5)\n"
    "• <b>K</b> = <b>Король</b>\n"
    "• <b>Q</b> = <b>Дама</b>\n"
    "• <b>J</b> = <b>Валет</b>\n"
    "• <b>10, 9, 8... 2</b> = числовые карты по убыванию\n\n"
    "🔄 <b>РАУНДЫ РАЗДАЧИ (УЛИЦЫ):</b>\n"
    "1️⃣ <b>Префлоп:</b> Игрокам раздаются по 2 скрытые карты. Автоматически вносятся блайнды (SB и BB). Первый раунд торгов.\n"
    "2️⃣ <b>Флоп:</b> На стол выкладываются первые 3 общие карты. Раунд торгов.\n"
    "3️⃣ <b>Терн:</b> На столе открывается 4-я общая карта. Раунд торгов.\n"
    "4️⃣ <b>Ривер:</b> На столе открывается 5-я финальная карта. Последний раунд ставок.\n"
    "5️⃣ <b>Шоудаун:</b> Вскрытие карт! Оставшиеся игроки показывают руки, банк забирает лучшая комбинация.\n\n"
    "⚡ <b>ДЕЙСТВИЯ И ТЕРМИНЫ:</b>\n"
    "• <b>Банк (Pot):</b> Общая сумма монет на кону, которую заберет победитель.\n"
    "• <b>Стек:</b> Количество ваших доступных монет за покерным столом.\n"
    "• <b>Блайнды (SB / BB):</b> Обязательные начальные ставки (Малый и Большой блайнды) для создания стартового банка.\n"
    "• <b>Чек:</b> Пропустить ход без ставки (доступно, если до вас ставку никто не поднимал).\n"
    "• <b>Колл:</b> Уравнять текущую наибольшую ставку соперника.\n"
    "• <b>Рейз:</b> Повысить текущую ставку, заставляя других доплачивать.\n"
    "• <b>Пас (Фолд):</b> Сбросить карты и выйти из раздачи.\n"
    "• <b>All-in (Ва-банк):</b> Поставить все свои оставшиеся монеты.\n\n"
    "👀 <i>Во время игры нажимайте кнопку <b>«Посмотреть мои карты»</b>, чтобы тайно видеть свои карты во всплывающем окне!</i>"
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
