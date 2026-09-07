"""Фоновый монитор активных Специальных Военных Операций (СВО)."""
import asyncio
import logging
from aiogram import Bot

from utils.war_manager import WarManager

logger = logging.getLogger(__name__)


async def war_monitor(bot: Bot):
    """
    Фоновый мониторинг активных СВО:
    - Отслеживание таймеров и завершения времени операции
    - Запуск динамических погодных факторов и балансирующего ленд-лиза
    - Фиксация победы при разгроме противника
    """
    # Задержка на прогрев бота при старте
    await asyncio.sleep(20)
    logger.info("Фоновый монитор СВО успешно запущен.")

    wm = WarManager()

    while True:
        try:
            active_war_ids = [
                wid for wid, wdata in list(wm.wars.items())
                if wdata.get("status") == "active"
            ]

            for wid in active_war_ids:
                wdata = wm.wars.get(wid)
                if not wdata or wdata.get("status") != "active":
                    continue

                chat_id = wdata.get("chat_id")
                thread_id = wdata.get("message_thread_id")

                # 1. Проверяем внешние события (погода, ленд-лиз, партизаны, РЭБ)
                event_msg = wm.tick_war_events(wid)
                if event_msg and chat_id:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=event_msg,
                            message_thread_id=thread_id,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Ошибка отправки фронтового события СВО в чат {chat_id}: {e}")

                # 2. Проверяем условия окончания СВО
                finished, win_side, reason = wm.check_war_outcome(wid)
                if finished:
                    report = wm.finish_war(wid, win_side, reason)
                    if chat_id:
                        try:
                            await bot.send_message(
                                chat_id=chat_id,
                                text=report,
                                message_thread_id=thread_id,
                                parse_mode="HTML"
                            )
                        except Exception as e:
                            logger.warning(f"Ошибка отправки победного рапорта СВО в чат {chat_id}: {e}")

        except Exception as e:
            logger.error(f"Непредвиденная ошибка в war_monitor: {e}", exc_info=True)

        await asyncio.sleep(15)
