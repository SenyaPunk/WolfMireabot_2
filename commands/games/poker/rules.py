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
    "🎯 <b>Цель игры:</b> Собрать лучшую комбинацию из 5 карт (используя 2 свои тайные карты + 5 общих на столе) "
    "или вынудить всех соперников сбросить карты блефом!\n\n"
    "🎮 <b>КАК ПРОХОДИТ ИГРА В БОТЕ (ХОД ИГРЫ):</b>\n"
    "1️⃣ <b>Сбор стола:</b> Кто-то пишет <code>/poker</code> (или <code>/poker 50</code>). Игроки жмут «Присоединиться». "
    "Создатель может нажать «🚀 Начать игру» сразу (от 2 игроков) или стол запустится сам через 60 сек.\n"
    "2️⃣ <b>Раздача карт:</b> Бот выставляет графический стол. Каждому выдаются 2 секретные карты. Первые двое автоматически вносят блайнды (SB и BB).\n"
    "3️⃣ <b>Ваши тайные карты:</b> Нажимайте кнопку <b>«👀 Посмотреть мои карты»</b> в любой момент — бот покажет их в личном всплывающем окне (другие игроки их НЕ увидят).\n"
    "4️⃣ <b>Очередь хода:</b> Ход идет по кругу по часовой стрелке. На ход дается <b>60 секунд</b>. Бот подсветит кнопки доступных действий: Чек, Колл, Рейз, All-in или Пас.\n"
    "5️⃣ <b>Улицы стола:</b> Когда ставки уравнены, дилер открывает общие карты: <b>Флоп</b> (3 карты) ➔ <b>Тёрн</b> (4-я) ➔ <b>Ривер</b> (5-я финальная). После каждого открытия идет новый раунд ставок.\n"
    "6️⃣ <b>Победа и банк:</b>\n"
    "   • <i>Досрочно (Блеф):</i> Если все оппоненты нажали «Пас», оставшийся игрок сразу забирает весь банк без показа карт!\n"
    "   • <i>Шоудаун (Вскрытие):</i> После ривера оставшиеся игроки вскрывают карты, и бот автоматически отдает банк игроку с сильнейшей комбинацией.\n\n"
    "⚡ <b>ТЕРМИНОЛОГИЯ И КНОПКИ:</b>\n"
    "• <b>Банк (Pot)</b> — общая сумма монет на столе, за которую идет борьба.\n"
    "• <b>Стек</b> — баланс ваших монет за игровым столом.\n"
    "• <b>Блайнды (SB / BB)</b> — обязательные начальные ставки (малый и большой), чтобы в банке сразу были монеты.\n"
    "• <b>Чек (Check)</b> — пропустить ход без ставки и остаться в игре бесплатно (доступен, если перед вами никто не повышал ставку).\n"
    "• <b>Колл (Call)</b> — уравнять чужую ставку (доплатить разницу до наивысшей ставки раунда).\n"
    "• <b>Рейз (Raise)</b> — повысить текущую ставку, заставляя остальных либо доплачивать, либо сдаваться.\n"
    "• <b>Пас / Фолд (Fold)</b> — сбросить карты и выйти из раздачи, чтобы не терять больше монет.\n"
    "• <b>All-in (Ва-банк)</b> — поставить все оставшиеся монеты из стека.\n"
    "• <b>Кикер</b> — старшая карта вне комбинации (решает спор при одинаковых парах/тройках).\n\n"
    "🃏 <b>ОБОЗНАЧЕНИЯ КАРТ:</b>\n"
    "• Масти: ♠ Пики | ♥ Черви | ♦ Бубны | ♣ Крести\n"
    "• Ранги: <b>A</b> (Туз), <b>K</b> (Король), <b>Q</b> (Дама), <b>J</b> (Валет), <b>10...2</b>\n"
    "• <code>🂠</code> — закрытая карта рубашкой вверх (еще не открыта дилером)\n\n"
    "💡 <i>Нажмите кнопку ниже, чтобы открыть шпаргалку по всем комбинациям!</i>"
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
