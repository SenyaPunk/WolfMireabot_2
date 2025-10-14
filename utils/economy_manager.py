"""Модуль для управления экономикой бота."""
import json
import os
import logging
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

class EconomyManager:
    def __init__(self, economy_file: str = "economy.json"):
        self.economy_file = economy_file
        self.balances: Dict[int, float] = {}
        self.load_balances()
    
    def load_balances(self):
        try:
            if os.path.exists(self.economy_file):
                with open(self.economy_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем ключи обратно в int
                    self.balances = {int(k): float(v) for k, v in data.get('balances', {}).items()}
                    logger.info(f"Загружено {len(self.balances)} балансов")
            else:
                logger.info("Файл экономики не найден, создаем новый")
                self.save_balances()
        except Exception as e:
            logger.error(f"Ошибка загрузки балансов: {e}")
            self.balances = {}
    
    def save_balances(self):
        try:
            with open(self.economy_file, 'w', encoding='utf-8') as f:
                json.dump({'balances': self.balances}, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.balances)} балансов")
        except Exception as e:
            logger.error(f"Ошибка сохранения балансов: {e}")
    
    def get_balance(self, user_id: int) -> float:
        """Получить баланс пользователя."""
        self.load_balances()
        return self.balances.get(user_id, 0.0)
    
    def set_balance(self, user_id: int, amount: float):
        """Установить баланс пользователя."""
        self.load_balances()
        self.balances[user_id] = round(amount, 2)
        self.save_balances()
    
    def add_money(self, user_id: int, amount: float) -> float:
        """Добавить деньги пользователю."""
        self.load_balances()
        current = self.balances.get(user_id, 0.0)
        new_balance = current + amount
        self.balances[user_id] = round(new_balance, 2)
        self.save_balances()
        logger.info(f"Добавлено {amount} пользователю {user_id}. Новый баланс: {new_balance}")
        return new_balance
    
    def remove_money(self, user_id: int, amount: float) -> float:
        """Убрать деньги у пользователя."""
        self.load_balances()
        current = self.balances.get(user_id, 0.0)
        new_balance = current - amount
        self.balances[user_id] = round(new_balance, 2)
        self.save_balances()
        logger.info(f"Убрано {amount} у пользователя {user_id}. Новый баланс: {new_balance}")
        return new_balance
    
    def get_top_users(self, limit: int = 10) -> List[Tuple[int, float]]:
        """Получить топ пользователей по балансу."""
        self.load_balances()
        sorted_balances = sorted(self.balances.items(), key=lambda x: x[1], reverse=True)
        return sorted_balances[:limit]
