"""Фоновый мониторинг микрозаймов, начисления пени и надзора за коллекторами."""
import asyncio
import logging
import time
from aiogram import Bot

from utils.loan_manager import LoanManager, PENALTY_INTERVAL, PENALTY_RATE, MAX_DEBT_MULTIPLIER
from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager
from utils.user_link import get_user_link

logger = logging.getLogger(__name__)


async def loan_monitor(bot: Bot):
    """
    Фоновая задача:
    1. Отслеживает дедлайны займов и переводит их в статус 'overdue'.
    2. Начисляет штрафную пеню каждые 12 часов просрочки.
    3. Контролирует сроки контрактов коллекторов (налагает санкции за простой).
    """
    # Ждем старта бота
    await asyncio.sleep(20)
    loan_manager = LoanManager()
    economy_manager = EconomyManager()
    slave_manager = SlaveManager()

    logger.info("Фоновый монитор микрозаймов и коллекторов запущен.")

    while True:
        try:
            now = time.time()

            # 1. Проверка займов
            loans_snapshot = list(loan_manager.loans.items())
            for user_id, user_loans in loans_snapshot:
                for loan in list(user_loans):
                    due_at = loan.get("due_at", 0)
                    status = loan.get("status", "active")
                    principal = loan.get("principal", 100.0)
                    debt = loan.get("debt", 0.0)
                    loan_id = loan.get("id", 1)

                    # Перевод в статус просрочки
                    if status == "active" and now > due_at:
                        loan["status"] = "overdue"
                        loan["last_penalty_at"] = now
                        loan_manager.save_data()
                        logger.warning(f"Займ #{loan_id} пользователя {user_id} перешел в статус OVERDUE. Долг: {debt}")

                        # Пробуем уведомить должника в ЛС
                        try:
                            user_link = get_user_link(user_id)
                            await bot.send_message(
                                chat_id=user_id,
                                text=(
                                    f"🚨 <b>ВНИМАНИЕ: СРОК ЗАЙМА #{loan_id} ИСТЕК!</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                    f"Уважаемый {user_link}, срок возврата займа #{loan_id} по тарифу «{loan.get('tariff_name')}» истек!\n\n"
                                    f"💸 <b>Текущий долг:</b> {debt:.2f} монет\n"
                                    f"⚠️ <b>Статус:</b> <code>ПРОСРОЧЕН (OVERDUE)</code>\n"
                                    f"📈 Каждые 12 часов будет начисляться пеня (+5%).\n"
                                    f"🔒 Ваши переводы монет заблокированы, а дело передано на <b>Биржу коллекторов</b>!\n\n"
                                    f"💡 <i>Срочно погасите задолженность командой /repay</i>"
                                ),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                    # Начисление пени каждые 12 часов
                    elif status == "overdue":
                        last_penalty = loan.get("last_penalty_at", due_at)
                        if now - last_penalty >= PENALTY_INTERVAL:
                            max_cap = round(principal * MAX_DEBT_MULTIPLIER, 2)
                            if debt < max_cap:
                                penalty = round(principal * PENALTY_RATE, 2)
                                new_debt = round(min(debt + penalty, max_cap), 2)
                                loan["debt"] = new_debt
                                loan["last_penalty_at"] = now
                                loan_manager.save_data()
                                logger.info(f"Начислена пеня {penalty} пользователю {user_id} по займу #{loan_id}. Новый долг: {new_debt}")

                                # Проверяем платежеспособность заемщика
                                debtor_bal = economy_manager.get_balance(user_id)
                                if debtor_bal <= 0.5:
                                    owner_id = slave_manager.get_owner(user_id)
                                    if owner_id:
                                        # Если заемщик — чей-то раб, пеня взыскивается с баланса владельца!
                                        owner_bal = economy_manager.get_balance(owner_id)
                                        from_owner = round(min(owner_bal, penalty), 2)
                                        if from_owner > 0:
                                            economy_manager.remove_money(owner_id, from_owner)
                                            loan_manager.record_owner_bailout(user_id, owner_id, from_owner)
                                            # Погашаем часть пени за счет хозяина
                                            loan["debt"] = round(max(0.0, new_debt - from_owner), 2)
                                            loan_manager.save_data()
                                            try:
                                                await bot.send_message(
                                                    chat_id=owner_id,
                                                    text=(
                                                        f"🚨 <b>Списание за долги раба!</b>\n"
                                                        f"У вашего раба (ID: {user_id}) просрочен займ #{loan_id}.\n"
                                                        f"С вашего баланса автоматически списана пеня <b>{from_owner:.2f}</b> монет!"
                                                    ),
                                                    parse_mode="HTML"
                                                )
                                            except Exception:
                                                pass

                                        rem_shortfall = round(penalty - from_owner, 2)
                                        if rem_shortfall > 0:
                                            _, disc = slave_manager.apply_price_penalty(user_id, rem_shortfall)
                                            loan_manager.record_price_reduction(user_id, disc)
                                    else:
                                        # Владельца нет (свободен) -> снижение стоимости человека (банкротство)
                                        _, disc = slave_manager.apply_price_penalty(user_id, penalty)
                                        loan_manager.record_price_reduction(user_id, disc)

            # 2. Проверка контрактов коллекторов
            collectors_snapshot = list(loan_manager.collectors.items())
            for collector_id, coll_data in collectors_snapshot:
                contract = coll_data.get("active_contract")
                if contract:
                    expires_at = contract.get("expires_at", 0)
                    actions_done = contract.get("actions_done", 0)

                    # Срок контракта истек
                    if now > expires_at:
                        debtor_id = contract.get("debtor_id")
                        if actions_done == 0:
                            # Коллектор заблокировал дело и ничего не сделал -> Санкция за халатность!
                            strikes, ban_time, desc = loan_manager.apply_sanction(
                                collector_id,
                                f"Халатность: ордер на должника {debtor_id} истек без единого действия"
                            )
                            try:
                                await bot.send_message(
                                    chat_id=collector_id,
                                    text=(
                                        f"🚨 <b>КОНТРАКТ СГОРЕЛ ПО ХАЛАТНОСТИ!</b>\n\n"
                                        f"{desc}"
                                    ),
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass
                        else:
                            # Коллектор пытался, но срок ордера вышел без санкции
                            loan_manager.release_contract(collector_id, penalty_strike=False)
                            try:
                                await bot.send_message(
                                    chat_id=collector_id,
                                    text=f"⌛ Срок вашего ордера на должника {debtor_id} истек. Дело возвращено на биржу.",
                                    parse_mode="HTML"
                                )
                            except Exception:
                                pass

        except Exception as e:
            logger.error(f"Ошибка в loan_monitor: {e}", exc_info=True)

        await asyncio.sleep(60)
