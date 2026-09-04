"""Команды для управления армиями и войсками."""
import datetime
import html
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.army_manager import (
    ArmyManager,
    CREATE_ARMY_COST,
    RANK_CREATOR,
    RANK_MOBILIZED,
    RANK_DEFAULT
)
from utils.user_link import get_user_link

router = Router()
logger = logging.getLogger(__name__)
army_manager = ArmyManager()


def get_user_display_name(message: Message) -> str:
    user = message.from_user
    if not user:
        return "Неизвестный боец"
    return user.full_name or user.first_name or f"ID {user.id}"


@router.message(Command("create_army", "создать_армию", "армия_создать"))
async def create_army_cmd(message: Message):
    """Команда для создания собственной армии."""
    parts = message.text.split()[1:]
    
    if len(parts) < 2:
        await message.reply(
            f"⚠️ <b>Использование:</b> <code>/создать_армию [Название] [Численность]</code>\n\n"
            f"💡 <i>Пример:</i> <code>/создать_армию Спарта 15</code>\n"
            f"💰 <i>Стоимость создания:</i> <b>{int(CREATE_ARMY_COST)} монет</b>",
            parse_mode="HTML"
        )
        return

    if not parts[-1].isdigit():
        await message.reply(
            "❌ Численность армии должна быть целым числом! (Пример: <code>/создать_армию Спарта 15</code>)",
            parse_mode="HTML"
        )
        return

    max_members = int(parts[-1])
    army_name = " ".join(parts[:-1])
    creator_name = get_user_display_name(message)

    success, result_msg = army_manager.create_army(
        creator_id=message.from_user.id,
        creator_name=creator_name,
        army_name=army_name,
        max_members=max_members
    )

    await message.reply(result_msg, parse_mode="HTML")


@router.message(Command("join_army", "вступить_в_армию", "армия_вступить", "войти_в_армию"))
async def join_army_cmd(message: Message):
    """Команда для вступления в существующую армию."""
    parts = message.text.split()[1:]
    
    if not parts:
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/вступить_в_армию [Название армии]</code>\n\n"
            "💡 <i>Пример:</i> <code>/вступить_в_армию Спарта</code>",
            parse_mode="HTML"
        )
        return

    army_name = " ".join(parts)
    user_name = get_user_display_name(message)

    success, result_msg = army_manager.join_army(
        user_id=message.from_user.id,
        user_name=user_name,
        army_name=army_name
    )

    await message.reply(result_msg, parse_mode="HTML")


@router.message(Command("my_army", "моя_армия", "армия"))
async def my_army_cmd(message: Message):
    """Информация о собственной армии."""
    user_id = message.from_user.id
    army, member_info = army_manager.get_user_army(user_id)

    if not army or not member_info:
        await message.reply(
            "🪖 <b>Вы не состоите ни в одной армии.</b>\n\n"
            f"👑 Вы можете создать свою армию за <b>{int(CREATE_ARMY_COST)} монет</b>:\n"
            "• <code>/создать_армию [Название] [Численность]</code>\n\n"
            "🎖️ Или вступить в чужую армию:\n"
            "• <code>/вступить_в_армию [Название]</code>\n\n"
            "📋 Список всех армий: /армии",
            parse_mode="HTML"
        )
        return

    members = army.get("members", {})
    created_at = army.get("created_at", 0)
    created_date = datetime.datetime.fromtimestamp(created_at).strftime("%d.%m.%Y %H:%M") if created_at else "Неизвестно"
    
    mobilized_cnt = sum(1 for m in members.values() if m.get("rank") == RANK_MOBILIZED)
    privates_cnt = sum(1 for m in members.values() if m.get("rank") == RANK_DEFAULT)

    members_list_str = []
    # Сортируем: сначала Главнокомандующий (0), затем Штурмовики на передке (1), затем Рядовые (2)
    def rank_sort_order(m):
        r = m.get("rank")
        if r == RANK_CREATOR:
            return 0
        elif r == RANK_MOBILIZED:
            return 1
        return 2

    sorted_m = sorted(members.values(), key=lambda x: (rank_sort_order(x), x.get("joined_at", 0)))
    
    for idx, m in enumerate(sorted_m, 1):
        rank = m.get("rank", RANK_DEFAULT)
        mid = m.get("user_id")
        if mid:
            user_link = get_user_link(int(mid))
        else:
            raw_name = m.get("name", "Боец").lstrip("@")
            user_link = html.escape(raw_name)
            
        if rank == RANK_CREATOR:
            icon = "👑"
        elif rank == RANK_MOBILIZED:
            icon = "⚔️"
        else:
            icon = "🎖️"

        members_list_str.append(f"{idx}. {icon} {user_link} — <i>{html.escape(rank)}</i>")

    members_text = "\n".join(members_list_str)

    msg_text = (
        f"🪖 <b>Вооружённые Силы «{html.escape(army['name'])}»</b>\n\n"
        f"👥 <b>Состав:</b> {len(members)}/{army['max_members']} чел.\n"
        f"⚔️ <b>Штурмовиков на передке:</b> {mobilized_cnt} чел.\n"
        f"🎖️ <b>В тыловом резерве:</b> {privates_cnt} чел.\n"
        f"📅 <b>Основана:</b> {created_date}\n\n"
        f"📋 <b>Личный состав:</b>\n{members_text}\n\n"
        f"💡 <i>Ваше звание:</i> <b>{html.escape(member_info.get('rank', RANK_DEFAULT))}</b>\n"
        f"🚪 <i>Покинуть армию:</i> /покинуть_армию"
    )

    if member_info.get("rank") == RANK_CREATOR:
        msg_text += (
            "\n\n⚙️ <b>Панель Главнокомандующего:</b>\n"
            "• <code>/мобилизация [число]</code> — отправить рядовых на передок\n"
            "• <code>/демобилизация [число|все]</code> — вернуть бойцов в резерв\n"
            "• /расформировать_армию — ликвидировать армию"
        )

    await message.reply(msg_text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("armies", "армии", "список_армий"))
async def list_armies_cmd(message: Message):
    """Список всех созданных армий."""
    armies = army_manager.get_all_armies()

    if not armies:
        await message.reply(
            "🪖 <b>На данный момент не создано ни одной армии.</b>\n\n"
            f"Вы можете стать первым и создать армию за <b>{int(CREATE_ARMY_COST)} монет</b>:\n"
            "• <code>/создать_армию [Название] [Численность]</code>",
            parse_mode="HTML"
        )
        return

    # Сортируем армии по количеству бойцов
    sorted_armies = sorted(armies, key=lambda a: len(a.get("members", {})), reverse=True)

    lines = ["📋 <b>Список созданных армий:</b>\n"]
    for idx, army in enumerate(sorted_armies, 1):
        name = army.get("name", "Безымянная")
        members_cnt = len(army.get("members", {}))
        max_members = army.get("max_members", 10)
        
        # Находим Главнокомандующего
        leader_link = "Неизвестен"
        for m in army.get("members", {}).values():
            if m.get("rank") == RANK_CREATOR:
                uid = m.get("user_id")
                if uid:
                    leader_link = get_user_link(int(uid))
                else:
                    leader_link = html.escape(m.get("name", "Неизвестен").lstrip("@"))
                break

        status = "🔴 (Заполнена)" if members_cnt >= max_members else f"🟢 ({max_members - members_cnt} мест)"
        lines.append(
            f"{idx}. 🪖 <b>{html.escape(name)}</b> — {members_cnt}/{max_members} чел. {status}\n"
            f"   👑 Главнокомандующий: {leader_link}"
        )

    lines.append("\n💡 <i>Вступить в армию:</i> <code>/вступить_в_армию [Название]</code>")

    await message.reply("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("leave_army", "покинуть_армию", "выйти_из_армии"))
async def leave_army_cmd(message: Message):
    """Команда для выхода из армии."""
    user_id = message.from_user.id
    success, result_msg = army_manager.leave_army(user_id)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("disband_army", "расформировать_армию"))
async def disband_army_cmd(message: Message):
    """Команда для расформирования армии Главнокомандующим."""
    user_id = message.from_user.id
    success, result_msg = army_manager.disband_army(user_id)
    await message.reply(result_msg, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("mobilize", "мобилизация", "призыв", "повестка"))
async def mobilize_cmd(message: Message):
    """Команда для объявления мобилизации Главнокомандующим."""
    user_id = message.from_user.id
    parts = message.text.split()[1:]

    if not parts:
        await message.reply(
            "⚠️ <b>Использование:</b> <code>/мобилизация [число_необходимых]</code>\n\n"
            "💡 <i>Пример:</i> <code>/мобилизация 3</code>\n"
            "🎖️ Случайным образом отправляет указанное число рядовых в штурмовики на передок.",
            parse_mode="HTML"
        )
        return

    if not parts[0].isdigit():
        await message.reply(
            "❌ Количество бойцов для мобилизации должно быть целым положительным числом! (Пример: <code>/мобилизация 3</code>)",
            parse_mode="HTML"
        )
        return

    count = int(parts[0])
    success, result_msg, mobilized_members = army_manager.mobilize_members(user_id, count)

    if not success:
        await message.reply(result_msg, parse_mode="HTML")
        return

    army, _ = army_manager.get_user_army(user_id)
    army_name = army["name"] if army else "армии"

    recruits_lines = []
    for idx, m in enumerate(mobilized_members, 1):
        mid = m.get("user_id")
        user_link = get_user_link(int(mid)) if mid else html.escape(m.get("name", "Боец").lstrip("@"))
        recruits_lines.append(f"{idx}. ⚔️ {user_link} — <b>отправлен на передок (Штурмовик)</b>")

    recruits_text = "\n".join(recruits_lines)

    response_text = (
        f"🚨 <b>ВНИМАНИЕ! ОБЪЯВЛЕНА МОБИЛИЗАЦИЯ!</b> 🚨\n\n"
        f"👑 Главнокомандующий вооружённых сил «<b>{html.escape(army_name)}</b>» подписал указ о мобилизации <b>{len(mobilized_members)}</b> бойцов на передовую!\n\n"
        f"🎯 <b>Список мобилизованных штурмовиков:</b>\n"
        f"{recruits_text}\n\n"
        f"🫡 Родина вас не забудет, бойцы! Готовьтесь к предстоящим боевым действиям на СВО!"
    )

    await message.reply(response_text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("demobilize", "демобилизация", "ротация"))
async def demobilize_cmd(message: Message):
    """Команда для демобилизации бойцов с передовой обратно в резерв."""
    user_id = message.from_user.id
    parts = message.text.split()[1:]

    count = None
    if parts:
        if parts[0].lower() in ("все", "all", "всё"):
            count = None
        elif parts[0].isdigit():
            count = int(parts[0])
        else:
            await message.reply(
                "⚠️ <b>Использование:</b> <code>/демобилизация [число | все]</code>\n\n"
                "💡 <i>Пример:</i> <code>/демобилизация 2</code> или <code>/демобилизация все</code>",
                parse_mode="HTML"
            )
            return

    success, result_msg, demobilized_members = army_manager.demobilize_members(user_id, count)

    if not success:
        await message.reply(result_msg, parse_mode="HTML")
        return

    army, _ = army_manager.get_user_army(user_id)
    army_name = army["name"] if army else "армии"

    demob_lines = []
    for idx, m in enumerate(demobilized_members, 1):
        mid = m.get("user_id")
        user_link = get_user_link(int(mid)) if mid else html.escape(m.get("name", "Боец").lstrip("@"))
        demob_lines.append(f"{idx}. 🎖️ {user_link} — возвращён в тыловой резерв (Рядовой)")

    demob_text = "\n".join(demob_lines)

    response_text = (
        f"🔄 <b>Проведена ротация и демобилизация!</b>\n\n"
        f"В армии «<b>{html.escape(army_name)}</b>» <b>{len(demobilized_members)}</b> бойцов возвращены с передовой в резерв:\n\n"
        f"{demob_text}\n\n"
        f"☕ Отдыхайте, бойцы, до следующего приказа Главнокомандующего."
    )

    await message.reply(response_text, parse_mode="HTML", disable_web_page_preview=True)
