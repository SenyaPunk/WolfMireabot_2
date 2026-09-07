"""Команды для проведения Специальных Военных Операций (СВО) и управления военнопленными."""
import html
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.army_manager import (
    ArmyManager,
    RANK_CREATOR,
    RANK_MOBILIZED,
    RANK_DEFAULT
)
from utils.war_manager import WarManager
from utils.user_link import get_user_link

router = Router()
logger = logging.getLogger(__name__)

army_manager = ArmyManager()
war_manager = WarManager()


@router.message(Command("svo", "сво", "война", "спецоперация"))
async def start_svo_cmd(message: Message):
    """Объявление Специальной Военной Операции Главкомом."""
    parts = message.text.split()[1:]
    if not parts:
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/сво [Название Армии Противника]</code>\n\n"
            "💡 <i>Пример:</i> <code>/сво Спарта</code>\n"
            "👑 Объявить СВО может только <b>Главнокомандующий</b> армии.\n"
            "⚔️ Убедитесь, что в обеих армиях есть мобилизованные штурмовики (<code>/мобилизация</code>)!",
            parse_mode="HTML"
        )
        return

    target_army_name = " ".join(parts)
    commander_id = message.from_user.id
    chat_id = message.chat.id
    thread_id = getattr(message, "message_thread_id", None)

    success, result_msg, war_data = war_manager.start_war(
        commander_id=commander_id,
        target_army_name=target_army_name,
        chat_id=chat_id,
        thread_id=thread_id
    )

    if not success:
        await message.reply(result_msg, parse_mode="HTML")
        return

    att_name = war_data["attacker_name"]
    def_name = war_data["defender_name"]
    att_cnt = len(war_data["attacker_soldiers"])
    def_cnt = len(war_data["defender_soldiers"])

    announcement = (
        f"🚨 <b>ОБЪЯВЛЕНА СПЕЦИАЛЬНАЯ ВОЕННАЯ ОПЕРАЦИЯ!</b> 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 Главнокомандующий вооружённых сил «<b>{html.escape(att_name)}</b>» отдал приказ о начале СВО "
        f"против армии «<b>{html.escape(def_name)}</b>»!\n\n"
        f"⚔️ <b>Силы на линии соприкосновения:</b>\n"
        f"🔴 Штурмовая группировка «{html.escape(att_name)}»: <b>{att_cnt} бойцов</b>\n"
        f"🔵 Оборонительный рубеж «{html.escape(def_name)}»: <b>{def_cnt} бойцов</b>\n\n"
        f"⏳ <b>Длительность операции:</b> 15 минут активных боевых действий.\n"
        f"🌦️ <b>Погодные условия:</b> {war_data['weather']['name']}\n\n"
        f"🎯 <b>ПРИКАЗЫ ДЛЯ ЛИЧНОГО СОСТАВА:</b>\n"
        f"• <b>Штурмовикам на передке:</b> <code>/штурм</code> (атака врага), <code>/оборона</code> (окопаться)\n"
        f"• <b>Тыловому резерву (рядовым):</b> <code>/медпомощь</code> (лечить раненых), <code>/снабжение</code> (подвоз БК и дронов)\n"
        f"• <b>Главнокомандующим:</b> <code>/приказ [атака|оборона]</code>, <code>/мобилизация [число]</code>, <code>/капитуляция</code>\n\n"
        f"📊 <i>Оперативная сводка фронта:</i> /сводка"
    )

    await message.reply(announcement, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("front", "сводка", "фронт", "сводка_сво"))
async def front_summary_cmd(message: Message):
    """Интерактивная фронтовая сводка текущей СВО."""
    user_id = message.from_user.id
    success, summary_text = war_manager.get_war_summary(user_id)
    await message.reply(summary_text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("assault", "штурм", "атака", "накат"))
async def assault_cmd(message: Message):
    """Штурмовой накат штурмовика."""
    user_id = message.from_user.id
    success, result_msg, war = war_manager.execute_assault(user_id)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("defense", "оборона", "окопаться", "защита"))
async def defense_cmd(message: Message):
    """Переход штурмовика в глухую оборону."""
    user_id = message.from_user.id
    success, result_msg, war = war_manager.execute_defense(user_id)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("heal", "медпомощь", "лечить", "эвакуация"))
async def heal_cmd(message: Message):
    """Оказание медицинской помощи раненому штурмовику тыловым резервом."""
    user_id = message.from_user.id
    parts = message.text.split()[1:]
    target_id = int(parts[0]) if parts and parts[0].isdigit() else None

    success, result_msg, war = war_manager.execute_heal(user_id, target_id)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("resupply", "снабжение", "бк", "дроны"))
async def resupply_cmd(message: Message):
    """Доставка боеприпасов и дронов штурмовикам тыловым резервом."""
    user_id = message.from_user.id
    success, result_msg, war = war_manager.execute_resupply(user_id)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("order", "приказ", "приказ_главкома"))
async def commander_order_cmd(message: Message):
    """Тактический приказ Главкома."""
    parts = message.text.split()[1:]
    if not parts:
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/приказ [атака | оборона]</code>\n\n"
            "• <code>/приказ атака</code> — даёт +40% к урону всех штурмовиков на 60 сек\n"
            "• <code>/приказ оборона</code> — окапывает всех активных штурмовиков в глухую защиту",
            parse_mode="HTML"
        )
        return

    order_type = parts[0].lower()
    commander_id = message.from_user.id
    success, result_msg, war = war_manager.execute_commander_order(commander_id, order_type)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("surrender", "капитуляция", "сдаться"))
async def surrender_cmd(message: Message):
    """Капитуляция армии Главкомом."""
    commander_id = message.from_user.id
    success, result_msg, war = war_manager.execute_surrender(commander_id)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("prisoners", "военнопленные", "пленные"))
async def prisoners_list_cmd(message: Message):
    """Список военнопленных армии."""
    user_id = message.from_user.id
    army_key = army_manager.get_user_army_key(user_id)
    if not army_key:
        await message.reply("❌ Вы не состоите ни в одной армии.", parse_mode="HTML")
        return

    army = army_manager.armies.get(army_key)
    prisoners = army.get("prisoners", [])

    if not prisoners:
        await message.reply(
            f"🕊️ В застенках армии «<b>{html.escape(army['name'])}</b>» сейчас нет военнопленных.\n"
            f"Захватывайте вражеских бойцов во время СВО (<code>/штурм</code>)!",
            parse_mode="HTML"
        )
        return

    lines = [f"⛓️ <b>Военнопленные в застенках «{html.escape(army['name'])}» ({len(prisoners)} чел.):</b>\n"]
    for idx, p in enumerate(prisoners, 1):
        uid = p.get("user_id")
        user_link = get_user_link(uid, p.get("name", "Боец")) if uid else html.escape(p.get("name", "Боец"))
        from_army = p.get("from_army", "Неизвестная армия")
        lines.append(f"{idx}. {user_link} (ID: <code>{uid}</code>) — захвачен из «{html.escape(from_army)}»")

    lines.append("\n💡 <b>Управление:</b>")
    lines.append("• <code>/освободить_пленного [ID]</code> — отпустить пленного (только Главком)")
    lines.append("• <code>/выкуп_пленного [ID] [сумма]</code> — выкупить соратника из чужого плена")

    await message.reply("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("release_prisoner", "освободить_пленного", "отпустить_пленного"))
async def release_prisoner_cmd(message: Message):
    """Освобождение военнопленного Главкомом."""
    commander_id = message.from_user.id
    parts = message.text.split()[1:]
    if not parts or not parts[0].isdigit():
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/освободить_пленного [ID бойца]</code>\n\n"
            "💡 Узнать ID бойцов можно в списке: <code>/военнопленные</code>",
            parse_mode="HTML"
        )
        return

    target_id = int(parts[0])
    success, result_msg, _ = army_manager.release_prisoner(commander_id, target_id)
    await message.reply(result_msg, parse_mode="HTML")


@router.message(Command("ransom_prisoner", "выкуп_пленного", "выкупить_пленного"))
async def ransom_prisoner_cmd(message: Message):
    """Выкуп военнопленного из плена чужой армии."""
    payer_id = message.from_user.id
    parts = message.text.split()[1:]
    if len(parts) < 2 or not parts[0].isdigit():
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/выкуп_пленного [ID бойца] [сумма]</code>\n\n"
            "💡 <i>Пример:</i> <code>/выкуп_пленного 123456789 200</code>\n"
            "💰 Сумма выкупа переводится в казну пленившей армии.",
            parse_mode="HTML"
        )
        return

    target_id = int(parts[0])
    try:
        amount = float(parts[1])
    except ValueError:
        await message.reply("❌ Сумма выкупа должна быть числом!", parse_mode="HTML")
        return

    success, result_msg, _ = army_manager.ransom_prisoner(payer_id, target_id, amount)
    await message.reply(result_msg, parse_mode="HTML")


@router.message(Command("army_bank", "казна", "бюджет_армии"))
async def army_bank_cmd(message: Message):
    """Просмотр казны армии."""
    user_id = message.from_user.id
    army_key = army_manager.get_user_army_key(user_id)
    if not army_key:
        await message.reply("❌ Вы не состоите ни в одной армии.", parse_mode="HTML")
        return

    army = army_manager.armies.get(army_key)
    bank = army.get("bank", 0.0)
    w_stats = army.get("war_stats", {})

    msg = (
        f"🏦 <b>Казна Вооружённых Сил «{html.escape(army['name'])}»</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Баланс казны:</b> <b>{bank:.2f} монет</b>\n\n"
        f"📊 <b>Военная статистика:</b>\n"
        f"⚔️ Побед в СВО: <b>{w_stats.get('wins', 0)}</b>\n"
        f"💀 Поражений: <b>{w_stats.get('losses', 0)}</b>\n"
        f"⛓️ Захвачено пленных: <b>{w_stats.get('captures', 0)}</b>\n"
        f"🏆 Захвачено трофеев: <b>{w_stats.get('total_looted', 0.0):.2f} монет</b>\n\n"
        f"💡 <i>Пополнить казну:</i> <code>/пополнить_казну [сумма]</code>"
    )
    await message.reply(msg, parse_mode="HTML")


@router.message(Command("deposit_bank", "пополнить_казну", "депозит_армия"))
async def deposit_bank_cmd(message: Message):
    """Внесение личных монет в казну армии."""
    user_id = message.from_user.id
    parts = message.text.split()[1:]
    if not parts:
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/пополнить_казну [сумма]</code>\n\n"
            "💡 <i>Пример:</i> <code>/пополнить_казну 100</code>",
            parse_mode="HTML"
        )
        return

    try:
        amount = float(parts[0])
    except ValueError:
        await message.reply("❌ Сумма должна быть числом!", parse_mode="HTML")
        return

    success, result_msg = army_manager.deposit_to_bank(user_id, amount)
    await message.reply(result_msg, parse_mode="HTML")


@router.message(Command("withdraw_bank", "вывести_казну", "снять_казну"))
async def withdraw_bank_cmd(message: Message):
    """Снятие средств из казны армии Главкомом."""
    commander_id = message.from_user.id
    parts = message.text.split()[1:]
    if not parts:
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/вывести_казну [сумма]</code>\n\n"
            "💡 <i>Пример:</i> <code>/вывести_казну 100</code>",
            parse_mode="HTML"
        )
        return

    try:
        amount = float(parts[0])
    except ValueError:
        await message.reply("❌ Сумма должна быть числом!", parse_mode="HTML")
        return

    success, result_msg = army_manager.withdraw_from_bank(commander_id, amount)
    await message.reply(result_msg, parse_mode="HTML")
