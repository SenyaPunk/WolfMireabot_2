"""Команды для управления армиями и войсками."""
import datetime
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.army_manager import ArmyManager, CREATE_ARMY_COST, RANK_CREATOR, RANK_DEFAULT

router = Router()
logger = logging.getLogger(__name__)
army_manager = ArmyManager()


def get_user_display_name(message: Message) -> str:
    user = message.from_user
    if not user:
        return "Неизвестный боец"
    if user.username:
        return f"@{user.username}"
    return user.full_name or user.first_name or f"ID {user.id}"


@router.message(Command("create_army", "создать_армию", "армия_создать"))
async def create_army_cmd(message: Message):
    """Команда для создания собственной армии."""
    parts = message.text.split()[1:]
    
    if len(parts) < 2:
        await message.reply(
            f"⚠️ **Использование:** `/создать_армию [Название] [Численность]`\n\n"
            f"💡 *Пример:* `/создать_армию Спарта 15`\n"
            f"💰 *Стоимость создания:* **{int(CREATE_ARMY_COST)} монет**",
            parse_mode="Markdown"
        )
        return

    if not parts[-1].isdigit():
        await message.reply(
            "❌ Численность армии должна быть целым числом! (Пример: `/создать_армию Спарта 15`)",
            parse_mode="Markdown"
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

    await message.reply(result_msg, parse_mode="Markdown")


@router.message(Command("join_army", "вступить_в_армию", "армия_вступить", "войти_в_армию"))
async def join_army_cmd(message: Message):
    """Команда для вступления в существующую армию."""
    parts = message.text.split()[1:]
    
    if not parts:
        await message.reply(
            "⚠️ **Использование:** `/вступить_в_армию [Название армии]`\n\n"
            "💡 *Пример:* `/вступить_в_армию Спарта`",
            parse_mode="Markdown"
        )
        return

    army_name = " ".join(parts)
    user_name = get_user_display_name(message)

    success, result_msg = army_manager.join_army(
        user_id=message.from_user.id,
        user_name=user_name,
        army_name=army_name
    )

    await message.reply(result_msg, parse_mode="Markdown")


@router.message(Command("my_army", "моя_армия", "армия"))
async def my_army_cmd(message: Message):
    """Информация о собственной армии."""
    user_id = message.from_user.id
    army, member_info = army_manager.get_user_army(user_id)

    if not army or not member_info:
        await message.reply(
            "🪖 **Вы не состоите ни в одной армии.**\n\n"
            f"👑 Вы можете создать свою армию за **{int(CREATE_ARMY_COST)} монет**:\n"
            "• `/создать_армию [Название] [Численность]`\n\n"
            "🎖️ Или вступить в чужую армию:\n"
            "• `/вступить_в_армию [Название]`\n\n"
            "📋 Список всех армий: `/армии`",
            parse_mode="Markdown"
        )
        return

    members = army.get("members", {})
    created_at = army.get("created_at", 0)
    created_date = datetime.datetime.fromtimestamp(created_at).strftime("%d.%m.%Y %H:%M") if created_at else "Неизвестно"
    
    members_list_str = []
    # Сортируем: сначала Главнокомандующий, затем остальной состав
    sorted_m = sorted(members.values(), key=lambda x: (0 if x.get("rank") == RANK_CREATOR else 1, x.get("joined_at", 0)))
    
    for idx, m in enumerate(sorted_m, 1):
        rank = m.get("rank", RANK_DEFAULT)
        name = m.get("name", "Боец")
        icon = "👑" if rank == RANK_CREATOR else "🎖️"
        members_list_str.append(f"{idx}. {icon} **{name}** — _{rank}_")

    members_text = "\n".join(members_list_str)

    msg_text = (
        f"🪖 **Вооружённые Силы «{army['name']}»**\n\n"
        f"👥 **Состав:** {len(members)}/{army['max_members']} чел.\n"
        f"📅 **Основана:** {created_date}\n\n"
        f"🎖️ **Личный состав:**\n{members_text}\n\n"
        f"💡 *Ваше звание:* **{member_info.get('rank', RANK_DEFAULT)}**\n"
        f"🚪 *Покинуть армию:* `/покинуть_армию`"
    )

    if member_info.get("rank") == RANK_CREATOR:
        msg_text += "\n💥 *Расформировать армию:* `/расформировать_армию`"

    await message.reply(msg_text, parse_mode="Markdown")


@router.message(Command("armies", "армии", "список_армий"))
async def list_armies_cmd(message: Message):
    """Список всех созданных армий."""
    armies = army_manager.get_all_armies()

    if not armies:
        await message.reply(
            "🪖 **На данный момент не создано ни одной армии.**\n\n"
            f"Вы можете стать первым и создать армию за **{int(CREATE_ARMY_COST)} монет**:\n"
            "• `/создать_армию [Название] [Численность]`",
            parse_mode="Markdown"
        )
        return

    # Сортируем армии по количеству бойцов
    sorted_armies = sorted(armies, key=lambda a: len(a.get("members", {})), reverse=True)

    lines = ["📋 **Список созданных армий:**\n"]
    for idx, army in enumerate(sorted_armies, 1):
        name = army.get("name", "Безымянная")
        members_cnt = len(army.get("members", {}))
        max_members = army.get("max_members", 10)
        
        # Находим Главнокомандующего
        leader_name = "Неизвестен"
        for m in army.get("members", {}).values():
            if m.get("rank") == RANK_CREATOR:
                leader_name = m.get("name", "Неизвестен")
                break

        status = "🔴 (Заполнена)" if members_cnt >= max_members else f"🟢 ({max_members - members_cnt} мест)"
        lines.append(f"{idx}. 🪖 **{name}** — {members_cnt}/{max_members} чел. {status}\n   👑 Главнокомандующий: {leader_name}")

    lines.append("\n💡 *Вступить в армию:* `/вступить_в_армию [Название]`")

    await message.reply("\n".join(lines), parse_mode="Markdown")


@router.message(Command("leave_army", "покинуть_армию", "выйти_из_армии"))
async def leave_army_cmd(message: Message):
    """Команда для выхода из армии."""
    user_id = message.from_user.id
    success, result_msg = army_manager.leave_army(user_id)
    await message.reply(result_msg, parse_mode="Markdown")


@router.message(Command("disband_army", "расформировать_армию"))
async def disband_army_cmd(message: Message):
    """Команда для расформирования армии Главнокомандующим."""
    user_id = message.from_user.id
    success, result_msg = army_manager.disband_army(user_id)
    await message.reply(result_msg, parse_mode="Markdown")
