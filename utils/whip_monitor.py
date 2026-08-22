"""Фоновый мониторинг порки рабов."""
import asyncio
import logging
import time
from aiogram import Bot

from utils.slave_manager import SlaveManager
from utils.economy_manager import EconomyManager
from utils.user_link import get_user_link

logger = logging.getLogger(__name__)

WHIP_TAX_INTERVAL = 600  # 10 минут
WHIP_TAX_AMOUNT = 5.0    # 5 монет


async def whip_monitor(bot: Bot):
    """Фоновая задача для снятия 5 монет каждые 10 минут у отхлестанных рабов."""
    await asyncio.sleep(10)
    slave_manager = SlaveManager()
    economy_manager = EconomyManager()

    while True:
        try:
            whipped_slaves = slave_manager.get_whipped_slaves()
            now = time.time()

            for slave_id, slave_data in whipped_slaves:
                last_tax_time = slave_data.get("last_whip_tax_time", 0)
                if now - last_tax_time >= WHIP_TAX_INTERVAL:
                    owner_id = slave_data.get("owner_id")
                    if not owner_id or slave_manager.get_owner(slave_id) != owner_id:
                        # Если владельца больше нет или владелец изменился
                        slave_manager.unwhip_slave(slave_id)
                        continue

                    slave_balance = economy_manager.get_balance(slave_id)
                    actual_tax = min(max(0.0, slave_balance), WHIP_TAX_AMOUNT)

                    if actual_tax > 0:
                        economy_manager.remove_money(slave_id, actual_tax)
                        economy_manager.add_money(owner_id, actual_tax)
                        slave_data["total_earned"] = round(
                            slave_data.get("total_earned", 0.0) + actual_tax, 2
                        )

                    slave_data["last_whip_tax_time"] = now
                    slave_manager.save_slaves()

                    chat_id = slave_data.get("whip_chat_id")
                    if chat_id:
                        slave_link = get_user_link(slave_id)
                        owner_link = get_user_link(owner_id)

                        if actual_tax > 0:
                            msg_text = (
                                f"🩸 <b>ПЛЁТКА В ДЕЙСТВИИ!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━\n\n"
                                f"⛓️ С раба {slave_link} списано <b>{actual_tax:.2f}</b> монет и передано хозяину {owner_link}!\n\n"
                                f"💡 <i>Раб, чтобы прекратить порку, поработайте (/work, /freelance) или сыграйте в казино (/roulette, /blackjack)!</i>"
                            )
                        else:
                            msg_text = (
                                f"🩸 <b>ПЛЁТКА В ДЕЙСТВИИ!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━\n\n"
                                f"⛓️ У раба {slave_link} 0 монет на балансе, хозяин {owner_link} ничего не получил!\n\n"
                                f"💡 <i>Раб, поработайте (/work, /freelance) или сыграйте в казино (/roulette, /blackjack)!</i>"
                            )

                        try:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=msg_text,
                                parse_mode="HTML",
                                disable_web_page_preview=True
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send whip tax notification to chat {chat_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка в фоновом мониторе whip_monitor: {e}", exc_info=True)

        await asyncio.sleep(30)
