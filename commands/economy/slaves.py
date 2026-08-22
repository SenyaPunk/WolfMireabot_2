"""Модуль команд для системы рабства."""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.cooldown_manager import CooldownManager
from utils.user_storage import UserStorage
from utils.user_link import get_user_link
from utils.error_handler import send_error_message

router = Router()
logger = logging.getLogger(__name__)

economy_manager = EconomyManager()
slave_manager = SlaveManager()
cooldown_manager = CooldownManager()
user_storage = UserStorage()


# /buy_slave, /купить_раба, /купить
@router.message(Command("buy_slave", "купить_раба", "купить"))
async def buy_slave_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return

    buyer_id = message.from_user.id
    buyer_link = get_user_link(buyer_id)

    target_user_id = None

    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            if not target_user_id:
                await send_error_message(
                    message,
                    f"❌ Пользователь @{username} не найден в базе данных.\n"
                    "Убедитесь, что пользователь писал сообщения в этом чате."
                )
                return
        else:
            await send_error_message(
                message,
                "💡 <b>Использование команды:</b>\n"
                "• Ответьте на сообщение человека: <code>/купить</code>\n"
                "• Укажите юзернейм: <code>/купить @username</code>"
            )
            return

    if buyer_id == target_user_id:
        await send_error_message(message, "❌ Вы не можете купить самого себя!")
        return

    # 0. Проверка лимита рабов у покупателя
    current_slaves = slave_manager.get_slaves_of(buyer_id)
    max_slaves = slave_manager.get_max_slaves(buyer_id)
    if len(current_slaves) >= max_slaves:
        await send_error_message(
            message,
            f"❌ <b>Достигнут лимит рабов!</b>\n\n"
            f"Вы можете владеть максимум <b>{max_slaves}</b> рабом.\n"
            f"Освободите имеющегося раба, чтобы купить нового!"
        )
        return

    target_link = get_user_link(target_user_id)

    # Проверка наличия VIP-пропуска "Купить любого участника"
    from utils.donation_manager import DonationManager
    donation_mgr = DonationManager()
    has_vip_pass = donation_mgr.get_force_buy_passes(buyer_id) > 0

    if has_vip_pass:
        # Освобождаем от прошлых владельцев если был рабом
        slave_manager.free_slave(target_user_id)
        donation_mgr.use_force_buy_pass(buyer_id)
        slave_manager.buy_slave(target_user_id, buyer_id, 0.0)

        await message.reply(
            f"👑 <b>КОРОЛЕВСКИЙ ПЕРЕХВАТ РАБА (VIP)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>Покупатель:</b> {buyer_link}\n"
            f"⛓️ <b>Захваченный раб:</b> {target_link}\n"
            f"🎟️ <b>Использован предмет:</b> 👑 Купить любого участника\n\n"
            f"💸 <i>Благодаря VIP-пропуску вы забрали этого участника в рабство в обход обычных правил! Теперь 30% всех его доходов перечисляются вам.</i>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    # 1. Проверка: куплен ли уже
    current_owner = slave_manager.get_owner(target_user_id)
    if current_owner is not None:
        owner_link = get_user_link(current_owner)
        await send_error_message(
            message,
            f"❌ Пользователь {target_link} уже куплен!\n"
            f"Его владелец: {owner_link}. Купленного раба нельзя перекупить."
        )
        return

    # 2. Проверка: не пытается ли раб купить своего владельца / вышестоящего
    if slave_manager.is_in_master_chain(buyer_id, target_user_id):
        await send_error_message(
            message,
            f"❌ Вы не можете купить {target_link}, так как вы находитесь в его владении или цепи подчинения!"
        )
        return

    # 3. Расчет цены и проверка баланса покупателя
    price = slave_manager.get_user_price(target_user_id)
    buyer_balance = economy_manager.get_balance(buyer_id)

    if buyer_balance < price:
        await send_error_message(
            message,
            f"❌ <b>Недостаточно средств!</b>\n\n"
            f"Стоимость пользователя {target_link}: <b>{price:.2f}</b> монет.\n"
            f"Ваш баланс: <b>{buyer_balance:.2f}</b> монет."
        )
        return

    # Списываем деньги и оформляем рабство
    economy_manager.remove_money(buyer_id, price)
    slave_manager.buy_slave(target_user_id, buyer_id, price)

    await message.reply(
        f"⛓️ <b>УСПЕШНАЯ ПОКУПКА РАБА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Покупатель:</b> {buyer_link}\n"
        f"⛓️ <b>Новый раб:</b> {target_link}\n"
        f"💰 <b>Цена покупки:</b> {price:.2f} монет\n\n"
        f"💸 <i>Теперь 30% всех доходов {target_link} от работы и казино автоматически перечисляются хозяину!</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# /buyout, /выкупиться
@router.message(Command("buyout", "выкупиться"))
async def buyout_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return

    user_id = message.from_user.id
    user_link = get_user_link(user_id)

    owner_id = slave_manager.get_owner(user_id)
    if owner_id is None:
        await message.reply(
            f"🕊 {user_link}, вы свободный человек и никому не принадлежите!",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    purchase_price = slave_manager.get_purchase_price(user_id) or 1000.0
    user_balance = economy_manager.get_balance(user_id)

    if user_balance < purchase_price:
        await send_error_message(
            message,
            f"❌ <b>Недостаточно монет для выкупа!</b>\n\n"
            f"Цена вашего выкупа: <b>{purchase_price:.2f}</b> монет.\n"
            f"Ваш баланс: <b>{user_balance:.2f}</b> монет."
        )
        return

    # Списываем деньги раба и выжигаем их
    economy_manager.remove_money(user_id, purchase_price)
    slave_manager.free_slave(user_id)

    owner_link = get_user_link(owner_id)

    await message.reply(
        f"🕊 <b>ОСВОБОЖДЕНИЕ ИЗ РАБСТВА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 {user_link} выкупил себя на свободу за <b>{purchase_price:.2f}</b> монет!\n\n"
        f"Бывший владелец {owner_link} больше не получает процент от его заработка.",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# /my_slaves, /рабы, /мои_рабы, /раб
@router.message(Command("my_slaves", "рабы", "мои_рабы", "раб"))
async def my_slaves_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return

    target_user_id = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            if not target_user_id:
                await send_error_message(message, f"❌ Пользователь @{username} не найден.")
                return
        else:
            target_user_id = message.from_user.id

    user_link = get_user_link(target_user_id)
    slaves = slave_manager.get_slaves_of(target_user_id)

    if not slaves:
        await message.reply(
            f"📜 У пользователя {user_link} нет рабов.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    lines = []
    total_revenue = 0.0
    for idx, (slave_id, s_data) in enumerate(slaves, 1):
        s_link = get_user_link(slave_id)
        p_price = s_data.get("purchase_price", 0.0)
        t_earned = s_data.get("total_earned", 0.0)
        total_revenue += t_earned
        lines.append(f"<b>{idx}.</b> {s_link} — куплен за <code>{p_price:.2f}</code> монет (принес: <code>{t_earned:.2f}</code>)")

    slaves_list_text = "\n".join(lines)
    await message.reply(
        f"⛓️ <b>РАБЫ ПОЛЬЗОВАТЕЛЯ {user_link}</b> ({len(slaves)})\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"{slaves_list_text}\n\n"
        f"💰 <b>Всего пассивного дохода:</b> {total_revenue:.2f} монет",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# /my_master, /хозяин, /мой_хозяин
@router.message(Command("my_master", "хозяин", "мой_хозяин"))
async def my_master_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return

    target_user_id = None
    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            if not target_user_id:
                await send_error_message(message, f"❌ Пользователь @{username} не найден.")
                return
        else:
            target_user_id = message.from_user.id

    user_link = get_user_link(target_user_id)
    owner_id = slave_manager.get_owner(target_user_id)

    if owner_id is None:
        await message.reply(
            f"🕊 Пользователь {user_link} не находится в рабстве.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        return

    owner_link = get_user_link(owner_id)
    s_data = slave_manager.get_slave_data(target_user_id) or {}
    purchase_price = s_data.get("purchase_price", 0.0)
    total_earned = s_data.get("total_earned", 0.0)

    await message.reply(
        f"👑 <b>ИНФОРМАЦИЯ О ВЛАДЕЛЬЦЕ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>Раб:</b> {user_link}\n"
        f"👑 <b>Хозяин:</b> {owner_link}\n"
        f"💰 <b>Стоимость выкупа:</b> {purchase_price:.2f} монет\n"
        f"📊 <b>Принесено хозяину:</b> {total_earned:.2f} монет",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# /free_slave, /освободить, /освободить_раба
@router.message(Command("free_slave", "освободить", "освободить_раба"))
async def free_slave_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return

    owner_id = message.from_user.id
    target_user_id = None

    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            if not target_user_id:
                await send_error_message(message, f"❌ Пользователь @{username} не найден.")
                return
        else:
            await send_error_message(
                message,
                "💡 Укажите раба, которого хотите отпустить:\n"
                "• Ответьте на его сообщение командой <code>/освободить</code>\n"
                "• Напишите <code>/освободить @username</code>"
            )
            return

    target_link = get_user_link(target_user_id)
    current_owner = slave_manager.get_owner(target_user_id)

    if current_owner != owner_id:
        await send_error_message(message, f"❌ Пользователь {target_link} не является вашим рабом!")
        return

    slave_manager.free_slave(target_user_id)
    owner_link = get_user_link(owner_id)

    await message.reply(
        f"🕊 {owner_link} благородно даровал свободу {target_link}!",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# /whip, /плетка, /хлестать, /плеть
@router.message(Command("whip", "плетка", "хлестать", "плеть"))
async def whip_command(message: Message):
    if message.chat.type == "private":
        await send_error_message(message, "❌ Эта команда доступна только в групповых чатах.")
        return

    owner_id = message.from_user.id
    owner_link = get_user_link(owner_id)

    # 1. Проверка кулдауна у хозяина (5 часов = 18000 секунд)
    cooldown_key = f"whip_cooldown:{owner_id}"
    remaining = cooldown_manager.check_cooldown(cooldown_key, 18000)
    if remaining is not None:
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        if hours > 0:
            time_str = f"{hours}ч {minutes}м {seconds}с"
        elif minutes > 0:
            time_str = f"{minutes}м {seconds}с"
        else:
            time_str = f"{seconds}с"

        await send_error_message(
            message,
            f"⏳ <b>Плетка на восстановительной перезарядке!</b>\n\n"
            f"Вы сможете снова хлестать раба через <b>{time_str}</b>."
        )
        return

    target_user_id = None

    if message.reply_to_message:
        target_user_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            username = args[1].lstrip('@')
            target_user_id = user_storage.get_user_id(username)
            if not target_user_id:
                await send_error_message(message, f"❌ Пользователь @{username} не найден.")
                return
        else:
            await send_error_message(
                message,
                "💡 <b>Использование команды:</b>\n"
                "• Ответьте на сообщение раба: <code>/плетка</code>\n"
                "• Укажите юзернейм: <code>/плетка @username</code>"
            )
            return

    if owner_id == target_user_id:
        await send_error_message(message, "❌ Вы не можете отхлестать самого себя!")
        return

    target_link = get_user_link(target_user_id)
    current_owner = slave_manager.get_owner(target_user_id)

    if current_owner != owner_id:
        await send_error_message(message, f"❌ Пользователь {target_link} не является вашим рабом!")
        return

    if slave_manager.is_whipped(target_user_id):
        await send_error_message(
            message,
            f"❌ Пользователь {target_link} уже отхлестан плеткой!\n"
            f"С него и так каждые 10 минут снимаются монеты. Дождитесь, пока он поработает или сыграет в казино."
        )
        return

    # Накладываем статус порки и взводим кулдаун
    slave_manager.whip_slave(target_user_id, owner_id, message.chat.id)
    cooldown_manager.set_cooldown(cooldown_key)

    await message.reply(
        f"💥 <b>ХЛЁСТ ПЛЁТКОЙ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"👑 {owner_link} жестоко отхлестал раба {target_link} плеткой! 🩸\n\n"
        f"💸 <i>Теперь каждые 10 минут у {target_link} будет списываться по 5 монет в пользу хозяина, "
        f"пока раб не поработает (/work, /freelance) или не сыграет в казино (/roulette, /blackjack)!</i>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

