"""Модуль для управления экономикой бота."""
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class EconomyManager:
    _instance = None
    _initialized = False
    
    def __new__(cls, economy_file: str = "economy.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, economy_file: str = "economy.json"):
        if self._initialized:
            return
            
        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        econ_path = Path(economy_file)
        if not econ_path.is_absolute():
            econ_path = data_dir / econ_path

        self.economy_file: Path = econ_path
        self.balances: Dict[int, float] = {}
        self.load_balances()
        
        EconomyManager._initialized = True

    def load_balances(self):
        try:
            if self.economy_file.exists():
                with self.economy_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.balances = {int(k): float(v) for k, v in data.get('balances', {}).items()}
                    logger.info(f"Загружено {len(self.balances)} балансов из {self.economy_file}")
            else:
                logger.info(f"Файл экономики {self.economy_file} не найден, создаем новый")
                self.save_balances()
        except Exception as e:
            logger.error(f"Ошибка загрузки балансов: {e}")
            self.balances = {}

    def save_balances(self):
        try:
            serializable = {str(k): v for k, v in self.balances.items()}
            with self.economy_file.open('w', encoding='utf-8') as f:
                json.dump({'balances': serializable}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения балансов: {e}")

    def get_balance(self, user_id: int) -> float:
        return float(self.balances.get(user_id, 0.0))

    def set_balance(self, user_id: int, amount: float):
        self.balances[user_id] = round(float(amount), 2)
        self.save_balances()

    def add_money(self, user_id: int, amount: float) -> float:
        current = float(self.balances.get(user_id, 0.0))
        new_balance = round(current + float(amount), 2)
        self.balances[user_id] = new_balance
        self.save_balances()
        logger.debug(f"Добавлено {amount} пользователю {user_id}. Новый баланс: {new_balance}")
        return new_balance

    def remove_money(self, user_id: int, amount: float) -> float:
        current = float(self.balances.get(user_id, 0.0))
        new_balance = round(current - float(amount), 2)
        self.balances[user_id] = new_balance
        self.save_balances()
        logger.debug(f"Убрано {amount} у пользователя {user_id}. Новый баланс: {new_balance}")
        return new_balance

    def get_top_users(self, limit: int = 10) -> List[Tuple[int, float]]:
        sorted_balances = sorted(self.balances.items(), key=lambda x: x[1], reverse=True)
        return sorted_balances[:limit]
