"""Модуль для хранения информации о пользователях."""
import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class UserStorage:
    _instance = None
    _initialized = False

    def __new__(cls, storage_file: str = "users.json"):
        if cls._instance is None:
            cls._instance = super(UserStorage, cls).__new__(cls)
        return cls._instance

    def __init__(self, storage_file: str = "users.json"):
        if not UserStorage._initialized:
            data_dir = Path.cwd() / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            storage_path = Path(storage_file)
            if not storage_path.is_absolute():
                storage_path = data_dir / storage_path

            self.storage_file: Path = storage_path
            self.users: Dict[str, int] = {}
            self.user_info: Dict[int, Dict] = {}
            self.load_users()
            UserStorage._initialized = True
            logger.info(f"UserStorage инициализирован, файл: {self.storage_file}")

    def load_users(self):
        try:
            if self.storage_file.exists():
                with self.storage_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = {k: int(v) for k, v in data.get('users', {}).items()}
                    self.user_info = {int(k): v for k, v in data.get('user_info', {}).items()}
                    logger.info(f"Загружено {len(self.users)} пользователей из {self.storage_file}")
            else:
                logger.info(f"Файл пользователей {self.storage_file} не найден, создаем новый")
                self.save_users()
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            self.users = {}
            self.user_info = {}

    def save_users(self):
        try:
            with self.storage_file.open('w', encoding='utf-8') as f:
                json.dump({
                    'users': self.users,
                    'user_info': {str(k): v for k, v in self.user_info.items()}
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(self.users)} пользователей в {self.storage_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")

    def add_user(self, user_id: int, username: Optional[str] = None,
                 first_name: Optional[str] = None, last_name: Optional[str] = None):
        updated = False
        user_data = {'username': username, 'first_name': first_name, 'last_name': last_name}

        if user_id not in self.user_info or self.user_info[user_id] != user_data:
            self.user_info[user_id] = user_data
            updated = True

        if username:
            if username not in self.users or self.users[username] != user_id:
                self.users[username] = user_id
                updated = True

        if updated:
            self.save_users()
            logger.info(f"Обновлена информация о пользователе: {user_id} (@{username})")

    def get_user_id(self, username: str) -> Optional[int]:
        username = username.lstrip('@')
        user_id = self.users.get(username)
        logger.info(f"Поиск user_id для @{username}: {'найден' if user_id else 'не найден'} ({user_id})")
        return user_id

    def get_user_info(self, user_id: int) -> Optional[Dict]:
        return self.user_info.get(user_id)

    def get_display_name(self, user_id: int) -> str:
        info = self.get_user_info(user_id)
        if not info:
            return f"ID: {user_id}"
        if info.get('username'):
            return f"@{info['username']}"
        elif info.get('first_name'):
            full_name = info['first_name']
            if info.get('last_name'):
                full_name += f" {info['last_name']}"
            return full_name
        else:
            return f"ID: {user_id}"
