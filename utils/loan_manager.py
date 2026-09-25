"""Модуль для управления системой микрозаймов и работы коллекторов."""
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.economy_manager import EconomyManager

logger = logging.getLogger(__name__)

# Конфигурация тарифов
TARIFFS = {
    "light": {
        "name": "Лайт",
        "min_amount": 100,
        "max_amount": 350,
        "rate": 0.15,           # +15%
        "duration": 36 * 3600,   # 36 часов
        "req_loans": 0,
        "description": "Сумма 100–350 монет, срок 36 часов, ставка 15%. Доступен всем."
    },
    "standard": {
        "name": "Стандарт",
        "min_amount": 350,
        "max_amount": 900,
        "rate": 0.20,           # +20%
        "duration": 48 * 3600,   # 48 часов
        "req_loans": 1,
        "description": "Сумма 350–900 монет, срок 48 часов, ставка 20%. Требуется 1 успешно закрытый займ."
    },
    "premium": {
        "name": "Премиум",
        "min_amount": 900,
        "max_amount": 2000,
        "rate": 0.25,           # +25%
        "duration": 72 * 3600,   # 72 часа (3 дня)
        "req_loans": 3,
        "description": "Сумма 900–2000 монет, срок 72 часа, ставка 25%. Требуется 3 закрытых займа без просрочек."
    }
}

# Ранги коллекторов и проценты комиссии
COLLECTOR_RANKS = {
    "trainee": {
        "title": "Стажер-взыскатель",
        "min_closed": 0,
        "commission": 0.20,  # 20%
    },
    "enforcer": {
        "title": "Вышибала",
        "min_closed": 4,
        "commission": 0.25,  # 25%
    },
    "senior": {
        "title": "Старший дознаватель",
        "min_closed": 11,
        "commission": 0.30,  # 30%
    },
    "chief": {
        "title": "Глава ЧВК «Взыскание»",
        "min_closed": 25,
        "commission": 0.35,  # 35%
    }
}

# Санкции за нарушения коллекторов
# 1 страйк: 12 часов бана, штраф 100
# 2 страйка: 48 часов бана (2 дня), штраф 250
# 3 страйка: 120 часов бана (5 дней), штраф 500, сброс ранга
SANCTION_LEVELS = {
    1: {"ban_seconds": 12 * 3600, "fine": 100.0, "label": "12 часов"},
    2: {"ban_seconds": 48 * 3600, "fine": 250.0, "label": "2 дня (48 часов)"},
    3: {"ban_seconds": 120 * 3600, "fine": 500.0, "label": "5 ДНЕЙ (120 часов)"}
}

LICENSE_FEE = 50.0
CONTRACT_DURATION = 3 * 3600  # 3 часа на контракт
PENALTY_INTERVAL = 12 * 3600  # Каждые 12 часов просрочки
PENALTY_RATE = 0.05           # +5% от первоначального тела займа
MAX_DEBT_MULTIPLIER = 2.5     # Максимум 2.5x от первоначального тела
MAX_ACTIVE_LOANS = 5          # Максимум активных займов одновременно


class LoanManager:
    _instance = None
    _initialized = False

    def __new__(cls, loans_file: str = "loans.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, loans_file: str = "loans.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        loans_path = Path(loans_file)
        if not loans_path.is_absolute():
            loans_path = data_dir / loans_path

        self.loans_file: Path = loans_path
        self.loans: Dict[int, List[Dict[str, Any]]] = {}
        self.credit_history: Dict[int, Dict[str, Any]] = {}
        self.collectors: Dict[int, Dict[str, Any]] = {}
        self.load_data()

        # Очередь и фоновый поток для неблокирующей и надежной записи на диск
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        self.economy_manager = EconomyManager()
        LoanManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.loans_file.with_suffix(".tmp")
                serializable_loans = {str(k): v for k, v in data.get("loans", {}).items()}
                serializable_hist = {str(k): v for k, v in data.get("credit_history", {}).items()}
                serializable_coll = {str(k): v for k, v in data.get("collectors", {}).items()}

                payload = {
                    "loans": serializable_loans,
                    "credit_history": serializable_hist,
                    "collectors": serializable_coll
                }

                with temp_file.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

                for attempt in range(5):
                    try:
                        temp_file.replace(self.loans_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения loans.json в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_data(self):
        try:
            if self.loans_file.exists():
                with self.loans_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_loans = data.get("loans", {})
                    self.loans = {}
                    total_count = 0
                    for k, v in raw_loans.items():
                        uid = int(k)
                        if isinstance(v, list):
                            for idx, item in enumerate(v, 1):
                                if "id" not in item:
                                    item["id"] = idx
                            self.loans[uid] = v
                            total_count += len(v)
                        elif isinstance(v, dict):
                            # Обратная совместимость: если займ был сохранен как один dict
                            if "id" not in v:
                                v["id"] = 1
                            self.loans[uid] = [v]
                            total_count += 1
                        else:
                            self.loans[uid] = []

                    self.credit_history = {int(k): v for k, v in data.get("credit_history", {}).items()}
                    self.collectors = {int(k): v for k, v in data.get("collectors", {}).items()}
                    logger.info(f"Загружено {total_count} займов и {len(self.collectors)} коллекторов")
            else:
                logger.info(f"Файл {self.loans_file} не найден, создаем пустой")
                self.loans = {}
                self.credit_history = {}
                self.collectors = {}
                self.save_data_sync()
        except Exception as e:
            logger.error(f"Ошибка загрузки {self.loans_file}: {e}")
            self.loans = {}
            self.credit_history = {}
            self.collectors = {}

    def save_data(self):
        snapshot = {
            "loans": {k: [l.copy() for l in v] for k, v in self.loans.items()},
            "credit_history": self.credit_history.copy(),
            "collectors": self.collectors.copy()
        }
        self._write_queue.put(snapshot)

    def save_data_sync(self):
        payload = {
            "loans": {str(k): v for k, v in self.loans.items()},
            "credit_history": {str(k): v for k, v in self.credit_history.items()},
            "collectors": {str(k): v for k, v in self.collectors.items()}
        }
        with self.loans_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # -------------------------------------------------------------
    # ЛОГИКА МИКРОЗАЙМОВ
    # -------------------------------------------------------------

    def get_user_loans(self, user_id: int) -> List[Dict[str, Any]]:
        """Возвращает список всех активных или просроченных займов пользователя."""
        return self.loans.get(user_id, [])

    def get_user_loan(self, user_id: int, loan_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Возвращает займ пользователя:
        - если указан loan_id: конкретный займ по номеру
        - иначе наиболее приоритетный (сначала просроченный, иначе ближайший к дедлайну).
        """
        user_loans = self.get_user_loans(user_id)
        if not user_loans:
            return None

        if loan_id is not None:
            for l in user_loans:
                if l.get("id") == loan_id:
                    return l
            return None

        now = time.time()
        overdue = [l for l in user_loans if l.get("status") == "overdue" or l.get("due_at", 0) < now]
        if overdue:
            return overdue[0]
        return min(user_loans, key=lambda l: l.get("due_at", 0))

    def get_total_debt(self, user_id: int) -> float:
        """Возвращает общий долг по всем займам пользователя."""
        return round(sum(l.get("debt", 0.0) for l in self.get_user_loans(user_id)), 2)

    def get_total_overdue_debt(self, user_id: int) -> float:
        """Возвращает сумму только просроченных долгов пользователя."""
        now = time.time()
        return round(sum(
            l.get("debt", 0.0) for l in self.get_user_loans(user_id)
            if l.get("status") == "overdue" or l.get("due_at", 0) < now
        ), 2)

    def get_credit_history(self, user_id: int) -> Dict[str, Any]:
        """Возвращает кредитную историю пользователя."""
        if user_id not in self.credit_history:
            self.credit_history[user_id] = {
                "successful_loans": 0,
                "overdue_count": 0,
                "total_borrowed": 0.0,
                "total_repaid": 0.0
            }
        return self.credit_history[user_id]

    def can_take_loan(self, user_id: int, tariff_key: str, amount: float, count: int = 1) -> Tuple[bool, str]:
        """Проверяет возможность взять один или несколько займов."""
        if tariff_key not in TARIFFS:
            return False, "❌ Указан неверный тариф займа."

        if count < 1 or count > MAX_ACTIVE_LOANS:
            return False, f"❌ За раз можно оформить от 1 до {MAX_ACTIVE_LOANS} займов."

        user_loans = self.get_user_loans(user_id)

        # Проверка на наличие просроченных займов: при просрочке новые займы не выдаются
        now = time.time()
        overdue_loans = [l for l in user_loans if l.get("status") == "overdue" or l.get("due_at", 0) < now]
        if overdue_loans:
            overdue_debt = sum(l.get("debt", 0.0) for l in overdue_loans)
            return False, f"❌ У вас есть просроченный долг на сумму <b>{overdue_debt:.2f}</b> монет! Новые займы заблокированы до полного закрытия просрочки (/repay)."

        # Проверка лимита одновременных займов
        if len(user_loans) + count > MAX_ACTIVE_LOANS:
            rem = max(0, MAX_ACTIVE_LOANS - len(user_loans))
            if rem == 0:
                return False, f"❌ Достигнут лимит одновременных займов ({MAX_ACTIVE_LOANS} шт.). Погасите активные займы перед оформлением новых!"
            else:
                return False, f"❌ Вы можете оформить максимум ещё <b>{rem}</b> шт. (сейчас активно: {len(user_loans)} из {MAX_ACTIVE_LOANS})."

        tariff = TARIFFS[tariff_key]
        hist = self.get_credit_history(user_id)
        if hist.get("successful_loans", 0) < tariff["req_loans"]:
            return False, f"❌ Для тарифа «{tariff['name']}» необходимо минимум {tariff['req_loans']} успешно закрытых займов (у вас: {hist.get('successful_loans', 0)})."

        if amount < tariff["min_amount"] or amount > tariff["max_amount"]:
            return False, f"❌ Для тарифа «{tariff['name']}» сумма должна быть от <b>{tariff['min_amount']}</b> до <b>{tariff['max_amount']}</b> монет."

        # Проверка текущего баланса: микрозайм не выдается слишком богатым игрокам (> 5000 монет)
        current_balance = self.economy_manager.get_balance(user_id)
        if current_balance > 5000:
            return False, f"❌ Отказано службой безопасности МФО! Ваш баланс (<b>{current_balance:.2f}</b> монет) слишком велик для получения микрозайма."

        return True, ""

    def take_loan(self, user_id: int, tariff_key: str, amount: float, count: int = 1) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """Оформляет один или несколько займов и выдает монеты игроку."""
        can, reason = self.can_take_loan(user_id, tariff_key, amount, count)
        if not can:
            return False, reason, None

        tariff = TARIFFS[tariff_key]
        now = time.time()
        initial_debt = round(amount * (1.0 + tariff["rate"]), 2)
        due_at = now + tariff["duration"]

        user_loans = self.loans.setdefault(user_id, [])
        max_id = max([l.get("id", 0) for l in user_loans], default=0)

        created_loans = []
        for i in range(1, count + 1):
            loan_id = max_id + i
            loan_data = {
                "id": loan_id,
                "tariff": tariff_key,
                "tariff_name": tariff["name"],
                "principal": round(float(amount), 2),
                "debt": initial_debt,
                "rate": tariff["rate"],
                "taken_at": now,
                "due_at": due_at,
                "status": "active",
                "last_penalty_at": due_at,
                "repaid_amount": 0.0,
                "collector_contract": None
            }
            user_loans.append(loan_data)
            created_loans.append(loan_data)

        total_received = round(amount * count, 2)
        hist = self.get_credit_history(user_id)
        hist["total_borrowed"] = round(hist.get("total_borrowed", 0.0) + total_received, 2)

        self.economy_manager.add_money(user_id, total_received)
        self.save_data()

        logger.info(f"User {user_id} took {count} loan(s) of tariff {tariff_key}, amount {amount} each, total received {total_received}")
        msg = f"✅ Успешно оформлено займов: {count} шт.!" if count > 1 else "✅ Займ успешно оформлен!"
        return True, msg, created_loans

    def repay_loan(self, user_id: int, amount: Optional[float] = None, loan_id: Optional[int] = None) -> Tuple[bool, str, float]:
        """
        Погашает займы (частично или полностью).
        Если loan_id указан — погашает конкретный займ.
        Иначе погашает долги в порядке срочности (сначала просроченные, затем ближайшие к дедлайну).
        """
        user_loans = self.get_user_loans(user_id)
        if not user_loans:
            return False, "❌ У вас нет активных займов для погашения.", 0.0

        user_balance = self.economy_manager.get_balance(user_id)
        now = time.time()

        if loan_id is not None:
            target_loan = self.get_user_loan(user_id, loan_id)
            if not target_loan:
                return False, f"❌ Займ #{loan_id} не найден. Проверьте список активных займов: /my_loan", 0.0
            targets = [target_loan]
        else:
            # Сортируем: сначала просроченные по due_at, затем активные по due_at
            targets = sorted(
                user_loans,
                key=lambda l: (0 if l.get("status") == "overdue" or l.get("due_at", 0) < now else 1, l.get("due_at", 0))
            )

        total_target_debt = sum(l.get("debt", 0.0) for l in targets)

        if amount is None or amount <= 0 or amount > total_target_debt:
            available_payment = min(user_balance, total_target_debt)
        else:
            available_payment = min(user_balance, amount)

        if available_payment <= 0:
            return False, "❌ На вашем балансе недостаточно монет для внесения платежа.", 0.0

        rem_pay = available_payment
        actual_paid = 0.0
        closed_loans_info = []
        partially_paid_info = []
        hist = self.get_credit_history(user_id)

        for loan in list(targets):
            if rem_pay <= 0.001:
                break
            debt = loan.get("debt", 0.0)
            pay = min(rem_pay, debt)
            new_debt = round(debt - pay, 2)
            loan["debt"] = new_debt
            loan["repaid_amount"] = round(loan.get("repaid_amount", 0.0) + pay, 2)
            rem_pay = round(rem_pay - pay, 2)
            actual_paid = round(actual_paid + pay, 2)
            hist["total_repaid"] = round(hist.get("total_repaid", 0.0) + pay, 2)

            lid = loan.get("id", 1)
            t_name = loan.get("tariff_name", "Займ")
            if new_debt <= 0.01:
                was_overdue = (loan.get("status") == "overdue" or loan.get("due_at", 0) < now)
                if was_overdue:
                    hist["overdue_count"] = hist.get("overdue_count", 0) + 1
                else:
                    hist["successful_loans"] = hist.get("successful_loans", 0) + 1

                if loan in self.loans.get(user_id, []):
                    self.loans[user_id].remove(loan)
                closed_loans_info.append(f"• Займ #{lid} «{t_name}» (закрыт!)")
            else:
                partially_paid_info.append(f"• Займ #{lid} «{t_name}»: остаток {new_debt:.2f}м")

        self.economy_manager.remove_money(user_id, actual_paid)

        # Очищаем запись пользователя, если займов больше нет
        if user_id in self.loans and len(self.loans[user_id]) == 0:
            del self.loans[user_id]
            # Снимаем контракт коллектора, если был активен
            for coll_data in self.collectors.values():
                if coll_data.get("active_contract", {}).get("debtor_id") == user_id:
                    coll_data["active_contract"] = None
        else:
            # Если не осталось просроченных займов, освобождаем коллектора
            if not self.has_overdue_loan(user_id):
                for coll_data in self.collectors.values():
                    if coll_data.get("active_contract", {}).get("debtor_id") == user_id:
                        coll_data["active_contract"] = None

        self.save_data()

        # Формирование ответа
        rem_loans = self.get_user_loans(user_id)
        rem_debt = self.get_total_debt(user_id)

        lines = [f"💳 <b>Платеж успешно внесен!</b>\nСписано: <b>{actual_paid:.2f}</b> монет.\n"]
        if closed_loans_info:
            lines.append("🎉 <b>Полностью погашены:</b>\n" + "\n".join(closed_loans_info))
        if partially_paid_info:
            lines.append("📉 <b>Частично оплачены:</b>\n" + "\n".join(partially_paid_info))

        if not rem_loans:
            lines.append("\n🥳 <b>Поздравляем! Все ваши займы полностью закрыты!</b>")
        else:
            lines.append(f"\n📊 Осталось активных займов: <b>{len(rem_loans)}</b> (общий долг: <b>{rem_debt:.2f}</b> монет).")

        return True, "\n".join(lines), actual_paid

    def has_overdue_loan(self, user_id: int) -> bool:
        """Проверяет, есть ли у игрока хотя бы один просроченный долг."""
        now = time.time()
        for loan in self.get_user_loans(user_id):
            if loan.get("status") == "overdue" or loan.get("due_at", 0) < now:
                return True
        return False

    def get_all_overdue_loans(self) -> List[Tuple[int, Dict[str, Any]]]:
        """Возвращает список должников с просроченными займами для биржи коллекторов."""
        now = time.time()
        overdue_list = []
        for uid, user_loans in self.loans.items():
            user_overdue = [l for l in user_loans if l.get("status") == "overdue" or l.get("due_at", 0) < now]
            if user_overdue:
                total_debt = round(sum(l.get("debt", 0.0) for l in user_overdue), 2)
                coll_id = next((l.get("collector_contract") for l in user_overdue if l.get("collector_contract")), None)
                earliest_due = min(l.get("due_at", 0) for l in user_overdue)
                overdue_list.append((uid, {
                    "debt": total_debt,
                    "count": len(user_overdue),
                    "loans": user_overdue,
                    "collector_contract": coll_id,
                    "status": "overdue",
                    "due_at": earliest_due
                }))
        return overdue_list

    # -------------------------------------------------------------
    # ЛОГИКА РАБОТЫ КОЛЛЕКТОРА
    # -------------------------------------------------------------

    def get_collector(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Возвращает данные коллектора."""
        return self.collectors.get(user_id)

    def is_collector_banned(self, user_id: int) -> Tuple[bool, float, str]:
        """Проверяет, забанен ли коллектор и сколько секунд осталось."""
        coll = self.get_collector(user_id)
        if not coll:
            return False, 0.0, ""

        banned_until = coll.get("banned_until", 0.0)
        now = time.time()
        if banned_until > now:
            remaining = banned_until - now
            last_reason = coll.get("strike_history", [{}])[-1].get("reason", "Нарушение кодекса коллекторов") if coll.get("strike_history") else "Нарушение правил"
            return True, remaining, last_reason
        return False, 0.0, ""

    def update_collector_rank(self, user_id: int):
        """Обновляет ранг коллектора в зависимости от числа закрытых дел."""
        coll = self.get_collector(user_id)
        if not coll:
            return

        closed = coll.get("contracts_closed", 0)
        if closed >= 25:
            coll["rank"] = "chief"
        elif closed >= 11:
            coll["rank"] = "senior"
        elif closed >= 4:
            coll["rank"] = "enforcer"
        else:
            coll["rank"] = "trainee"

    def register_collector(self, user_id: int) -> Tuple[bool, str]:
        """Регистрирует игрока в качестве коллектора."""
        if self.has_overdue_loan(user_id):
            return False, "❌ Вы не можете работать коллектором, пока у вас самих висит просроченный займ!"

        is_banned, remaining, reason = self.is_collector_banned(user_id)
        if is_banned:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return False, f"🚫 <b>Вам запрещено работать коллектором!</b>\nПричина: {reason}\nОсталось бана: <b>{hours}ч {minutes}м</b>."

        coll = self.get_collector(user_id)
        if coll and coll.get("status") == "active":
            return False, "ℹ️ Вы уже устроены коллектором в агентстве «Взыскание»!"

        # Проверка и списание лицензионного сбора (50 монет)
        balance = self.economy_manager.get_balance(user_id)
        if balance < LICENSE_FEE:
            return False, f"❌ Для покупки лицензии коллектора и экипировки требуется <b>{LICENSE_FEE:.0f}</b> монет (у вас: {balance:.2f})."

        self.economy_manager.remove_money(user_id, LICENSE_FEE)

        if not coll:
            self.collectors[user_id] = {
                "status": "active",
                "rank": "trainee",
                "registered_at": time.time(),
                "total_collected": 0.0,
                "contracts_closed": 0,
                "active_contract": None,
                "strikes": 0,
                "banned_until": 0.0,
                "strike_history": []
            }
        else:
            coll["status"] = "active"

        self.save_data()
        return True, f"💼 <b>Поздравляем с трудоустройством!</b>\nВам выдано служебное удостоверение коллектора агентства «Взыскание». С баланса списан сбор <b>{LICENSE_FEE:.0f}</b> монет.\nИзучите базу должников командой <code>/debtors</code>."

    def resign_collector(self, user_id: int) -> Tuple[bool, str]:
        """Увольнение с работы коллектора."""
        coll = self.get_collector(user_id)
        if not coll or coll.get("status") != "active":
            return False, "❌ Вы не работаете коллектором."

        if coll.get("active_contract"):
            return False, "❌ Сначала завершите или отмените активный контракт на взыскание долга!"

        coll["status"] = "inactive"
        self.save_data()
        return True, "👋 Вы успешно уволились из коллекторского агентства."

    def apply_sanction(self, user_id: int, reason: str) -> Tuple[int, float, str]:
        """
        Применяет санкцию к коллектору.
        Возвращает (новый уровень страйков, секунды бана, текстовое описание).
        """
        coll = self.get_collector(user_id)
        if not coll:
            return 0, 0.0, ""

        strikes = coll.get("strikes", 0) + 1
        coll["strikes"] = strikes

        now = time.time()
        level = min(strikes, 3)
        sanction = SANCTION_LEVELS[level]
        ban_duration = sanction["ban_seconds"]
        fine_amount = sanction["fine"]

        coll["banned_until"] = now + ban_duration
        coll["active_contract"] = None  # Сброс контракта

        # Списание штрафа с баланса (если есть деньги)
        user_bal = self.economy_manager.get_balance(user_id)
        actual_fine = min(user_bal, fine_amount)
        if actual_fine > 0:
            self.economy_manager.remove_money(user_id, actual_fine)

        # При 3 страйках сбрасывается карьерный ранг
        if strikes >= 3:
            coll["rank"] = "trainee"

        record = {
            "strike_num": strikes,
            "reason": reason,
            "timestamp": now,
            "ban_seconds": ban_duration,
            "fine_charged": actual_fine
        }
        coll.setdefault("strike_history", []).append(record)
        self.save_data()

        label = sanction["label"]
        desc = (
            f"⚠️ <b>НАЛОЖЕНЫ САНКЦИИ НА КОЛЛЕКТОРА!</b> (Страйк {strikes}/3)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 <b>Причина:</b> {reason}\n"
            f"⏳ <b>Запрет работы:</b> на {label}\n"
            f"💸 <b>Штраф:</b> {actual_fine:.2f} монет\n"
        )
        if strikes >= 3:
            desc += "🚨 <i>Вы получили 3-й страйк! Ранг аннулирован до Стажера, максимальный бан на 5 дней!</i>"

        logger.warning(f"Collector {user_id} received strike {strikes}: {reason}. Ban: {ban_duration}s")
        return strikes, ban_duration, desc

    def take_debt_contract(self, collector_id: int, debtor_id: int) -> Tuple[bool, str]:
        """Коллектор берет должника в работу."""
        is_banned, remaining, reason = self.is_collector_banned(collector_id)
        if is_banned:
            hours = int(remaining // 3600)
            return False, f"🚫 Вы временно отстранены от работы! Оставшийся срок бана: <b>{hours}ч</b>."

        coll = self.get_collector(collector_id)
        if not coll or coll.get("status") != "active":
            return False, "❌ Вы не являетесь действующим сотрудником агентства. Начните с команды <code>/become_collector</code>."

        if coll.get("active_contract"):
            target = coll["active_contract"].get("debtor_id")
            return False, f"❌ У вас уже есть дело в работе (ID: <code>{target}</code>)! Завершите его перед взятием нового."

        if not self.has_overdue_loan(debtor_id):
            return False, "❌ Этот заемщик не имеет просроченных задолженностей или уже закрыл долг!"

        user_loans = self.get_user_loans(debtor_id)
        now = time.time()
        overdue_loans = [l for l in user_loans if l.get("status") == "overdue" or l.get("due_at", 0) < now]

        # Проверяем, не ведет ли уже кто-то этот контракт
        for l in overdue_loans:
            current_contract_collector = l.get("collector_contract")
            if current_contract_collector and current_contract_collector != collector_id:
                other_coll = self.get_collector(current_contract_collector)
                if other_coll and other_coll.get("active_contract", {}).get("expires_at", 0) > now:
                    return False, "🔒 Это дело уже передано в разработку другому коллектору! Подождите истечения срока его ордера."

        # Закрепляем контракт на всех просроченных займах должника
        coll["active_contract"] = {
            "debtor_id": debtor_id,
            "taken_at": now,
            "expires_at": now + CONTRACT_DURATION,
            "actions_done": 0
        }
        for l in overdue_loans:
            l["collector_contract"] = collector_id
        self.save_data()

        total_overdue = sum(l.get("debt", 0.0) for l in overdue_loans)
        count_str = f" ({len(overdue_loans)} шт.)" if len(overdue_loans) > 1 else ""
        return True, f"📁 <b>Контракт оформлен!</b>\nВы взяли в разработку дело должника <code>{debtor_id}</code> на общую сумму <b>{total_overdue:.2f}</b> монет{count_str}.\nОрдер действует 3 часа. Используйте спецприемы в чате!"

    def release_contract(self, collector_id: int, penalty_strike: bool = False, reason: str = ""):
        """Снимает активный контракт с коллектора."""
        coll = self.get_collector(collector_id)
        if not coll:
            return

        act = coll.get("active_contract")
        if not act:
            return

        debtor_id = act.get("debtor_id")
        if debtor_id in self.loans:
            for l in self.loans[debtor_id]:
                if l.get("collector_contract") == collector_id:
                    l["collector_contract"] = None

        coll["active_contract"] = None

        if penalty_strike:
            self.apply_sanction(collector_id, reason or "Халатность: невыполнение условий контракта")
        else:
            self.save_data()

    def process_collector_success(self, collector_id: int, debtor_id: int, collected_amount: float) -> Tuple[float, float, bool]:
        """
        Обрабатывает успешное взыскание долга:
        - распределяет сумму (процент коллектору, остальное гасит долг)
        - обновляет статистику коллектора и проверяет повышение ранга
        """
        coll = self.get_collector(collector_id)
        if not coll:
            return 0.0, 0.0, False

        rank_key = coll.get("rank", "trainee")
        commission_rate = COLLECTOR_RANKS.get(rank_key, {}).get("commission", 0.20)

        collector_share = round(collected_amount * commission_rate, 2)
        mfi_share = round(collected_amount - collector_share, 2)

        # Выплачиваем комиссию коллектору
        self.economy_manager.add_money(collector_id, collector_share)
        coll["total_collected"] = round(coll.get("total_collected", 0.0) + collected_amount, 2)

        user_loans = self.get_user_loans(debtor_id)
        now = time.time()
        # В первую очередь гасим просроченные займы
        overdue_loans = [l for l in user_loans if l.get("status") == "overdue" or l.get("due_at", 0) < now]
        targets = overdue_loans if overdue_loans else user_loans

        rem = collected_amount
        for l in list(targets):
            if rem <= 0.001:
                break
            current_debt = l.get("debt", 0.0)
            pay = min(rem, current_debt)
            new_debt = max(0.0, round(current_debt - pay, 2))
            l["debt"] = new_debt
            l["repaid_amount"] = round(l.get("repaid_amount", 0.0) + pay, 2)
            rem = round(rem - pay, 2)

            if new_debt <= 0.01:
                if l in self.loans.get(debtor_id, []):
                    self.loans[debtor_id].remove(l)

        if debtor_id in self.loans and len(self.loans[debtor_id]) == 0:
            del self.loans[debtor_id]

        # Проверяем, закрыты ли все просроченные долги заемщика
        has_overdue = self.has_overdue_loan(debtor_id)
        is_fully_closed = not has_overdue
        if is_fully_closed:
            coll["contracts_closed"] = coll.get("contracts_closed", 0) + 1
            self.update_collector_rank(collector_id)
            coll["active_contract"] = None

        self.save_data()
        return collector_share, mfi_share, is_fully_closed

