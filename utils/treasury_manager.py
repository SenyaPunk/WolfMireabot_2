"""Модуль для управления Государственной Казной Волка и фондом ограблений."""
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

DEFAULT_INITIAL_BALANCE = 15000.0
DEFAULT_RESERVE = 1000.0
MAX_HISTORY_ENTRIES = 25
MAX_HALL_ENTRIES = 10


class TreasuryManager:
    _instance = None
    _initialized = False

    def __new__(cls, treasury_file: str = "treasury.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, treasury_file: str = "treasury.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        t_path = Path(treasury_file)
        if not t_path.is_absolute():
            t_path = data_dir / t_path

        self.treasury_file: Path = t_path
        self.balance: float = DEFAULT_INITIAL_BALANCE
        self.reserve: float = DEFAULT_RESERVE
        self.total_collected: float = DEFAULT_INITIAL_BALANCE
        self.total_robbed: float = 0.0
        self.heist_cooldown_until: float = 0.0
        self.recent_transactions: List[Dict[str, Any]] = []
        self.hall_of_fame: List[Dict[str, Any]] = []

        # Очередь и фоновый поток для неблокирующей и безопасной записи на диск
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        self.load_data()

        TreasuryManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.treasury_file.with_suffix(".tmp")
                with temp_file.open('w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                for attempt in range(5):
                    try:
                        temp_file.replace(self.treasury_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения данных казны в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_data(self):
        try:
            if self.treasury_file.exists():
                with self.treasury_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.balance = float(data.get("balance", DEFAULT_INITIAL_BALANCE))
                    self.reserve = float(data.get("reserve", DEFAULT_RESERVE))
                    self.total_collected = float(data.get("total_collected", self.balance))
                    self.total_robbed = float(data.get("total_robbed", 0.0))
                    self.heist_cooldown_until = float(data.get("heist_cooldown_until", 0.0))
                    self.recent_transactions = data.get("recent_transactions", [])
                    self.hall_of_fame = data.get("hall_of_fame", [])
                    logger.info(f"Загружена Казна: баланс {self.balance:.2f} монет")
            else:
                logger.info(f"Файл казны {self.treasury_file} не найден, создаем начальный резерв")
                self.balance = DEFAULT_INITIAL_BALANCE
                self.reserve = DEFAULT_RESERVE
                self.total_collected = DEFAULT_INITIAL_BALANCE
                self.total_robbed = 0.0
                self.heist_cooldown_until = 0.0
                self.recent_transactions = [
                    {
                        "time": time.time(),
                        "amount": DEFAULT_INITIAL_BALANCE,
                        "type": "init",
                        "source": "reserve",
                        "desc": "Стартовый золотой запас Волка"
                    }
                ]
                self.hall_of_fame = []
                self.save_data()
        except Exception as e:
            logger.error(f"Ошибка загрузки данных казны: {e}")
            self.balance = DEFAULT_INITIAL_BALANCE
            self.reserve = DEFAULT_RESERVE

    def save_data(self):
        snapshot = {
            "balance": round(self.balance, 2),
            "reserve": round(self.reserve, 2),
            "total_collected": round(self.total_collected, 2),
            "total_robbed": round(self.total_robbed, 2),
            "heist_cooldown_until": self.heist_cooldown_until,
            "recent_transactions": self.recent_transactions[-MAX_HISTORY_ENTRIES:],
            "hall_of_fame": self.hall_of_fame[:MAX_HALL_ENTRIES]
        }
        self._write_queue.put(snapshot)

    def get_balance(self) -> float:
        """Возвращает текущий полный баланс казны."""
        return max(self.reserve, round(self.balance, 2))

    def get_robbable_amount(self) -> float:
        """Возвращает доступную для ограбления сумму (сверх резерва)."""
        return max(0.0, round(self.balance - self.reserve, 2))

    def add_to_treasury(self, amount: float, source: str = "general", description: str = "") -> float:
        """Пополняет казну с фиксацией источника."""
        if amount <= 0:
            return self.balance

        amt = round(float(amount), 2)
        self.balance = round(self.balance + amt, 2)
        self.total_collected = round(self.total_collected + amt, 2)

        entry = {
            "time": time.time(),
            "amount": amt,
            "type": "add",
            "source": source,
            "desc": description or f"Пополнение ({source})"
        }
        self.recent_transactions.append(entry)
        if len(self.recent_transactions) > MAX_HISTORY_ENTRIES:
            self.recent_transactions = self.recent_transactions[-MAX_HISTORY_ENTRIES:]

        self.save_data()
        logger.info(f"Казна пополнена на +{amt:.2f} монет (источник: {source}). Баланс: {self.balance:.2f}")
        return self.balance

    def take_from_treasury(
        self,
        amount: float,
        leader_id: int,
        leader_name: str,
        gang_names: Optional[List[str]] = None
    ) -> float:
        """Списывает украденную сумму из казны и записывает ограбление."""
        robbable = self.get_robbable_amount()
        actual_take = round(min(float(amount), robbable), 2)

        if actual_take <= 0:
            return 0.0

        self.balance = round(self.balance - actual_take, 2)
        self.total_robbed = round(self.total_robbed + actual_take, 2)

        participants = gang_names if gang_names else [leader_name]
        entry = {
            "time": time.time(),
            "amount": actual_take,
            "type": "rob",
            "source": "heist",
            "desc": f"Ограбление: {', '.join(participants)}"
        }
        self.recent_transactions.append(entry)

        hall_entry = {
            "leader_id": leader_id,
            "leader_name": leader_name,
            "gang_names": participants,
            "amount": actual_take,
            "time": time.time()
        }
        self.hall_of_fame.insert(0, hall_entry)
        if len(self.hall_of_fame) > MAX_HALL_ENTRIES:
            self.hall_of_fame = self.hall_of_fame[:MAX_HALL_ENTRIES]

        self.save_data()
        logger.info(f"Казна ограблена на {actual_take:.2f} монет бандой {participants}. Новый баланс: {self.balance:.2f}")
        return actual_take

    def set_heist_cooldown(self, seconds: int = 3600):
        """Устанавливает глобальный режим тревоги/ЧП на казну после налета."""
        self.heist_cooldown_until = time.time() + seconds
        self.save_data()

    def get_heist_cooldown_remaining(self) -> float:
        """Возвращает оставшееся время кулдауна на ограбление казны (в сек)."""
        rem = self.heist_cooldown_until - time.time()
        return max(0.0, rem)

    def get_security_level(self) -> Tuple[str, str, int]:
        """Возвращает информацию о текущей системе охраны в зависимости от объема казны."""
        bal = self.balance
        if bal < 10000:
            return ("🟢 Стандартный", "Базовая сигнализация МИРЭА и камеры", 1)
        elif bal < 30000:
            return ("🟡 Повышенный", "Лазерная паутина и сторожевые псы", 2)
        elif bal < 75000:
            return ("🟠 Усиленный", "Бронированная гермодверь и ЧОП «Волк»", 3)
        else:
            return ("🔴 Максимальный", "Квантовый шифр, турели и элитный спецназ", 4)

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает сводные данные о казне."""
        sec_level, sec_desc, sec_tier = self.get_security_level()
        return {
            "balance": round(self.balance, 2),
            "reserve": round(self.reserve, 2),
            "robbable": self.get_robbable_amount(),
            "total_collected": round(self.total_collected, 2),
            "total_robbed": round(self.total_robbed, 2),
            "security_level": sec_level,
            "security_desc": sec_desc,
            "security_tier": sec_tier,
            "cooldown_remaining": self.get_heist_cooldown_remaining(),
            "hall_of_fame": self.hall_of_fame[:5],
            "recent_transactions": self.recent_transactions[-5:]
        }
