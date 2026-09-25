"""Модуль для управления системой рабства."""
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.economy_manager import EconomyManager

logger = logging.getLogger(__name__)


class SlaveManager:
    _instance = None
    _initialized = False

    def __new__(cls, slaves_file: str = "slaves.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, slaves_file: str = "slaves.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        slaves_path = Path(slaves_file)
        if not slaves_path.is_absolute():
            slaves_path = data_dir / slaves_path

        self.slaves_file: Path = slaves_path
        self.slaves: Dict[int, Dict[str, Any]] = {}
        self.slave_slots: Dict[int, int] = {}
        self.price_penalties: Dict[int, float] = {}
        self.load_slaves()

        # Очередь и фоновый поток для безопасной записи на диск
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        self.economy_manager = EconomyManager()
        SlaveManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.slaves_file.with_suffix(".tmp")
                serializable_slaves = {str(k): v for k, v in data.get("slaves", {}).items()}
                serializable_slots = {str(k): v for k, v in data.get("slave_slots", {}).items()}
                serializable_penalties = {str(k): v for k, v in data.get("price_penalties", {}).items()}
                with temp_file.open("w", encoding="utf-8") as f:
                    json.dump({
                        "slaves": serializable_slaves,
                        "slave_slots": serializable_slots,
                        "price_penalties": serializable_penalties
                    }, f, ensure_ascii=False, indent=2)

                for attempt in range(5):
                    try:
                        temp_file.replace(self.slaves_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения системы рабства в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_slaves(self):
        try:
            if self.slaves_file.exists():
                with self.slaves_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_slaves = data.get("slaves", {})
                    self.slaves = {int(k): v for k, v in raw_slaves.items()}
                    raw_slots = data.get("slave_slots", {})
                    self.slave_slots = {int(k): int(v) for k, v in raw_slots.items()}
                    raw_penalties = data.get("price_penalties", {})
                    self.price_penalties = {int(k): float(v) for k, v in raw_penalties.items()}
                    logger.info(f"Загружено {len(self.slaves)} записей о рабах и {len(self.price_penalties)} уценок из {self.slaves_file}")
            else:
                logger.info(f"Файл рабства {self.slaves_file} не найден, создаем новый")
                serializable_slaves = {str(k): v for k, v in self.slaves.items()}
                serializable_slots = {str(k): v for k, v in self.slave_slots.items()}
                serializable_penalties = {str(k): v for k, v in self.price_penalties.items()}
                with self.slaves_file.open("w", encoding="utf-8") as f:
                    json.dump({
                        "slaves": serializable_slaves,
                        "slave_slots": serializable_slots,
                        "price_penalties": serializable_penalties
                    }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка загрузки файлов рабства: {e}")
            self.slaves = {}
            self.slave_slots = {}
            self.price_penalties = {}

    def save_slaves(self):
        snapshot = {
            "slaves": self.slaves.copy(),
            "slave_slots": self.slave_slots.copy(),
            "price_penalties": self.price_penalties.copy()
        }
        self._write_queue.put(snapshot)

    def get_max_slaves(self, owner_id: int) -> int:
        return self.slave_slots.get(owner_id, 1)

    def set_max_slaves(self, owner_id: int, slots: int):
        self.slave_slots[owner_id] = max(1, slots)
        self.save_slaves()

    def get_user_price(self, user_id: int) -> float:
        """
        Рассчитывает рыночную стоимость человека.
        Формула:
        Base = 1000 + Balance * 1.3
        Discount = (Overdue_Debt * 0.80) + Accumulated_Default_Penalty
        Price = max(50.0, Base - Discount)
        """
        balance = self.economy_manager.get_balance(user_id)
        base_price = 1000.0 + balance * 1.3

        # Снижение стоимости из-за долгов и неплатежеспособности
        from utils.loan_manager import LoanManager
        loan_mgr = LoanManager()
        overdue_debt = loan_mgr.get_total_overdue_debt(user_id)
        accumulated_penalty = self.price_penalties.get(user_id, 0.0)

        discount = (overdue_debt * 0.80) + accumulated_penalty
        final_price = max(50.0, round(base_price - discount, 2))
        return final_price

    def get_price_discount(self, user_id: int) -> float:
        """Возвращает сумму, на которую была снижена стоимость пользователя из-за долгов."""
        balance = self.economy_manager.get_balance(user_id)
        base_price = 1000.0 + balance * 1.3
        actual_price = self.get_user_price(user_id)
        return max(0.0, round(base_price - actual_price, 2))

    def apply_price_penalty(self, user_id: int, debt_amount: float) -> Tuple[float, float]:
        """
        Применяет штрафное снижение стоимости к должнику-банкроту.
        Формула: уценка на max(50, min(300, debt_amount * 0.35)) монет.
        Возвращает (новая_цена, размер_уценки).
        """
        old_price = self.get_user_price(user_id)
        penalty_add = round(max(50.0, min(300.0, debt_amount * 0.35)), 2)
        self.price_penalties[user_id] = round(self.price_penalties.get(user_id, 0.0) + penalty_add, 2)
        self.save_slaves()
        new_price = self.get_user_price(user_id)
        discount = round(old_price - new_price, 2)
        logger.info(f"Снижена стоимость пользователя {user_id}: {old_price} -> {new_price} (уценка: {discount})")
        return new_price, discount

    def reset_price_penalty(self, user_id: int):
        """Сбрасывает штрафную уценку стоимости (при покупке в рабство или закрытии долгов)."""
        if user_id in self.price_penalties:
            del self.price_penalties[user_id]
            self.save_slaves()

    def get_slave_data(self, slave_id: int) -> Optional[Dict[str, Any]]:
        return self.slaves.get(slave_id)

    def get_owner(self, slave_id: int) -> Optional[int]:
        slave_data = self.get_slave_data(slave_id)
        if slave_data:
            return slave_data.get("owner_id")
        return None

    def get_purchase_price(self, slave_id: int) -> Optional[float]:
        slave_data = self.get_slave_data(slave_id)
        if slave_data:
            return slave_data.get("purchase_price")
        return None

    def get_slaves_of(self, owner_id: int) -> List[Tuple[int, Dict[str, Any]]]:
        result = []
        for s_id, s_data in self.slaves.items():
            if s_data.get("owner_id") == owner_id:
                result.append((s_id, s_data))
        return result

    def is_in_master_chain(self, buyer_id: int, target_id: int) -> bool:
        """
        Проверяет, является ли target_id хозяином buyer_id или любого его хозяина выше по цепочке.
        Или если buyer_id == target_id.
        Служит для предотвращения покупки своего владельца / зацикливания.
        """
        if buyer_id == target_id:
            return True

        current = buyer_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            owner = self.get_owner(current)
            if owner == target_id:
                return True
            current = owner

        return False

    def buy_slave(self, slave_id: int, owner_id: int, price: float) -> bool:
        self.slaves[slave_id] = {
            "owner_id": owner_id,
            "purchase_price": round(price, 2),
            "bought_at": time.time(),
            "total_earned": 0.0,
        }
        self.save_slaves()
        logger.info(f"Пользователь {owner_id} купил раба {slave_id} за {price}")
        return True

    def free_slave(self, slave_id: int) -> bool:
        if slave_id in self.slaves:
            del self.slaves[slave_id]
            self.save_slaves()
            logger.info(f"Раб {slave_id} был освобожден")
            return True
        return False

    def process_slave_earnings(
        self, slave_id: int, gross_profit: float, percent: float = 0.30
    ) -> Tuple[float, float, Optional[int]]:
        """
        Обрабатывает прибыль раба.
        Если раб принадлежит хозяину, отбирает percent (по умолчанию 30%) в пользу хозяина.
        Возвращает (награда_раба, отчисление_хозяину, owner_id).
        """
        owner_id = self.get_owner(slave_id)
        if not owner_id or gross_profit <= 0:
            return gross_profit, 0.0, None

        master_share = round(gross_profit * percent, 2)
        slave_share = round(gross_profit - master_share, 2)

        # Начисляем долю хозяину
        self.economy_manager.add_money(owner_id, master_share)

        # Обновляем статистику заработанного этим рабом для хозяина
        if slave_id in self.slaves:
            self.slaves[slave_id]["total_earned"] = round(
                self.slaves[slave_id].get("total_earned", 0.0) + master_share, 2
            )
            self.save_slaves()

        logger.info(
            f"Раб {slave_id} принес хозяину {owner_id} доход {master_share} монет ({percent*100}% от {gross_profit})"
        )

        return slave_share, master_share, owner_id

    def whip_slave(self, slave_id: int, owner_id: int, chat_id: int) -> bool:
        """Устанавливает статус порки для раба."""
        if slave_id in self.slaves:
            self.slaves[slave_id]["is_whipped"] = True
            self.slaves[slave_id]["last_whip_tax_time"] = time.time()
            self.slaves[slave_id]["whipped_by"] = owner_id
            self.slaves[slave_id]["whip_chat_id"] = chat_id
            self.save_slaves()
            logger.info(f"Раб {slave_id} отхлестан хозяином {owner_id} в чате {chat_id}")
            return True
        return False

    def unwhip_slave(self, slave_id: int) -> bool:
        """Снимает статус порки с раба."""
        slave_data = self.get_slave_data(slave_id)
        if slave_data and slave_data.get("is_whipped"):
            slave_data["is_whipped"] = False
            slave_data.pop("last_whip_tax_time", None)
            slave_data.pop("whipped_by", None)
            slave_data.pop("whip_chat_id", None)
            self.save_slaves()
            logger.info(f"С раба {slave_id} снято состояние порки.")
            return True
        return False

    def is_whipped(self, slave_id: int) -> bool:
        """Проверяет, находится ли раб под поркой."""
        slave_data = self.get_slave_data(slave_id)
        if slave_data:
            return bool(slave_data.get("is_whipped", False))
        return False

    def get_whipped_slaves(self) -> List[Tuple[int, Dict[str, Any]]]:
        """Возвращает список всех отхлестанных рабов."""
        result = []
        for s_id, s_data in self.slaves.items():
            if s_data.get("is_whipped"):
                result.append((s_id, s_data))
        return result

