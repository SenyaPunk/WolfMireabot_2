"""Обработчик платежей и зачисления бонусов."""
import logging
from typing import Optional
from utils.economy_manager import EconomyManager

logger = logging.getLogger(__name__)


class DonateManager:
    
    DONATE_TYPES = {
        "500coins": {
            "coins": 500,
            "amount": 100,
            "description": "500 монет"
        },
        "1000coins": {
            "coins": 1000,
            "amount": 190,
            "description": "1000 монет"
        },
        "3000coins": {
            "coins": 3000,
            "amount": 550,
            "description": "3000 монет"
        },
        "blackjack_boost": {
            "boost_type": "blackjack",
            "amount": 90,
            "description": "Буст шансов в блекджеке",
            "duration_days": 7
        },
        "slavery_slots": {
            "unlock_type": "slavery_slots",
            "amount": 150,
            "description": "Открытие всех слотов рабства",
            "permanent": True 
        }
    }
    
    def __init__(self):
        self.economy_manager = EconomyManager()
    
    def process_payment(self, user_id: int, donate_type: str) -> Optional[dict]:
        if donate_type not in self.DONATE_TYPES:
            logger.error(f"Неизвестный тип доната: {donate_type}")
            return None
        
        donate_info = self.DONATE_TYPES[donate_type]
        
        # Монеты
        if "coins" in donate_info:
            coins = donate_info["coins"]
            new_balance = self.economy_manager.add_money(user_id, coins)
            
            logger.info(
                f"Зачислено {coins} монет пользователю {user_id}. "
                f"Новый баланс: {new_balance}"
            )
            
            return {
                "type": "coins",
                "amount": coins,
                "new_balance": new_balance,
                "description": donate_info["description"]
            }
        
        # Буст
        if "boost_type" in donate_info:
            # TODO: Реализовать систему хранения бустов в базе данных
            logger.info(
                f"Активирован буст {donate_info['boost_type']} "
                f"для пользователя {user_id} на {donate_info.get('duration_days', 0)} дней"
            )
            
            return {
                "type": donate_info["boost_type"],
                "description": donate_info["description"],
                "duration_days": donate_info.get("duration_days")
            }
        
        # Слоты рабства 
        if "unlock_type" in donate_info:
            # TODO: Реализовать систему хранения разблокировок в базе данных
            logger.info(
                f"Активирована разблокировка {donate_info['unlock_type']} "
                f"для пользователя {user_id}"
            )
            
            return {
                "type": donate_info["unlock_type"],
                "description": donate_info["description"],
                "permanent": donate_info.get("permanent", False)
            }
        
        logger.error(f"Неизвестный формат доната: {donate_type}")
        return None
    
    def get_donate_info(self, donate_type: str) -> Optional[dict]:
        return self.DONATE_TYPES.get(donate_type)
