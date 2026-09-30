"""Модуль Государственной Казны Волка и интерактивного командного ограбления."""
import asyncio
import html
import logging
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
    User
)

from utils.economy_manager import EconomyManager
from utils.treasury_manager import TreasuryManager
from utils.cooldown_manager import CooldownManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
treasury_manager = TreasuryManager()
cooldown_manager = CooldownManager()
user_storage = UserStorage()

# Константы
HEIST_LOBBY_DURATION = 60      # 60 секунд на сбор банды
HEIST_QTE_TIMEOUT = 14         # 14 секунд на каждый QTE-выбор
USER_HEIST_COOLDOWN = 3600     # 1 час личный кулдаун игрока
TREASURY_HEIST_CD = 900        # 15 минут кулдаун на саму казну после налета бандой
MIN_GANG_MEMBERS = 2
MAX_GANG_MEMBERS = 4


# Пути к графическим ассетам
ASSETS_DIR = Path.cwd() / "data" / "assets"
TREASURY_BANNER_PATH = ASSETS_DIR / "wolf_treasury.jpg"
HEIST_BANNER_PATH = ASSETS_DIR / "wolf_heist.jpg"

# Роли в банде
ROLES_INFO = {
    "hacker": {"title": "Хакер", "emoji": "💻", "desc": "Взлом файрвола и отключение сигнализации"},
    "breacher": {"title": "Подрывник", "emoji": "💣", "desc": "Вскрытие титановой двери сейфа"},
    "gunner": {"title": "Стрелок", "emoji": "🔫", "desc": "Огневое прикрытие и нейтрализация охраны"},
    "driver": {"title": "Водитель", "emoji": "🏎️", "desc": "Скоростной отход и уход от погони"}
}

# Хранилище активных лобби банд: chat_id -> dict
active_gang_lobbies: Dict[int, Dict[str, Any]] = {}
# Множество чатов, где прямо сейчас идет штурм сейфа
active_heists: Set[int] = set()


def format_duration(seconds: float) -> str:
    secs = int(max(0, seconds))
    mins = secs // 60
    s = secs % 60
    if mins > 60:
        h = mins // 60
        m = mins % 60
        return f"{h}ч {m}м"
    return f"{mins}м {s}с"


def get_treasury_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🥷 Ограбить соло", callback_data="tr_solo_choice"),
            InlineKeyboardButton(text="👥 Собрать банду", callback_data="tr_start_gang_lobby")
        ],
        [
            InlineKeyboardButton(text="🏆 Зал славы грабителей", callback_data="tr_hall_of_fame"),
            InlineKeyboardButton(text="📜 История пополнений", callback_data="tr_recent_logs")
        ],
        [
            InlineKeyboardButton(text="💡 Правила налёта", callback_data="tr_rules"),
            InlineKeyboardButton(text="🔄 Обновить", callback_data="tr_refresh_menu")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_treasury_menu_text() -> str:
    stats = treasury_manager.get_stats()
    balance = stats["balance"]
    robbable = stats["robbable"]
    sec_level = stats["security_level"]
    sec_desc = stats["security_desc"]
    cd_rem = stats["cooldown_remaining"]

    status_line = "🟢 <b>Открыта для налётов</b>"
    if cd_rem > 0:
        status_line = f"🚨 <b>РЕЖИМ ЧП! Охрана усилена еще {format_duration(cd_rem)}</b>"

    last_tx_text = "<i>Нет недавних записей</i>"
    if stats["recent_transactions"]:
        last_t = stats["recent_transactions"][-1]
        t_amt = last_t.get("amount", 0.0)
        t_desc = html.escape(str(last_t.get("desc", "")))
        last_tx_text = f"+{t_amt:.2f} монет ({t_desc})"

    fame_text = ""
    if stats["hall_of_fame"]:
        top = stats["hall_of_fame"][0]
        leader_name = html.escape(str(top.get("leader_name", "Бандит")))
        top_amt = top.get("amount", 0.0)
        fame_text = f"\n👑 <b>Рекордный налёт:</b> {leader_name} (вынес <b>{top_amt:.2f}</b> монет)\n"

    return (
        f"🏦 <b>ГОСУДАРСТВЕННАЯ КАЗНА ВОЛКА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>В хранилище:</b> <code>{balance:,.2f}</code> монет\n"
        f"💵 <b>Доступно для куша:</b> <code>{robbable:,.2f}</code> монет\n"
        f"🛡️ <b>Уровень защиты:</b> {sec_level}\n"
        f"🔍 <i>{sec_desc}</i>\n"
        f"🚨 <b>Статус:</b> {status_line}\n"
        f"{fame_text}"
        f"📈 <b>Крайний приток:</b> {last_tx_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Сюда стекаются все проигрыши в казино, займы, пошлины и штрафы бота. "
        f"Соберите банду и сорвите куш до 50% от сейфа!</i>"
    )


# =================================================================
# 1. КОМАНДЫ КАЗНЫ (/treasury, /казна)
# =================================================================

@router.message(Command("treasury", "казна", "сейф"))
async def treasury_command(message: Message):
    text = format_treasury_menu_text()
    kb = get_treasury_keyboard()

    if TREASURY_BANNER_PATH.exists():
        try:
            photo = FSInputFile(str(TREASURY_BANNER_PATH))
            await message.reply_photo(photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception as e:
            logger.warning(f"Не удалось отправить фото казны: {e}")

    await message.reply(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "tr_refresh_menu")
async def callback_refresh_treasury(callback: CallbackQuery):
    text = format_treasury_menu_text()
    kb = get_treasury_keyboard()
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
        await callback.answer("🔄 Данные казны обновлены!")
    except Exception:
        await callback.answer()


@router.callback_query(F.data == "tr_rules")
async def callback_treasury_rules(callback: CallbackQuery):
    rules_text = (
        f"📖 <b>ПРАВИЛА НАЛЁТА НА КАЗНУ ВОЛКА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🥷 <b>Одиночный налёт (Соло):</b>\n"
        f"• Куш: <b>5% – 10%</b> от свободной казны\n"
        f"• Шанс успеха: <b>~12% – 18%</b> (высокий риск!)\n"
        f"• Риск провала: штраф 10% от баланса и 1ч личного розыска\n\n"
        f"👥 <b>Командное ограбление (Банда 2–4 чел):</b>\n"
        f"• Куш: <b>20% – 35%</b> от свободной казны, делится <b>поровну</b> между всеми выжившими!\n"
        f"• Шанс успеха: от <b>25% до 45%</b> (зависит от числа бойцов, уникальности ролей и безошибочного прохождения QTE-фаз)\n"
        f"• Роли: 💻 Хакер, 💣 Подрывник, 🔫 Стрелок, 🏎️ Водитель\n"
        f"• За каждую ошибку в фазах взлома шанс падает на -10%!\n\n"
        f"⚠️ <i>После успешного командного налёта казна переходит на 15-минутный режим ЧП.</i>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к казне", callback_data="tr_refresh_menu")]
    ])
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=rules_text, reply_markup=back_kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=rules_text, reply_markup=back_kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "tr_hall_of_fame")
async def callback_hall_of_fame(callback: CallbackQuery):
    stats = treasury_manager.get_stats()
    fame = stats.get("hall_of_fame", [])

    lines = []
    if not fame:
        lines.append("<i>Пока ни одной банде не удалось вскрыть этот сейф!</i>")
    else:
        for idx, entry in enumerate(fame, 1):
            amt = entry.get("amount", 0.0)
            gang = ", ".join(entry.get("gang_names", []))
            t_str = time.strftime("%d.%m %H:%M", time.localtime(entry.get("time", time.time())))
            badge = "🥇" if idx == 1 else ("🥈" if idx == 2 else ("🥉" if idx == 3 else "▫️"))
            lines.append(f"{badge} <b>{amt:,.2f} монет</b> — {gang} (<i>{t_str}</i>)")

    fame_text = (
        f"🏆 <b>ДОСКА СЛАВЫ: ЛЕГЕНДАРНЫЕ НАЛЁТЫ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Всего вынесено за историю: <b>{stats['total_robbed']:,.2f} монет</b>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к казне", callback_data="tr_refresh_menu")]
    ])
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=fame_text, reply_markup=back_kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=fame_text, reply_markup=back_kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "tr_recent_logs")
async def callback_recent_logs(callback: CallbackQuery):
    stats = treasury_manager.get_stats()
    logs = stats.get("recent_transactions", [])

    lines = []
    if not logs:
        lines.append("<i>Транзакций пока нет.</i>")
    else:
        for entry in reversed(logs[-8:]):
            amt = entry.get("amount", 0.0)
            desc = html.escape(str(entry.get("desc", "")))
            sign = "🔴 -" if entry.get("type") == "rob" else "🟢 +"
            lines.append(f"{sign}<b>{amt:.2f}м</b>: {desc}")

    log_text = (
        f"📜 <b>ПОСЛЕДНИЕ ПОСТУПЛЕНИЯ И СПИСАНИЯ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Текущий золотой фонд: <b>{stats['balance']:,.2f} монет</b>"
    )
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к казне", callback_data="tr_refresh_menu")]
    ])
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=log_text, reply_markup=back_kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=log_text, reply_markup=back_kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


# =================================================================
# 2. ОДИНОЧНОЕ ОГРАБЛЕНИЕ (/rob_treasury)
# =================================================================

@router.callback_query(F.data == "tr_solo_choice")
async def callback_solo_choice(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_link = get_user_link(user_id, callback.from_user.first_name)

    # Проверка глобального кулдауна казны
    cd_rem = treasury_manager.get_heist_cooldown_remaining()
    if cd_rem > 0:
        await callback.answer(f"🚨 Казна на карантине! Охрана усилена еще {format_duration(cd_rem)}.", show_alert=True)
        return

    # Проверка личного кулдауна игрока
    u_cd = cooldown_manager.check_cooldown(f"heist_user:{user_id}", USER_HEIST_COOLDOWN)
    if u_cd is not None:
        await callback.answer(f"⏳ Вы еще в розыске! Следующий налёт доступен через {format_duration(u_cd)}.", show_alert=True)
        return

    robbable = treasury_manager.get_robbable_amount()
    if robbable < 100:
        await callback.answer("❌ В казне сейчас недостаточно средств для куша!", show_alert=True)
        return

    solo_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🕳️ Пролезть по вентиляции", callback_data="tr_solo_exec:vent"),
            InlineKeyboardButton(text="💻 Взломать терминал", callback_data="tr_solo_exec:hack")
        ],
        [
            InlineKeyboardButton(text="💥 Заложить шашку на замок", callback_data="tr_solo_exec:c4")
        ],
        [
            InlineKeyboardButton(text="🔙 Отмена", callback_data="tr_refresh_menu")
        ]
    ])

    solo_text = (
        f"🥷 <b>ОДИНОЧНЫЙ НАЛЁТ НА КАЗНУ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Налётчик: {user_link}\n"
        f"💰 Свободный куш: <b>{robbable:,.2f} монет</b>\n"
        f"🎲 Шанс успеха: <b>~12% – 18%</b> (высокий риск!)\n\n"
        f"Выберите способ скрытного проникновения:"
    )
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=solo_text, reply_markup=solo_kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=solo_text, reply_markup=solo_kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("tr_solo_exec:"))
async def callback_solo_exec(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name
    user_link = get_user_link(user_id, user_name)
    method = callback.data.split(":")[1]

    # Проверка личного кулдауна игрока
    u_cd = cooldown_manager.check_cooldown(f"heist_user:{user_id}", USER_HEIST_COOLDOWN)
    if u_cd is not None:
        await callback.answer(f"⏳ Вы еще в розыске ({format_duration(u_cd)})!", show_alert=True)
        return

    # Устанавливаем личный кулдаун пользователю сразу
    cooldown_manager.set_cooldown(f"heist_user:{user_id}")

    robbable = treasury_manager.get_robbable_amount()
    sec_level, _, sec_tier = treasury_manager.get_security_level()

    method_chances = {
        "vent": 0.07,
        "hack": 0.06,
        "c4": 0.08
    }
    base_chance = method_chances.get(method, 0.06) - (sec_tier * 0.01)
    base_chance = max(0.04, min(0.08, base_chance))
    is_success = random.random() < base_chance

    methods_desc = {
        "vent": "пробрался по вентиляционной шахте к главному терминалу",
        "hack": "подключил декер к оптоволокну охраны и запустил эксплойт",
        "c4": "установил бесшумный термит на засов бронедвери"
    }
    action_str = methods_desc.get(method, "попытался проникнуть в сейф")

    if is_success:
        # Успех соло: выносит от 5% до 10% свободной казны
        loot_percent = random.uniform(0.05, 0.10)
        loot_amount = round(robbable * loot_percent, 2)
        stolen = treasury_manager.take_from_treasury(
            loot_amount,
            leader_id=user_id,
            leader_name=user_name,
            gang_names=[user_name]
        )
        economy_manager.add_money(user_id, stolen)
        # Соло налёт НЕ блокирует казну для остальных игроков!

        new_bal = economy_manager.get_balance(user_id)
        res_text = (
            f"🎉 <b>ДЕРЗКИЙ ОДИНОЧНЫЙ НАЛЁТ УВЕНЧАЛСЯ УСПЕХОМ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🥷 Грабитель: {user_link}\n"
            f"🛠️ Метод: {action_str}!\n"
            f"💰 <b>Сорванный куш:</b> <code>+{stolen:,.2f}</code> монет ({int(loot_percent*100)}% от сейфа)\n"
            f"💳 Ваш новый баланс: <b>{new_bal:,.2f} монет</b>\n\n"
            f"🚨 <i>Сигнализация сработала с опозданием! Волк в ярости объявляет план-перехват!</i>"
        )
    else:
        # Провал соло: штраф 10% от баланса игрока
        user_balance = economy_manager.get_balance(user_id)
        fine = round(min(500.0, max(50.0, user_balance * 0.10)), 2)
        if user_balance > 0:
            fine = min(fine, user_balance)
            economy_manager.remove_money(user_id, fine)
            treasury_manager.add_to_treasury(fine, source="heist_fine", description=f"Штраф с пойманного грабителя {user_name}")

        new_bal = economy_manager.get_balance(user_id)
        res_text = (
            f"🚨 <b>ОБЛАВА! НАЛЁТЧИК ПОЙМАН С ПОЛИЧНЫМ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🥷 Неудачник: {user_link}\n"
            f"💥 Охрана сейфа перехватила вас, когда вы {action_str}!\n"
            f"💸 Изъято в пользу казны: <b>-{fine:,.2f} монет</b>\n"
            f"💳 Ваш остаток: <b>{new_bal:,.2f} монет</b>\n"
            f"🔒 <i>Вы объявлены в розыск! Доступ к налётам заблокирован на 1 час.</i>"
        )

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏦 Вернуться к казне", callback_data="tr_refresh_menu")]
    ])
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=res_text, reply_markup=back_kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=res_text, reply_markup=back_kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(res_text, reply_markup=back_kb, parse_mode="HTML")
    await callback.answer()


# =================================================================
# 3. КОМАНДНОЕ ОГРАБЛЕНИЕ БАНДОЙ (/gang_heist)
# =================================================================

def make_gang_lobby_keyboard(chat_id: int, lobby: Dict[str, Any]) -> InlineKeyboardMarkup:
    members = lobby.get("members", {})
    taken_roles = {m["role"] for m in members.values()}

    role_buttons = []
    for r_key, r_info in ROLES_INFO.items():
        if r_key in taken_roles:
            btn_txt = f"🔒 {r_info['title']} (Занято)"
            role_buttons.append(InlineKeyboardButton(text=btn_txt, callback_data=f"tr_gang_busy:{chat_id}"))
        else:
            btn_txt = f"{r_info['emoji']} Стать: {r_info['title']}"
            role_buttons.append(InlineKeyboardButton(text=btn_txt, callback_data=f"tr_gang_join:{r_key}:{chat_id}"))

    # Группируем по 2 в ряд
    rows = [role_buttons[:2], role_buttons[2:]]

    cnt = len(members)
    can_start = cnt >= MIN_GANG_MEMBERS
    start_btn_text = f"🚀 НАЧАТЬ ШТУРМ ({cnt}/{MAX_GANG_MEMBERS})" if can_start else f"⏳ Ожидание бойцов ({cnt}/{MAX_GANG_MEMBERS})"

    action_row = [
        InlineKeyboardButton(text="🚪 Покинуть", callback_data=f"tr_gang_leave:{chat_id}"),
        InlineKeyboardButton(text=start_btn_text, callback_data=f"tr_gang_start:{chat_id}")
    ]
    rows.append(action_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_gang_lobby_text(lobby: Dict[str, Any]) -> str:
    leader_name = lobby["leader_name"]
    members = lobby.get("members", {})
    rem_time = max(0, int(lobby["expires_at"] - time.time()))
    robbable = treasury_manager.get_robbable_amount()

    # Считаем сбалансированный шанс
    cnt = len(members)
    est_chance = min(22, 6 + (cnt * 4))

    roster_lines = []
    for r_key, r_info in ROLES_INFO.items():
        occupant = None
        for uid, m in members.items():
            if m["role"] == r_key:
                occupant = m["name"]
                break
        if occupant:
            roster_lines.append(f"{r_info['emoji']} <b>{r_info['title']}:</b> {occupant} ✅")
        else:
            roster_lines.append(f"{r_info['emoji']} <b>{r_info['title']}:</b> <i>[Свободно...]</i> ❓")

    return (
        f"🚨 <b>СБОР БАНДЫ НА ОГРАБЛЕНИЕ КАЗНЫ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 <b>Главарь налёта:</b> {leader_name}\n"
        f"⏳ <b>До начала штурма:</b> {rem_time} сек\n"
        f"💰 <b>Куш на кону:</b> до <b>{robbable*0.45:,.2f} монет</b>\n"
        f"🎲 <b>Расчетный шанс на успех:</b> ~{est_chance}%\n\n"
        f"<b>Боевой состав ({cnt}/{MAX_GANG_MEMBERS}):</b>\n"
        + "\n".join(roster_lines) +
        f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Занимайте вакантные роли кнопками ниже! Чем слаженнее команда, тем выше шанс вскрыть сейф!</i>"
    )


@router.message(Command("gang_heist", "банда_ограбление", "ограбление_банда", "ограбить_бандой"))
async def gang_heist_command(message: Message, bot: Bot, user: Optional[User] = None):
    if message.chat.type == "private":
        await send_error_message(message, "Командное ограбление доступно только в групповых чатах!")
        return

    actor = user or message.from_user
    if not actor or actor.is_bot:
        return

    chat_id = message.chat.id
    user_id = actor.id
    user_name = actor.first_name or f"ID: {user_id}"

    if chat_id in active_heists:
        await message.reply("⏳ В этом чате прямо сейчас уже идет штурм сейфа!")
        return

    if chat_id in active_gang_lobbies:
        await message.reply("⚠️ В этом чате уже объявлен сбор банды! Присоединяйтесь по кнопкам выше.")
        return

    cd_rem = treasury_manager.get_heist_cooldown_remaining()
    if cd_rem > 0:
        await message.reply(f"🚨 Казна на усиленном карантине! Охрана начеку еще <b>{format_duration(cd_rem)}</b>.")
        return

    u_cd = cooldown_manager.check_cooldown(f"heist_user:{user_id}", USER_HEIST_COOLDOWN)
    if u_cd is not None:
        await message.reply(f"⏳ Вы еще в розыске! Следующий налёт доступен через <b>{format_duration(u_cd)}</b>.")
        return

    robbable = treasury_manager.get_robbable_amount()
    if robbable < 300:
        await message.reply("❌ В казне сейчас слишком мало средств для налёта бандой (минимум 300 монет).")
        return

    # Создаем лобби
    lobby = {
        "chat_id": chat_id,
        "leader_id": user_id,
        "leader_name": user_name,
        "created_at": time.time(),
        "expires_at": time.time() + HEIST_LOBBY_DURATION,
        "message_id": None,
        "members": {
            user_id: {
                "name": user_name,
                "role": "breacher"  # По умолчанию лидер - подрывник
            }
        }
    }
    active_gang_lobbies[chat_id] = lobby

    kb = make_gang_lobby_keyboard(chat_id, lobby)
    text = format_gang_lobby_text(lobby)

    lobby_msg = None
    if HEIST_BANNER_PATH.exists():
        try:
            photo = FSInputFile(str(HEIST_BANNER_PATH))
            lobby_msg = await message.reply_photo(photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Ошибка отправки баннера банды: {e}")

    if not lobby_msg:
        lobby_msg = await message.reply(text, reply_markup=kb, parse_mode="HTML")

    lobby["message_id"] = lobby_msg.message_id

    # Запускаем фоновый таймер лобби
    asyncio.create_task(run_gang_lobby_timer(bot, chat_id, lobby_msg.message_id))


@router.callback_query(F.data == "tr_start_gang_lobby")
async def callback_start_gang_from_menu(callback: CallbackQuery, bot: Bot):
    if callback.message.chat.type == "private":
        await callback.answer("Командное ограбление доступно только в группах!", show_alert=True)
        return
    if callback.from_user.is_bot:
        await callback.answer("Боты не могут грабить казну!", show_alert=True)
        return
    await gang_heist_command(callback.message, bot, user=callback.from_user)
    await callback.answer()


async def run_gang_lobby_timer(bot: Bot, chat_id: int, message_id: int):
    """Фоновый обратный отсчет лобби перед штурмом."""
    for _ in range(HEIST_LOBBY_DURATION // 10):
        await asyncio.sleep(10)
        lobby = active_gang_lobbies.get(chat_id)
        if not lobby or lobby.get("message_id") != message_id:
            return

        text = format_gang_lobby_text(lobby)
        kb = make_gang_lobby_keyboard(chat_id, lobby)
        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=message_id,
                caption=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception:
            pass

    # Время вышло - проверяем готовность
    lobby = active_gang_lobbies.pop(chat_id, None)
    if not lobby:
        return

    members = lobby.get("members", {})
    if len(members) < MIN_GANG_MEMBERS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"⏱️ <b>Время на сбор банды истекло!</b>\nНе набралось минимальное число участников ({MIN_GANG_MEMBERS} бойца). Ограбление отменено.",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    # Запуск интерактивного штурма
    await execute_gang_heist(bot, chat_id, lobby)


@router.callback_query(F.data.startswith("tr_gang_join:"))
async def callback_gang_join(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    role_key = parts[1]
    chat_id = int(parts[2])

    lobby = active_gang_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("❌ Сбор банды уже завершен или отменен!", show_alert=True)
        return

    user_id = callback.from_user.id
    if callback.from_user.is_bot:
        await callback.answer("Боты не могут участвовать в банде!", show_alert=True)
        return
    user_name = callback.from_user.first_name or f"ID: {user_id}"

    u_cd = cooldown_manager.check_cooldown(f"heist_user:{user_id}", USER_HEIST_COOLDOWN)
    if u_cd is not None:
        await callback.answer(f"⏳ Вы еще в розыске! Осталось {format_duration(u_cd)}.", show_alert=True)
        return

    members = lobby["members"]
    if len(members) >= MAX_GANG_MEMBERS and user_id not in members:
        await callback.answer("🚫 В банде уже максимальное количество бойцов (4 человека)!", show_alert=True)
        return

    # Проверяем не занята ли роль
    for uid, m in members.items():
        if m["role"] == role_key and uid != user_id:
            await callback.answer("❌ Эта роль уже занята другим бойцом!", show_alert=True)
            return

    # Записываем участника
    members[user_id] = {
        "name": user_name,
        "role": role_key
    }

    await callback.answer(f"✅ Вы заняли роль: {ROLES_INFO[role_key]['title']}!")

    # Обновляем сообщение
    text = format_gang_lobby_text(lobby)
    kb = make_gang_lobby_keyboard(chat_id, lobby)
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("tr_gang_busy:"))
async def callback_gang_busy(callback: CallbackQuery):
    await callback.answer("Эта роль уже закреплена за другим участником банды!", show_alert=True)


@router.callback_query(F.data.startswith("tr_gang_leave:"))
async def callback_gang_leave(callback: CallbackQuery):
    chat_id = int(callback.data.split(":")[1])
    lobby = active_gang_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("Сбор банды уже не активен.", show_alert=True)
        return

    user_id = callback.from_user.id
    if user_id not in lobby["members"]:
        await callback.answer("Вы не состоите в этой банде!", show_alert=True)
        return

    if user_id == lobby["leader_id"]:
        # Если вышел лидер
        active_gang_lobbies.pop(chat_id, None)
        await callback.answer("Главарь покинул банду. Сбор распущен!", show_alert=True)
        try:
            await callback.message.edit_caption(
                caption="❌ <b>Сбор банды отменен главарем.</b>",
                parse_mode="HTML"
            )
        except Exception:
            pass
        return

    del lobby["members"][user_id]
    await callback.answer("Вы вышли из состава банды.")

    text = format_gang_lobby_text(lobby)
    kb = make_gang_lobby_keyboard(chat_id, lobby)
    try:
        if callback.message.caption:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("tr_gang_start:"))
async def callback_gang_start(callback: CallbackQuery, bot: Bot):
    chat_id = int(callback.data.split(":")[1])
    lobby = active_gang_lobbies.get(chat_id)
    if not lobby:
        await callback.answer("Сбор банды уже не активен!", show_alert=True)
        return

    if callback.from_user.id != lobby["leader_id"]:
        await callback.answer("Только главарь банды может досрочно скомандовать штурм!", show_alert=True)
        return

    if len(lobby["members"]) < MIN_GANG_MEMBERS:
        await callback.answer(f"Для налёта нужно минимум {MIN_GANG_MEMBERS} бойца!", show_alert=True)
        return

    # Забираем из активных лобби
    active_gang_lobbies.pop(chat_id, None)
    await callback.answer("🔥 Штурм начинается!")
    await execute_gang_heist(bot, chat_id, lobby)


# =================================================================
# 4. ИНТЕРАКТИВНЫЙ ШТУРМ СЕЙФА (QTE EVENTS & RESOLUTION)
# =================================================================

# Хранение состояний QTE фаз: (chat_id, step) -> {"correct_choice": str, "chosen_by": set, "success": bool}
qte_phase_state: Dict[str, Dict[str, Any]] = {}


async def execute_gang_heist(bot: Bot, chat_id: int, lobby: Dict[str, Any]):
    """Запускает трехфазный интерактивный командный штурм."""
    active_heists.add(chat_id)
    members = lobby["members"]
    leader_name = lobby["leader_name"]
    leader_id = lobby["leader_id"]

    try:
        # Проставляем личные кулдауны участникам
        for uid in members.keys():
            cooldown_manager.set_cooldown(f"heist_user:{uid}")

        # Стартовое сообщение штурма
        m_list_str = ", ".join([f"<b>{m['name']}</b> ({ROLES_INFO[m['role']]['title']})" for m in members.values()])
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🚨 <b>ВНИМАНИЕ! БАНДА ИДЁТ НА ШТУРМ КАЗНЫ!</b> 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👥 <b>Ударная группа:</b> {m_list_str}\n\n"
                f"<i>Автомобиль с визгом тормозит у бронированного входа. "
                f"Начинается синхронная операция взлома...</i>"
            ),
            parse_mode="HTML"
        )
        await asyncio.sleep(3.5)

        # Бонусные очки за правильные QTE выборы
        qte_successes = 0

        # --- ФАЗА 1: СИСТЕМЫ ЗАЩИТЫ (ХАКЕР) ---
        qte_key_1 = f"{chat_id}:1"
        correct_port = "443"
        qte_phase_state[qte_key_1] = {"correct": correct_port, "solved": False, "solver": None}

        qte_kb_1 = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔌 Порт 8080 (Proxy)", callback_data=f"tr_qte:1:8080:{chat_id}"),
                InlineKeyboardButton(text="🔐 Порт 443 (SSL/Bypass)", callback_data=f"tr_qte:1:443:{chat_id}"),
                InlineKeyboardButton(text="⚡ Порт 22 (SSH/Brute)", callback_data=f"tr_qte:1:22:{chat_id}")
            ]
        ])

        hacker_id = next((uid for uid, m in members.items() if m["role"] == "hacker"), None)
        hacker_hint = f"<i>(Задача для Хакера! Любой боец может подстраховать)</i>" if hacker_id else "<i>(В банде нет хакера! Выбирайте наугад!)</i>"

        msg_qte_1 = await bot.send_message(
            chat_id=chat_id,
            text=(
                f"💻 <b>ФАЗА 1: ВЗЛОМ ФАЕРВОЛА СЕЙФА</b>\n"
                f"Лазерная сигнализация активирована! Запущен протокол перехвата.\n"
                f"{hacker_hint}\n"
                f"⏱️ <i>У вас 12 секунд, чтобы выбрать правильный порт обхода:</i>"
            ),
            reply_markup=qte_kb_1,
            parse_mode="HTML"
        )

        await asyncio.sleep(11)
        st1 = qte_phase_state.pop(qte_key_1, {})
        if st1.get("solved"):
            qte_successes += 1
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ <b>Фаза 1 пройдена!</b> Боец {st1['solver']} отключил камеры и лазеры без звука сирены!",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="⚠️ <b>Ошибка взлома!</b> Сработал резервный датчик вибрации, охрана поднята по тревоге!",
                parse_mode="HTML"
            )

        await asyncio.sleep(3.0)

        # --- ФАЗА 2: ВЗЛОМ ТИТАНОВОГО ЗАМКА (ПОДРЫВНИК) ---
        qte_key_2 = f"{chat_id}:2"
        correct_mode = "thermite"
        qte_phase_state[qte_key_2] = {"correct": correct_mode, "solved": False, "solver": None}

        qte_kb_2 = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔥 Кумулятивный термит", callback_data=f"tr_qte:2:thermite:{chat_id}"),
                InlineKeyboardButton(text="💥 Динамитная связка", callback_data=f"tr_qte:2:c4:{chat_id}"),
                InlineKeyboardButton(text="🪚 Алмазный бур", callback_data=f"tr_qte:2:drill:{chat_id}")
            ]
        ])

        msg_qte_2 = await bot.send_message(
            chat_id=chat_id,
            text=(
                f"💣 <b>ФАЗА 2: ВСКРЫТИЕ БРОНЕДВЕРИ</b>\n"
                f"Перед бандой трехтонная створка из титанового сплава!\n"
                f"<i>(Задача для Подрывника!)</i>\n"
                f"⏱️ <i>Выберите способ быстрого прожига замков:</i>"
            ),
            reply_markup=qte_kb_2,
            parse_mode="HTML"
        )

        await asyncio.sleep(11)
        st2 = qte_phase_state.pop(qte_key_2, {})
        if st2.get("solved"):
            qte_successes += 1
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ <b>Фаза 2 пройдена!</b> {st2['solver']} идеально прожег петли! Дверь рухнула, сейф открыт!",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="⚠️ <b>Задержка!</b> Замок заклинило от перегрева, пришлось выбивать кувалдой!",
                parse_mode="HTML"
            )

        await asyncio.sleep(3.0)

        # --- ФАЗА 3: ОТХОД И ПОГОНЯ (СТРЕЛОК / ВОДИТЕЛЬ) ---
        qte_key_3 = f"{chat_id}:3"
        correct_route = "alley"
        qte_phase_state[qte_key_3] = {"correct": correct_route, "solved": False, "solver": None}

        qte_kb_3 = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🏎️ По встречке через проспект", callback_data=f"tr_qte:3:highway:{chat_id}"),
                InlineKeyboardButton(text="🏙️ Дворами через арки", callback_data=f"tr_qte:3:alley:{chat_id}"),
                InlineKeyboardButton(text="🚇 В подземный тоннель", callback_data=f"tr_qte:3:metro:{chat_id}")
            ]
        ])

        msg_qte_3 = await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🏎️ <b>ФАЗА 3: МЕшки С ЗОЛОТОМ ПОГРУЖЕНЫ! УХОД ОТ ПОГОНИ</b>\n"
                f"Сирены воют со всех сторон! ЧОП «Волк» на хвосте!\n"
                f"<i>(Задача для Водителя и Стрелка!)</i>\n"
                f"⏱️ <i>Куда направляем машину для отрыва:</i>"
            ),
            reply_markup=qte_kb_3,
            parse_mode="HTML"
        )

        await asyncio.sleep(11)
        st3 = qte_phase_state.pop(qte_key_3, {})
        if st3.get("solved"):
            qte_successes += 1
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ <b>Фаза 3 пройдена!</b> {st3['solver']} мастерски скрылся во дворах! Хвост сброшен!",
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="⚠️ <b>Погоня продолжается!</b> Машина зацепила отбойник, копы буквально на бампере!",
                parse_mode="HTML"
            )

        await asyncio.sleep(3.0)

        # --- ИТОГОВЫЙ РАСЧЕТ РЕЗУЛЬТАТА ---
        robbable = treasury_manager.get_robbable_amount()
        _, _, sec_tier = treasury_manager.get_security_level()

        # Сбалансированная вероятность победы банды:
        # База: 10%
        # Бонус за бойцов: +5% за каждого (2-4 бойца = +10%..+20%)
        # Бонус за все 4 уникальные роли: +5%
        # Бонус за правильные QTE: +4% за каждое (3 QTE = +12%)
        # Штраф за ошибки в QTE: -8% за каждую ошибку
        # Штраф за уровень охраны: -4% за каждый тир (тиры 1-4)
        member_cnt = len(members)
        roles_set = {m["role"] for m in members.values()}
        role_diversity_bonus = 0.05 if len(roles_set) == 4 else (0.02 if len(roles_set) == 3 else 0.0)
        failed_qtes = 3 - qte_successes

        calc_chance = (
            0.05
            + (member_cnt * 0.03)
            + (role_diversity_bonus * 0.5)
            + (qte_successes * 0.02)
            - (failed_qtes * 0.06)
            - (sec_tier * 0.03)
        )
        calc_chance = min(0.22, max(0.04, calc_chance))

        is_victory = random.random() < calc_chance

        if is_victory:
            # Успех банды: забирают от 20% до 35% свободной казны
            loot_pct = random.uniform(0.20, 0.35)
            total_loot = round(robbable * loot_pct, 2)
            gang_names = [m["name"] for m in members.values()]

            stolen = treasury_manager.take_from_treasury(
                total_loot,
                leader_id=leader_id,
                leader_name=leader_name,
                gang_names=gang_names
            )
            treasury_manager.set_heist_cooldown(TREASURY_HEIST_CD)

            # Делим поровну
            share_each = round(stolen / member_cnt, 2)
            payout_lines = []
            for uid, m in members.items():
                economy_manager.add_money(uid, share_each)
                u_link = get_user_link(uid, m["name"])
                payout_lines.append(f"• {u_link} ({ROLES_INFO[m['role']]['title']}): <b>+{share_each:,.2f} монет</b>")

            victory_text = (
                f"🏆 💥 <b>ВЕЛИКОЕ ОГРАБЛЕНИЕ СЕЙФА ЗАВЕРШИЛОСЬ ТРИУМФОМ!</b> 💥 🏆\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 <b>Общий сорванный куш:</b> <code>+{stolen:,.2f}</code> монет!\n"
                f"🎯 Доля добычи: <b>{int(loot_pct*100)}%</b> от свободной казны!\n"
                f"🎲 Итоговый шанс банды был: <b>{int(calc_chance*100)}%</b>\n\n"
                f"<b>Распределение добычи поровну:</b>\n"
                + "\n".join(payout_lines) +
                f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👑 <i>Имена грабителей навечно занесены в Зал Славы! "
                f"Казна переходит в режим ЧП на 1 час.</i>"
            )
            await bot.send_message(chat_id=chat_id, text=victory_text, parse_mode="HTML")
        else:
            # Провал банды: облава, штрафы
            fine_lines = []
            for uid, m in members.items():
                bal = economy_manager.get_balance(uid)
                fine = round(min(400.0, max(40.0, bal * 0.10)), 2)
                if bal > 0:
                    fine = min(fine, bal)
                    economy_manager.remove_money(uid, fine)
                    treasury_manager.add_to_treasury(fine, source="gang_fine", description=f"Штраф бандита {m['name']}")
                u_link = get_user_link(uid, m["name"])
                fine_lines.append(f"• {u_link}: штраф <b>-{fine:,.2f}м</b> (в СИЗО на 1ч)")

            defeat_text = (
                f"🚨 💥 <b>ПРОВАЛ ОГРАБЛЕНИЯ! СПЕЦНАЗ ПЕРЕХВАТИЛ БАНДУ!</b> 💥 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Машина банды зажата в клещи броневиками ЧОП «Волк»!\n"
                f"Все участники задержаны и доставлены в отделение.\n\n"
                f"<b>Конфискация средств в пользу Казны:</b>\n"
                + "\n".join(fine_lines) +
                f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔒 <i>Всем участникам наложен статус «В розыске» на 1 час.</i>"
            )
            await bot.send_message(chat_id=chat_id, text=defeat_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка проведения командного ограбления: {e}", exc_info=True)
        await bot.send_message(chat_id=chat_id, text=f"❌ Технический сбой операции: {e}")
    finally:
        active_heists.discard(chat_id)


@router.callback_query(F.data.startswith("tr_qte:"))
async def callback_qte_click(callback: CallbackQuery):
    parts = callback.data.split(":")
    step = parts[1]
    choice = parts[2]
    chat_id = int(parts[3])

    qte_key = f"{chat_id}:{step}"
    st = qte_phase_state.get(qte_key)
    if not st:
        await callback.answer("⏱️ Время этой фазы уже истекло!", show_alert=True)
        return

    user_name = callback.from_user.first_name
    if choice == st.get("correct"):
        st["solved"] = True
        st["solver"] = user_name
        await callback.answer(f"🎯 ИДЕАЛЬНО! {user_name} выбрал(а) верное действие!", show_alert=True)
    else:
        await callback.answer(f"❌ Неверный выбор! Система зафиксировала ошибку!", show_alert=True)


@router.message(Command("reset_heist_cd", "сброс_карантина_казны", "казна_сброс_кд"))
async def reset_heist_cd_cmd(message: Message):
    """Команда для администраторов: мгновенно снять карантин с казны."""
    from utils.admin_manager import AdminManager
    if not AdminManager().is_admin(message.from_user.id):
        return
    treasury_manager.heist_cooldown_until = 0.0
    treasury_manager.save_data()
    await message.reply("✅ <b>Карантин и усиленная охрана казны сброшены!</b>\nКазна снова открыта для налётов.", parse_mode="HTML")

