"""Модуль для управления администраторами бота."""
import json
import os
import logging
from pathlib import Path
from typing import Set, List

logger = logging.getLogger(__name__)

class AdminManager:
    def __init__(self, admin_file: str = "admins.json"):
        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        admin_path = Path(admin_file)
        if not admin_path.is_absolute():
            admin_path = data_dir / admin_path

        self.admin_file: Path = admin_path
        self.admins: Set[int] = set()
        try:
            self.owner_id: int = int(os.getenv('OWNER_ID', '0'))
        except Exception:
            self.owner_id = 0
        self.load_admins()

    def load_admins(self):
        try:
            if self.admin_file.exists():
                with self.admin_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.admins = set(int(x) for x in data.get('admins', []) if str(x).strip() != '')
                    logger.info(f"Загружено {len(self.admins)} администраторов из {self.admin_file}")
            else:
                logger.info(f"Файл администраторов {self.admin_file} не найден, создаем новый")
                self.save_admins()
        except Exception as e:
            logger.error(f"Ошибка загрузки администраторов: {e}")
            self.admins = set()

    def save_admins(self):
        try:
            with self.admin_file.open('w', encoding='utf-8') as f:
                json.dump({'admins': sorted(list(self.admins))}, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.admins)} администраторов в {self.admin_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения администраторов: {e}")

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.owner_id

    def is_admin(self, user_id: int) -> bool:
        self.load_admins()
        return user_id in self.admins or self.is_owner(user_id)

    def add_admin(self, user_id: int) -> bool:
        self.load_admins()
        if int(user_id) not in self.admins:
            self.admins.add(int(user_id))
            self.save_admins()
            logger.info(f"Добавлен администратор: {user_id}")
            return True
        return False

    def remove_admin(self, user_id: int) -> bool:
        self.load_admins()
        if int(user_id) in self.admins:
            self.admins.remove(int(user_id))
            self.save_admins()
            logger.info(f"Удален администратор: {user_id}")
            return True
        return False

    def get_admins(self) -> List[int]:
        self.load_admins()
        return sorted(list(self.admins))
