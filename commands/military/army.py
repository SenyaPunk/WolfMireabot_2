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

    user_rank = member_info.get('rank', RANK_DEFAULT)
    is_pow, captor_key, pow_info = army_manager.is_user_prisoner(user_id)
    
    if is_pow:
        captor_army = army_manager.armies.get(captor_key, {})
        exit_line = f"⛓️ <i>Статус:</i> <b>В плену у армии «{html.escape(captor_army.get('name', 'врага'))}»!</b> (Ожидайте освобождения или выкупа)"
    elif user_rank == RANK_MOBILIZED:
        exit_line = "⚔️ <i>Статус:</i> <b>На передке (самовольный выход запрещён)</b>"
    else:
        exit_line = "🚪 <i>Покинуть армию:</i> /покинуть_армию"

    bank = army.get("bank", 0.0)
    prisoners_cnt = len(army.get("prisoners", []))
    w_stats = army.get("war_stats", {})
    active_war_id = army.get("active_war_id")
    war_status_str = "⚔️ <b>ИДЁТ СВО!</b> (Сводка: /сводка)" if active_war_id else "🕊️ Мирное время"

    msg_text = (
        f"🪖 <b>Вооружённые Силы «{html.escape(army['name'])}»</b>\n\n"
        f"👥 <b>Состав:</b> {len(members)}/{army['max_members']} чел.\n"
        f"⚔️ <b>Штурмовиков на передке:</b> {mobilized_cnt} чел.\n"
        f"🎖️ <b>В тыловом резерве:</b> {privates_cnt} чел.\n"
        f"💰 <b>Казна армии:</b> {bank:.2f} монет (/казна)\n"
        f"⛓️ <b>Военнопленных в застенках:</b> {prisoners_cnt} чел. (/военнопленные)\n"
        f"🚩 <b>Фронтовой статус:</b> {war_status_str}\n"
        f"🏆 <b>Побед в СВО:</b> {w_stats.get('wins', 0)} | 💀 <b>Поражений:</b> {w_stats.get('losses', 0)}\n"
        f"📅 <b>Основана:</b> {created_date}\n\n"
        f"📋 <b>Личный состав:</b>\n{members_text}\n\n"
        f"💡 <i>Ваше звание:</i> <b>{html.escape(user_rank)}</b>\n"
        f"{exit_line}"
    )

    if member_info.get("rank") == RANK_CREATOR:
        msg_text += (
            "\n\n⚙️ <b>Панель Главнокомандующего:</b>\n"
            "• <code>/сво [Армия]</code> — объявить Специальную Военную Операцию\n"
            "• <code>/мобилизация [число]</code> — отправить бойцов на передок\n"
            "• <code>/демобилизация [число|все]</code> — вернуть бойцов в резерв\n"
            "• /казна — управление военным бюджетом\n"
            "• /военнопленные — застенки и пленные\n"
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

    # Если идёт активная СВО — немедленно зачисляем на фронт
    reinforce_note = ""
    if army and army.get("active_war_id"):
        from utils.war_manager import WarManager
        wm = WarManager()
        army_key = army_manager.get_user_army_key(user_id)
        if army_key:
            wm.register_reinforcement(army_key, mobilized_members)
            reinforce_note = "\n🔥 <b>БОЕВОЕ ПОДКРЕПЛЕНИЕ!</b> Новобранцы немедленно развёрнуты на линии соприкосновения текущей СВО!\n"

    recruits_lines = []
    for idx, m in enumerate(mobilized_members, 1):
        mid = m.get("user_id")
        user_link = get_user_link(int(mid)) if mid else html.escape(m.get("name", "Боец").lstrip("@"))
        recruits_lines.append(f"{idx}. ⚔️ {user_link} — <b>отправлен на передок (Штурмовик)</b>")

    recruits_text = "\n".join(recruits_lines)

    response_text = (
        f"🚨 <b>ВНИМАНИЕ! ОБЪЯВЛЕНА МОБИЛИЗАЦИЯ!</b> 🚨\n\n"
        f"👑 Главнокомандующий вооружённых сил «<b>{html.escape(army_name)}</b>» подписал указ о мобилизации <b>{len(mobilized_members)}</b> бойцов на передовую!\n"
        f"{reinforce_note}\n"
        f"🎯 <b>Список мобилизованных штурмовиков:</b>\n"
        f"{recruits_text}\n\n"
        f"🫡 Родина вас не забудет, бойцы! Готовьтесь к предстоящим боевым действиям на СВО!"
    )

    await message.reply(response_text, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("demobilize", "демобилизация", "ротация"))
async def demobilize_cmd(message: Message):
    """Команда для демобилизации бойцов с передовой обратно в резерв."""
    user_id = message.from_user.id
    army, _ = army_manager.get_user_army(user_id)
    if army and army.get("active_war_id"):
        await message.reply(
            "⚔️ <b>Отставить ротацию! Ваша армия сейчас ведёт боевые действия на СВО!</b>\n"
            "Демобилизация штурмовиков во время боя приравнивается к паникёрству. "
            "Дождитесь окончания операции или объявите капитуляцию (<code>/капитуляция</code>).",
            parse_mode="HTML"
        )
        return

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


@router.message(Command("army_help", "армия_помощь", "помощь_армия", "армия_гайд", "гайд_армия", "сво_помощь", "сво_гайд", "руководство_армия"))
async def army_help_cmd(message: Message):
    """Полное подробное руководство по системе Армии и СВО."""
    help_text = (
        "📚 <b>ПОЛНОЕ РУКОВОДСТВО: СИСТЕМА АРМИИ И СВО</b> 🎖️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1️⃣ СОЗДАНИЕ И ВСТУПЛЕНИЕ:</b>\n"
        "• Любой боец может основать Вооружённые Силы за <b>700 монет</b>:\n"
        "  <code>/создать_армию [Название] [Лимит_людей]</code> (от 2 до 1000 чел).\n"
        "• Бойцы без армии могут вступить в ряды:\n"
        "  <code>/вступить_в_армию [Название]</code>\n"
        "• Информация о своей армии: <code>/моя_армия</code>\n"
        "• Список всех созданных армий сервера: <code>/армии</code>\n\n"

        "<b>2️⃣ ИЕРАРХИЯ И ЗВАНИЯ:</b>\n"
        "👑 <b>Главнокомандующий</b> — создатель армии. Управляет мобилизацией, казной, боевыми приказами, объявляет СВО или капитуляцию.\n"
        "⚔️ <b>Штурмовик</b> — мобилизованный боец на передке. Находится на линии соприкосновения. Единственный, кто штурмует вражеские окопы и берет пленных!\n"
        "🎖️ <b>Рядовой (Тыловой резерв)</b> — тыловое обеспечение. Не рискует попасть в плен, обеспечивает полевую медпомощь, подвоз БК и дронов.\n"
        "⛓️ <b>Военнопленный</b> — захваченный враг. Находится в застенках победителя до выкупа или помилования.\n\n"

        "<b>3️⃣ МОБИЛИЗАЦИЯ И РОТАЦИЯ:</b>\n"
        "• Главком переводит рядовых в штурмовики: <code>/мобилизация [число]</code>\n"
        "  <i>(Если СВО уже идёт — бойцы мгновенно прибывают подкреплением на фронт!)</i>\n"
        "• Главком возвращает бойцов в тыл: <code>/демобилизация [число|все]</code>\n"
        "  <i>(Во время активного боя демобилизация заблокирована!)</i>\n\n"

        "<b>4️⃣ СПЕЦИАЛЬНАЯ ВОЕННАЯ ОПЕРАЦИЯ (СВО):</b>\n"
        "• Объявление СВО: <code>/сво [Армия Противника]</code> (только Главком).\n"
        "• Длительность: <b>15 минут</b> в реальном времени.\n"
        "• <b>Действия штурмовиков:</b>\n"
        "  — <code>/штурм</code> (кд 30с) — накат на позиции противника. Наносит урон врагу. Если HP цели падает до 0 — шанс 50% <b>взять в плен прямо на поле боя</b>!\n"
        "  — <code>/оборона</code> (кд 45с) — окопаться на 1.5 мин (-50% входящего урона, защита от пленения).\n"
        "• <b>Действия тыла (рядовых):</b>\n"
        "  — <code>/медпомощь</code> (кд 25с) — перевязать раненого бойца (+35..55 HP), снимает статус ранения.\n"
        "  — <code>/снабжение</code> (кд 45с) — подвезти термобарический БК и FPV-дроны (+30% урона штурмовиков на 90с).\n"
        "• <b>Действия Главкома:</b>\n"
        "  — <code>/приказ атака</code> (+40% урона) или <code>/приказ оборона</code> (все окапываются).\n"
        "  — <code>/капитуляция</code> — признать поражение и спасти оставшихся бойцов.\n\n"

        "<b>5️⃣ «ТУМАН ВОЙНЫ» И БАЛАНСИРОВКА:</b>\n"
        "• 🌦️ <b>Погода:</b> каждые 3 минуты меняются условия (туман, дождь, шквал снижают точность и урон).\n"
        "• 📦 <b>Ленд-лиз:</b> если у одной армии штурмовиков в 1.5+ раза меньше — аутсайдер получает внешнюю гуманитарную помощь (+30 HP всем бойцам) либо партизаны взрывают тыл лидера!\n"
        "• 📡 <b>РЭБ «Красуха»:</b> на 60 секунд глушит связь тыла (нельзя лечить и подвозить БК).\n\n"

        "<b>6️⃣ ВОЕННОПЛЕННЫЕ И КАЗНА:</b>\n"
        "• <code>/казна</code> — просмотр бюджета армии, боевых трофеев и побед.\n"
        "• <code>/пополнить_казну [сумма]</code> — внести монеты в общую казну.\n"
        "• <code>/военнопленные</code> — застенки и список пленённых бойцов противника.\n"
        "• <code>/выкуп_пленного [ID] [сумма]</code> — выкупить бойца из чужого плена (монеты идут в казну захватчиков).\n"
        "• <code>/освободить_пленного [ID]</code> — отпустить пленного на волю (только Главком).\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Следите за фронтом в реальном времени:</i> <code>/сводка</code>"
    )
    await message.reply(help_text, parse_mode="HTML", disable_web_page_preview=True)
