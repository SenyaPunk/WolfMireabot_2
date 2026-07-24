"""Модуль для управления донатами, бустами и покупками."""
import json
import logging
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Any, List

from utils.economy_manager import EconomyManager
from utils.slave_manager import SlaveManager

logger = logging.getLogger(__name__)

# Определение донат-товаров
DONATE_ITEMS = {
    "coins_500": {
        "title": "💰 500 монет",
        "price_rub": 100,
        "description": "500 внутриигровых монет для ставок в мини-играх и покупки товаров.",
        "type": "coins",
        "value": 500
    },
    "coins_1000": {
        "title": "💎 1000 монет (скидка 5%)",
        "price_rub": 190,
        "description": "1000 внутриигровых монет. Экономия по сравнению с мелкими покупками.",
        "type": "coins",
        "value": 1000
    },
    "coins_3000": {
        "title": "🏆 3000 монет (скидка 8%)",
        "price_rub": 550,
        "description": "Крупный пакет 3000 монет для длительной игры и высокой активности.",
        "type": "coins",
        "value": 3000
    },
    "casino_boost": {
        "title": "🎰 Буст шансов в казино",
        "price_rub": 90,
        "description": "Повышает вероятность выигрыша во всех мини-играх («Казино»).",
        "type": "boost",
        "value": "casino"
    },
    "unlock_slots": {
        "title": "🔓 Открытие всех слотов рабства",
        "price_rub": 150,
        "description": "Разблокирует все 100 игровых слотов в системе «рабства».",
        "type": "unlock",
        "value": 100
    },
    "force_buy_slave": {
        "title": "👑 Купить любого участника",
        "price_rub": 300,
        "description": "Разблокирует 1 пропуск на покупку абсолютно любого участника чата в рабство.",
        "type": "pass",
        "value": 1
    }
}


class DonationManager:
    _instance = None
    _initialized = False

    def __new__(cls, donations_file: str = "donations.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, donations_file: str = "donations.json"):
        if self._initialized:
            return

        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        don_path = Path(donations_file)
        if not don_path.is_absolute():
            don_path = data_dir / don_path

        self.donations_file: Path = don_path
        self.user_perks: Dict[int, Dict[str, Any]] = {}
        self.orders: Dict[str, Dict[str, Any]] = {}

        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()

        self.load_data()

        self.economy_manager = EconomyManager()
        self.slave_manager = SlaveManager()

        DonationManager._initialized = True

    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                temp_file = self.donations_file.with_suffix(".tmp")
                serializable_perks = {str(k): v for k, v in data.get("perks", {}).items()}
                serializable_orders = data.get("orders", {})
                with temp_file.open("w", encoding="utf-8") as f:
                    json.dump({"perks": serializable_perks, "orders": serializable_orders}, f, ensure_ascii=False, indent=2)

                for attempt in range(5):
                    try:
                        temp_file.replace(self.donations_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения донатов в фоновом потоке: {e}")
            finally:
                self._write_queue.task_done()

    def load_data(self):
        try:
            if self.donations_file.exists():
                with self.donations_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_perks = data.get("perks", {})
                    self.user_perks = {int(k): v for k, v in raw_perks.items()}
                    self.orders = data.get("orders", {})
                    logger.info(f"Загружены донат-данные: {len(self.user_perks)} перков, {len(self.orders)} заказов")
            else:
                self.save_data()
        except Exception as e:
            logger.error(f"Ошибка загрузки донат-данных: {e}")
            self.user_perks = {}
            self.orders = {}

    def save_data(self):
        snapshot = {
            "perks": self.user_perks.copy(),
            "orders": self.orders.copy()
        }
        self._write_queue.put(snapshot)

    def _get_user_entry(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self.user_perks:
            self.user_perks[user_id] = {
                "casino_boost": False,
                "all_slots_unlocked": False,
                "force_buy_passes": 0
            }
        return self.user_perks[user_id]

    def has_casino_boost(self, user_id: int) -> bool:
        return self._get_user_entry(user_id).get("casino_boost", False)

    def activate_casino_boost(self, user_id: int):
        entry = self._get_user_entry(user_id)
        entry["casino_boost"] = True
        self.save_data()
        logger.info(f"Активирован казино буст для пользователя {user_id}")

    def is_all_slots_unlocked(self, user_id: int) -> bool:
        return self._get_user_entry(user_id).get("all_slots_unlocked", False)

    def unlock_all_slots(self, user_id: int):
        entry = self._get_user_entry(user_id)
        entry["all_slots_unlocked"] = True
        self.slave_manager.set_max_slaves(user_id, 100)
        self.save_data()
        logger.info(f"Разблокированы все слоты рабства для пользователя {user_id}")

    def get_force_buy_passes(self, user_id: int) -> int:
        return self._get_user_entry(user_id).get("force_buy_passes", 0)

    def add_force_buy_pass(self, user_id: int, count: int = 1):
        entry = self._get_user_entry(user_id)
        entry["force_buy_passes"] = entry.get("force_buy_passes", 0) + count
        self.save_data()
        logger.info(f"Добавлено {count} пропусков принудительной покупки раба пользователю {user_id}")

    def use_force_buy_pass(self, user_id: int) -> bool:
        current = self.get_force_buy_passes(user_id)
        if current > 0:
            entry = self._get_user_entry(user_id)
            entry["force_buy_passes"] = current - 1
            self.save_data()
            logger.info(f"Пользователь {user_id} использовал 1 пропуск принудительной покупки раба")
            return True
        return False

    def create_order(self, user_id: int, item_id: str) -> Optional[Dict[str, Any]]:
        if item_id not in DONATE_ITEMS:
            return None

        item = DONATE_ITEMS[item_id]
        order_id = str(uuid.uuid4())[:12]
        order_data = {
            "order_id": order_id,
            "user_id": user_id,
            "item_id": item_id,
            "title": item["title"],
            "price_rub": item["price_rub"],
            "status": "pending",
            "created_at": time.time()
        }
        self.orders[order_id] = order_data
        self.save_data()
        return order_data

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.orders.get(order_id)

    def set_order_invoice_id(self, order_id: str, invoice_id: str):
        order = self.get_order(order_id)
        if order:
            order["crystalpay_id"] = invoice_id
            self.save_data()

    def complete_order(self, order_id: str) -> bool:
        order = self.get_order(order_id)
        if not order or order.get("status") == "completed":
            return False

        order["status"] = "completed"
        order["completed_at"] = time.time()
        user_id = order["user_id"]
        item_id = order["item_id"]

        item = DONATE_ITEMS.get(item_id)
        if item:
            item_type = item.get("type")
            if item_type == "coins":
                self.economy_manager.add_money(user_id, item["value"])
            elif item_type == "boost" and item["value"] == "casino":
                self.activate_casino_boost(user_id)
            elif item_type == "unlock":
                self.unlock_all_slots(user_id)
            elif item_type == "pass":
                self.add_force_buy_pass(user_id, item["value"])

        self.save_data()
        logger.info(f"Заказ {order_id} успешно исполнен для пользователя {user_id}")
        return True
