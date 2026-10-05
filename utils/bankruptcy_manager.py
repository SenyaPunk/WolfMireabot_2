"""Модуль для управления процедурой банкротства и судебного урегулирования долгов."""
import json
import logging
import queue
import random
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.economy_manager import EconomyManager
from utils.treasury_manager import TreasuryManager
from utils.slave_manager import SlaveManager

logger = logging.getLogger(__name__)

# Конфигурация условий банкротства
MIN_DEBT_FOR_BANKRUPTCY = 1500.0   # Минимальный просроченный долг для подачи
MAX_BALANCE_FOR_BANKRUPTCY = 100.0  # Максимальный баланс на руках у должника
BANKRUPTCY_COOLDOWN = 21 * 86400    # Кулдаун между банкротствами (21 день)
IMMUNITY_DURATION = 7 * 86400      # 7 дней иммунитета от коллекторов после списания
QUARANTINE_DURATION = 14 * 86400   # 14 дней запрета на получение новых микрозаймов

SERVICE_SHIFTS_TOTAL = 8           # Количество исправительных смен
SERVICE_COOLDOWN = 900             # 15 минут между сменами
SERVICE_PAY_PER_SHIFT = 25.0       # Монет на руки за каждую смену


class BankruptcyManager:
    _instance = None
    _initialized = False

    def __new__(cls, bankruptcy_file: str = "bankruptcy.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, bankruptcy_file: str = "bankruptcy.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        b_path = Path(bankruptcy_file)
        if not b_path.is_absolute():
            b_path = data_dir / b_path

        self.bankruptcy_file: Path = b_path
        self.active_cases: Dict[int, Dict[str, Any]] = {}
        self.discharged: Dict[int, Dict[str, Any]] = {}
        self.history: List[Dict[str, Any]] = []

        self.load_data()

        # Потокобезопасная очередь для асинхронной записи
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        self.economy_manager = EconomyManager()
        self.treasury_manager = TreasuryManager()
        self.slave_manager = SlaveManager()

        BankruptcyManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.bankruptcy_file.with_suffix(".tmp")
                serializable_active = {str(k): v for k, v in data.get("active_cases", {}).items()}
                serializable_discharged = {str(k): v for k, v in data.get("discharged", {}).items()}
                payload = {
                    "active_cases": serializable_active,
                    "discharged": serializable_discharged,
                    "history": data.get("history", [])
                }
                with temp_file.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

                for attempt in range(5):
                    try:
                        temp_file.replace(self.bankruptcy_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения {self.bankruptcy_file} в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_data(self):
        try:
            if self.bankruptcy_file.exists():
                with self.bankruptcy_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_active = data.get("active_cases", {})
                    self.active_cases = {int(k): v for k, v in raw_active.items()}
                    raw_discharged = data.get("discharged", {})
                    self.discharged = {int(k): v for k, v in raw_discharged.items()}
                    self.history = data.get("history", [])
                    logger.info(f"Загружено дел о банкротстве: {len(self.active_cases)} активных, {len(self.discharged)} завершенных.")
            else:
                self.active_cases = {}
                self.discharged = {}
                self.history = []
        except Exception as e:
            logger.error(f"Ошибка загрузки {self.bankruptcy_file}: {e}")
            self.active_cases = {}
            self.discharged = {}
            self.history = []

    def save_data(self):
        snapshot = {
            "active_cases": {k: v.copy() for k, v in self.active_cases.items()},
            "discharged": {k: v.copy() for k, v in self.discharged.items()},
            "history": list(self.history)
        }
        self._write_queue.put(snapshot)

    # -------------------------------------------------------------
    # ПРОВЕРКИ И ВАЛИДАЦИЯ
    # -------------------------------------------------------------

    def get_case(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.active_cases.get(user_id)

    def get_discharged_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.discharged.get(user_id)

    def has_immunity(self, user_id: int) -> Tuple[bool, float]:
        """
        Проверяет, действует ли судебный иммунитет от коллекторов:
        - во время активного рассмотрения дела о банкротстве
        - в течение IMMUNITY_DURATION после завершения банкротства.
        Возвращает (есть_иммунитет, оставшееся_время_в_сек).
        """
        now = time.time()
        # Во время активного дела иммунитет действует постоянно
        if user_id in self.active_cases:
            return True, 86400.0

        # После завершения дела
        disc = self.discharged.get(user_id)
        if disc:
            imm_until = disc.get("immunity_until", 0.0)
            if now < imm_until:
                return True, round(imm_until - now, 1)

        return False, 0.0

    def is_in_quarantine(self, user_id: int) -> Tuple[bool, float]:
        """
        Проверяет, действует ли запрет на оформление новых микрозаймов.
        Возвращает (на_карантине, оставшееся_время_в_сек).
        """
        now = time.time()
        if user_id in self.active_cases:
            return True, 86400.0

        disc = self.discharged.get(user_id)
        if disc:
            quar_until = disc.get("quarantine_until", 0.0)
            if now < quar_until:
                return True, round(quar_until - now, 1)

        return False, 0.0

    def can_declare_bankruptcy(self, user_id: int) -> Tuple[bool, str]:
        """
        Проверяет соблюдение условий для подачи заявления о банкротстве:
        1. Нет активного открытого дела
        2. Прошел кулдаун 21 день с прошлого банкротства
        3. Долг по займам >= 1500 монет
        4. Есть просроченные займы (overdue или defaulted)
        5. Баланс на руках <= 100 монет
        """
        if user_id in self.active_cases:
            return False, "⚠️ У вас уже открыто активное судебное дело о банкротстве! Проверьте статус: <code>/банкротство</code>"

        now = time.time()
        disc = self.discharged.get(user_id)
        if disc:
            last_time = disc.get("discharged_at", 0.0)
            time_passed = now - last_time
            if time_passed < BANKRUPTCY_COOLDOWN:
                rem = BANKRUPTCY_COOLDOWN - time_passed
                days = int(rem // 86400)
                hours = int((rem % 86400) // 3600)
                return False, f"⏳ Судебный мораторий: повторное банкротство возможно только через <b>{days}д {hours}ч</b>."

        from utils.loan_manager import LoanManager
        loan_mgr = LoanManager()
        total_debt = loan_mgr.get_total_debt(user_id)
        overdue_debt = loan_mgr.get_total_overdue_debt(user_id)
        has_overdue = loan_mgr.has_overdue_loan(user_id)

        if not has_overdue and total_debt < MIN_DEBT_FOR_BANKRUPTCY:
            return False, (
                f"❌ <b>ОТКАЗ В ВОЗБУЖДЕНИИ ДЕЛА О БАНКРОТСТВЕ!</b>\n\n"
                f"Критерии для банкротства:\n"
                f"• Наличие просроченного долга от <b>{MIN_DEBT_FOR_BANKRUPTCY:.0f}</b> монет (у вас: {total_debt:.2f}м)\n"
                f"• Наличие просроченных договоров займа (у вас просрочек нет)\n\n"
                f"<i>Вы способны обслуживать свои обязательства в стандартном порядке.</i>"
            )

        if total_debt < MIN_DEBT_FOR_BANKRUPTCY:
            return False, f"❌ Сумма вашего долга (<b>{total_debt:.2f}</b> монет) меньше минимального порога банкротства (<b>{MIN_DEBT_FOR_BANKRUPTCY:.0f}</b> монет)."

        balance = self.economy_manager.get_balance(user_id)
        if balance > MAX_BALANCE_FOR_BANKRUPTCY:
            return False, (
                f"❌ <b>ОТКАЗ: ПРИЗНАКИ ФИКТИВНОГО БАНКРОТСТВА!</b>\n\n"
                f"На вашем балансе находится <b>{balance:.2f}</b> монет (лимит для банкротства: до {MAX_BALANCE_FOR_BANKRUPTCY:.0f}м).\n"
                f"Суд считает, что у вас есть средства для погашения долга через <code>/repay</code>."
            )

        return True, ""

    # -------------------------------------------------------------
    # СТАРТ БАНКРОТСТВА И НАЦИОНАЛИЗАЦИЯ ИМУЩЕСТВА
    # -------------------------------------------------------------

    def declare_bankruptcy(self, user_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """Инициирует банкротство, производит опись и конфискацию имущества."""
        can, reason = self.can_declare_bankruptcy(user_id)
        if not can:
            return False, reason, {}

        from utils.loan_manager import LoanManager
        loan_mgr = LoanManager()
        total_debt = loan_mgr.get_total_debt(user_id)
        now = time.time()

        # 1. Опись и конфискация остатков баланса в Казну
        current_balance = self.economy_manager.get_balance(user_id)
        confiscated_money = 0.0
        if current_balance > 0:
            confiscated_money = current_balance
            self.economy_manager.remove_money(user_id, confiscated_money)
            self.treasury_manager.add_to_treasury(
                confiscated_money,
                source="bankruptcy_seizure",
                description=f"Конфискация остатков средств банкрота {user_id}"
            )

        # 2. Освобождение рабов, если должник кем-то владеет
        freed_slaves = []
        slaves_of_user = self.slave_manager.get_slaves_of(user_id)
        for s_id, _ in slaves_of_user:
            self.slave_manager.free_slave(s_id)
            freed_slaves.append(s_id)

        # 3. Расчет стоимости выкупа на аукционе (25% от долга, кап от 500 до 3500)
        auction_price = round(max(500.0, min(3500.0, total_debt * 0.25)), 2)

        case_data = {
            "user_id": user_id,
            "declared_at": now,
            "initial_debt": total_debt,
            "remaining_debt": total_debt,
            "status": "awaiting_choice",
            "confiscated_money": confiscated_money,
            "freed_slaves_count": len(freed_slaves),
            "service_data": {
                "shifts_needed": SERVICE_SHIFTS_TOTAL,
                "shifts_done": 0,
                "last_shift_at": 0.0,
                "total_earned_pocket": 0.0,
                "total_debt_reduced": 0.0
            },
            "auction_data": {
                "buyout_price": auction_price,
                "chat_id": None,
                "message_id": None,
                "created_at": now
            },
            "duel_data": {
                "rounds_played": 0,
                "player_score": 0,
                "bailiff_score": 0,
                "log": []
            }
        }

        self.active_cases[user_id] = case_data
        self.save_data()

        # Добавляем запись в кредитную историю
        loan_mgr.add_credit_event(
            user_id,
            "bankruptcy_started",
            f"Возбуждено судебное производство о банкротстве. Опись долга: {total_debt:.2f}м."
        )

        logger.info(f"User {user_id} declared bankruptcy for debt {total_debt:.2f}. Confiscated: {confiscated_money:.2f}")
        return True, "Судебное производство успешно открыто!", case_data

    # -------------------------------------------------------------
    # ВЫБОР ПУТИ
    # -------------------------------------------------------------

    def choose_path(self, user_id: int, path: str) -> Tuple[bool, str]:
        case = self.active_cases.get(user_id)
        if not case:
            return False, "❌ У вас нет активного открытого дела о банкротстве."

        if path not in ("service", "auction", "duel"):
            return False, "❌ Неверный путь реабилитации."

        case["status"] = path
        self.save_data()
        return True, f"Выбран путь: {path}"

    # -------------------------------------------------------------
    # ПУТЬ А: ИСПРАВИТЕЛЬНЫЕ РАБОТЫ
    # -------------------------------------------------------------

    def perform_service_shift(self, user_id: int) -> Tuple[bool, str, bool]:
        """
        Выполняет одну смену исправительных работ.
        Возвращает (успех, текст_сообщения, завершено_ли_банкротство).
        """
        case = self.active_cases.get(user_id)
        if not case:
            return False, "❌ У вас нет активного дела о банкротстве.", False

        if case["status"] != "service":
            return False, "❌ Вы не выбрали исправительные работы в Арбитражном суде!", False

        s_data = case["service_data"]
        now = time.time()
        last_shift = s_data.get("last_shift_at", 0.0)

        # Проверка кулдауна (15 минут)
        if now - last_shift < SERVICE_COOLDOWN:
            rem = SERVICE_COOLDOWN - (now - last_shift)
            mins = int(rem // 60)
            secs = int(rem % 60)
            return False, f"⏳ Судебный надзиратель не дает смену! Перекур продлится ещё <b>{mins}м {secs}с</b>.", False

        shifts_done = s_data.get("shifts_done", 0) + 1
        shifts_needed = s_data.get("shifts_needed", SERVICE_SHIFTS_TOTAL)
        s_data["shifts_done"] = shifts_done
        s_data["last_shift_at"] = now

        # Каждая смена списывает пропорциональную долю долга
        debt_slice = round(case["initial_debt"] / shifts_needed, 2)
        new_remaining = max(0.0, round(case["remaining_debt"] - debt_slice, 2))
        case["remaining_debt"] = new_remaining

        s_data["total_debt_reduced"] = round(s_data.get("total_debt_reduced", 0.0) + debt_slice, 2)
        s_data["total_earned_pocket"] = round(s_data.get("total_earned_pocket", 0.0) + SERVICE_PAY_PER_SHIFT, 2)

        # Начисляем 25 монет на карман на еду
        self.economy_manager.add_money(user_id, SERVICE_PAY_PER_SHIFT)
        self.save_data()

        # Если выполнены все смены — долг полностью списан!
        if shifts_done >= shifts_needed:
            self.discharge_bankruptcy(user_id, method="service")
            msg = (
                f"🎉 <b>ПОЛНОЕ ОСВОБОЖДЕНИЕ ОТ ДОЛГОВ!</b>\n\n"
                f"Вы добросовестно отработали все <b>{shifts_needed}</b> исправительных смен!\n"
                f"⚖️ Арбитражный суд Волка постановил: <b>полностью аннулировать все ваши кредиты и пени!</b>\n"
                f"🛡️ Вам предоставлен <b>судебный иммунитет от коллекторов на 7 дней</b>.\n"
                f"💵 Заработано на смене: <b>+{SERVICE_PAY_PER_SHIFT:.2f}</b> монет на карман."
            )
            return True, msg, True

        msg = (
            f"🧹 <b>Смена #{shifts_done}/{shifts_needed} успешно отработана!</b>\n\n"
            f"• Списано с судебного долга: <b>-{debt_slice:.2f}</b> монет\n"
            f"• Выдано на питание: <b>+{SERVICE_PAY_PER_SHIFT:.2f}</b> монет\n"
            f"• Оставшийся долг: <b>{new_remaining:.2f}</b> монет\n"
            f"⏳ Следующая смена доступна через <b>15 минут</b> (<code>/clean</code>)."
        )
        return True, msg, False

    # -------------------------------------------------------------
    # ПУТЬ Б: ВЫКУП НА ДОЛГОВОМ АУКЦИОНЕ
    # -------------------------------------------------------------

    def buyout_bankrupt(self, buyer_id: int, bankrupt_id: int) -> Tuple[bool, str]:
        """Олигарх выкупает должника на аукционе банкротов."""
        if buyer_id == bankrupt_id:
            return False, "❌ Вы не можете выкупить самого себя на аукционе!"

        case = self.active_cases.get(bankrupt_id)
        if not case:
            return False, "❌ Дело о банкротстве этого игрока не найдено или уже закрыто."

        if case["status"] != "auction":
            return False, "❌ Этот должник в данный момент не выставлен на аукцион."

        buyout_price = case["auction_data"]["buyout_price"]
        buyer_balance = self.economy_manager.get_balance(buyer_id)

        if buyer_balance < buyout_price:
            return False, f"❌ У вас недостаточно монет для выкупа каторжника! Требуется: <b>{buyout_price:.2f}</b> монет (у вас: {buyer_balance:.2f}м)."

        # Проверка цепочки владения (нельзя купить своего хозяина)
        if self.slave_manager.is_in_master_chain(buyer_id, bankrupt_id):
            return False, "❌ Парадокс рабства: вы не можете выкупить своего господина!"

        # 1. Списание суммы выкупа у покупателя и отправка в Казну
        self.economy_manager.remove_money(buyer_id, buyout_price)
        self.treasury_manager.add_to_treasury(
            buyout_price,
            source="bankrupt_buyout",
            description=f"Выкуп банкрота {bankrupt_id} покупателем {buyer_id}"
        )

        # 2. Оформление банкрота в рабы к покупателю
        self.slave_manager.buy_slave(bankrupt_id, buyer_id, buyout_price)
        self.slave_manager.reset_price_penalty(bankrupt_id)

        # 3. Полное аннулирование долга перед МФО
        self.discharge_bankruptcy(bankrupt_id, method="auction", sponsor_id=buyer_id)

        logger.info(f"Buyer {buyer_id} bought out bankrupt {bankrupt_id} for {buyout_price:.2f}")
        return True, f"✅ Выкуп совершен! Банкрот поступил в ваше распоряжение, а все его долги перед МФО списаны."

    # -------------------------------------------------------------
    # ПУТЬ В: СУДЕБНЫЙ ПОЕДИНОК
    # -------------------------------------------------------------

    def play_duel_round(self, user_id: int) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Проводит раунд броска волчьих судебных костей против Судебного Пристава Лютого.
        Бросок 2d6 игрока против 2d6 пристава. Всего 3 раунда.
        """
        case = self.active_cases.get(user_id)
        if not case:
            return False, "❌ У вас нет открытого судебного дела о банкротстве.", {}

        if case["status"] != "duel":
            return False, "❌ Вы не выбрали судебный поединок!", {}

        duel = case["duel_data"]
        rounds_played = duel.get("rounds_played", 0)

        if rounds_played >= 3:
            return False, "❌ Все 3 раунда судебного поединка уже сыграны!", {}

        # Бросок 2d6
        p_die1, p_die2 = random.randint(1, 6), random.randint(1, 6)
        b_die1, b_die2 = random.randint(1, 6), random.randint(1, 6)

        player_total = p_die1 + p_die2
        bailiff_total = b_die1 + b_die2

        round_num = rounds_played + 1
        duel["rounds_played"] = round_num

        round_winner = "draw"
        if player_total > bailiff_total:
            round_winner = "player"
            duel["player_score"] = duel.get("player_score", 0) + 1
        elif bailiff_total > player_total:
            round_winner = "bailiff"
            duel["bailiff_score"] = duel.get("bailiff_score", 0) + 1

        round_entry = {
            "round": round_num,
            "player_dice": (p_die1, p_die2, player_total),
            "bailiff_dice": (b_die1, b_die2, bailiff_total),
            "winner": round_winner
        }
        duel.setdefault("log", []).append(round_entry)
        self.save_data()

        is_finished = round_num >= 3
        result_payload = {
            "round": round_num,
            "player_dice": f"🎲 {p_die1} + {p_die2} = <b>{player_total}</b>",
            "bailiff_dice": f"⚖️ {b_die1} + {b_die2} = <b>{bailiff_total}</b>",
            "round_winner": round_winner,
            "player_score": duel["player_score"],
            "bailiff_score": duel["bailiff_score"],
            "is_finished": is_finished,
            "final_outcome": None
        }

        if is_finished:
            p_score = duel["player_score"]
            b_score = duel["bailiff_score"]
            if p_score > b_score:
                # Победа игрока! Мгновенное списание 100%
                result_payload["final_outcome"] = "victory"
                self.discharge_bankruptcy(user_id, method="duel_victory")
            else:
                # Поражение или ничья: Суд списывает 60% долга, а остаток переводит в 4 легкие смены
                result_payload["final_outcome"] = "defeat"
                initial_debt = case["initial_debt"]
                rem_debt = round(initial_debt * 0.40, 2)
                case["status"] = "service"
                case["remaining_debt"] = rem_debt
                case["service_data"] = {
                    "shifts_needed": 4,
                    "shifts_done": 0,
                    "last_shift_at": 0.0,
                    "total_earned_pocket": 0.0,
                    "total_debt_reduced": round(initial_debt * 0.60, 2)
                }
                self.save_data()

        return True, "Раунд сыгран", result_payload

    # -------------------------------------------------------------
    # ЗАВЕРШЕНИЕ БАНКРОТСТВА И СНЯТИЕ ВСЕХ ДОЛГОВ
    # -------------------------------------------------------------

    def discharge_bankruptcy(self, user_id: int, method: str, sponsor_id: Optional[int] = None) -> str:
        """
        Полностью списывает все кредиты игрока в LoanManager,
        вешает судебный иммунитет на 7 дней и кредитный карантин на 14 дней.
        """
        from utils.loan_manager import LoanManager
        loan_mgr = LoanManager()

        case = self.active_cases.pop(user_id, None)
        initial_debt = case["initial_debt"] if case else loan_mgr.get_total_debt(user_id)

        # Полное удаление всех займов в LoanManager
        total_cleared = loan_mgr.clear_all_loans(user_id)

        now = time.time()
        self.discharged[user_id] = {
            "discharged_at": now,
            "immunity_until": now + IMMUNITY_DURATION,
            "quarantine_until": now + QUARANTINE_DURATION,
            "total_debt_discharged": initial_debt,
            "method": method,
            "sponsor_id": sponsor_id
        }

        # Запись в историю
        hist_entry = {
            "user_id": user_id,
            "discharged_at": now,
            "debt": initial_debt,
            "method": method,
            "sponsor_id": sponsor_id
        }
        self.history.append(hist_entry)
        if len(self.history) > 100:
            self.history = self.history[-100:]

        self.save_data()

        # Добавляем запись в кредитную историю пользователя
        method_names = {
            "service": "исправительные работы",
            "auction": f"долговой выкуп спонсором {sponsor_id}",
            "duel_victory": "победа в судебном поединке",
            "admin": "помилование верховного судьи"
        }
        m_str = method_names.get(method, method)
        loan_mgr.add_credit_event(
            user_id,
            "bankruptcy_discharged",
            f"Банкротство завершено ({m_str}). Списано {initial_debt:.2f}м долга. Иммунитет 7 дней."
        )

        logger.info(f"User {user_id} discharged from bankruptcy via {method}. Cleared debt: {initial_debt:.2f}")
        return f"Банкротство успешно завершено! Списано {initial_debt:.2f} монет."
