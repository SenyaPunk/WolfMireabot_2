"""Утилита для управления расписанием работы казино."""
from datetime import datetime, timezone, timedelta
from typing import Optional

# Московское время (UTC+3)
MSK_TZ = timezone(timedelta(hours=3))

# Выходные дни казино: Понедельник (0) и Суббота (5)
CASINO_OFF_DAYS = {0, 5}

DAY_NAMES = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}


def get_current_msk_time() -> datetime:
    """Возвращает текущее время по Москве."""
    return datetime.now(MSK_TZ)


def is_casino_weekend(dt: Optional[datetime] = None) -> bool:
    """
    Проверяет, является ли указанное время (или текущее) выходным днем для казино.
    Выходные дни: Понедельник (0) и Суббота (5).
    """
    if dt is None:
        dt = get_current_msk_time()
    return dt.weekday() in CASINO_OFF_DAYS


def get_casino_closed_message(dt: Optional[datetime] = None) -> str:
    """Возвращает подробное сообщение о закрытии казино на выходной."""
    if dt is None:
        dt = get_current_msk_time()
    day_name = DAY_NAMES.get(dt.weekday(), "выходной день")
    
    return (
        "🎰 <b>КАЗИНО ЗАКРЫТО НА ВЫХОДНОЙ!</b> 🛑\n\n"
        f"📅 Сегодня <b>{day_name}</b> — в Волчьем казино официальный выходной день!\n"
        "🎲 Все азартные игры (<b>Покер</b>, <b>Рулетка / Слоты</b>, <b>Блекджек</b>) временно закрыты.\n\n"
        "⏳ <b>График выходных дней:</b> <b>Понедельник</b> и <b>Суббота</b>.\n"
        "🐺 <i>Сделайте паузу от ставок, сберегите баланс и возвращайтесь в рабочие дни!</i>"
    )


def get_casino_closed_alert_text() -> str:
    """Возвращает короткий текст для всплывающего уведомления (CallbackQuery alert)."""
    return "🎰 Сегодня выходной в казино (Пн, Сб)! Игры закрыты до рабочего дня."


def get_casino_status_text(dt: Optional[datetime] = None) -> str:
    """Возвращает общую информацию о статусе и расписании казино."""
    if dt is None:
        dt = get_current_msk_time()
    
    day_name = DAY_NAMES.get(dt.weekday(), "Неизвестно")
    time_str = dt.strftime("%H:%M МСК")
    closed = is_casino_weekend(dt)
    
    status_icon = "🛑" if closed else "🟢"
    status_title = "ЗАКРЫТО (ВЫХОДНОЙ)" if closed else "ОТКРЫТО"
    
    return (
        f"🎰 <b>ВОЛЧЬЕ КАЗИНО — РАСПИСАНИЕ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 <b>Сегодня:</b> {day_name} ({time_str})\n"
        f"Статус: {status_icon} <b>{status_title}</b>\n\n"
        f"🗓 <b>График работы:</b>\n"
        f"• <b>Понедельник:</b> 🛑 <i>Выходной день (игры отключены)</i>\n"
        f"• <b>Вторник — Пятница:</b> 🟢 <i>Рабочие дни</i>\n"
        f"• <b>Суббота:</b> 🛑 <i>Выходной день (игры отключены)</i>\n"
        f"• <b>Воскресенье:</b> 🟢 <i>Рабочий день</i>\n\n"
        f"🎲 <b>Доступные игры в рабочие дни:</b>\n"
        f"• 🃏 /poker, /покер [блайнд] — Техасский Холдем\n"
        f"• 🎰 /roulette, /рулетка, /slots — Игровой автомат «777»\n"
        f"• ♠️ /blackjack, /блекджек — Карточный Блекджек\n"
    )
