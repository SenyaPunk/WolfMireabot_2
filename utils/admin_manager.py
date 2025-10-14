"""Модуль для управления администраторами бота."""
import json
import os
import logging
from typing import Set

logger = logging.getLogger(__name__)

class AdminManager:
    def __init__(self, admin_file: str = "admins.json"):
        self.admin_file = admin_file
        self.admins: Set[int] = set()
        self.owner_id: int = int(os.getenv('OWNER_ID', '0'))
        self.load_admins()
    
    def load_admins(self):
        try:
            if os.path.exists(self.admin_file):
                with open(self.admin_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.admins = set(data.get('admins', []))
                    logger.info(f"Загружено {len(self.admins)} администраторов")
            else:
                logger.info("Файл администраторов не найден, создаем новый")
                self.save_admins()
        except Exception as e:
            logger.error(f"Ошибка загрузки администраторов: {e}")
            self.admins = set()
    
    def save_admins(self):
        try:
            with open(self.admin_file, 'w', encoding='utf-8') as f:
                json.dump({'admins': list(self.admins)}, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.admins)} администраторов")
        except Exception as e:
            logger.error(f"Ошибка сохранения администраторов: {e}")
    
    def is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id
    
    def is_admin(self, user_id: int) -> bool:
        self.load_admins()
        return user_id in self.admins or self.is_owner(user_id)
    
    def add_admin(self, user_id: int) -> bool:
        self.load_admins()
        if user_id not in self.admins:
            self.admins.add(user_id)
            self.save_admins()
            logger.info(f"Добавлен администратор: {user_id}")
            return True
        return False
    
    def remove_admin(self, user_id: int) -> bool:
        self.load_admins()
        if user_id in self.admins:
            self.admins.remove(user_id)
            self.save_admins()
            logger.info(f"Удален администратор: {user_id}")
            return True
        return False
    
    def get_admins(self) -> list:
        self.load_admins()
        return list(self.admins)
