"""Модуль для управления кулдаунами команд."""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class CooldownManager:
    _instance = None
    _initialized = False
    
    def __new__(cls, cooldown_file: str = "cooldowns.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, cooldown_file: str = "cooldowns.json"):
        if self._initialized:
            return
            
        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        cooldown_path = Path(cooldown_file)
        if not cooldown_path.is_absolute():
            cooldown_path = data_dir / cooldown_path

        self.cooldown_file: Path = cooldown_path
        self.cooldowns: Dict[str, Any] = {}
        self.load_cooldowns()
        self._modified = False
        
        CooldownManager._initialized = True

    def load_cooldowns(self):
        try:
            if self.cooldown_file.exists():
                file_content = self.cooldown_file.read_text(encoding='utf-8').strip()
                if file_content:
                    self.cooldowns = json.loads(file_content)
                    logger.info(f"Загружено {len(self.cooldowns)} кулдаунов из {self.cooldown_file}")
                else:
                    logger.info("Cooldowns file is empty, initializing with empty dict")
                    self.cooldowns = {}
                    self.save_cooldowns()
            else:
                logger.info(f"Файл кулдаунов {self.cooldown_file} не найден, создаем новый")
                self.save_cooldowns()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in cooldowns file: {e}. Resetting to empty.")
            self.cooldowns = {}
            self.save_cooldowns()
        except Exception as e:
            logger.error(f"Ошибка загрузки кулдаунов: {e}")
            self.cooldowns = {}

    def save_cooldowns(self):
        try:
            with self.cooldown_file.open('w', encoding='utf-8') as f:
                json.dump(self.cooldowns, f, ensure_ascii=False, indent=2)
            logger.debug(f"Сохранено {len(self.cooldowns)} кулдаунов в {self.cooldown_file}")
            self._modified = False
        except Exception as e:
            logger.error(f"Ошибка сохранения кулдаунов: {e}")

    def check_cooldown(self, key: str, cooldown_seconds: float) -> Optional[float]:
        
        if key not in self.cooldowns:
            return None
        
        last_time = self.cooldowns[key].get("last_time", 0)
        current_time = time.time()
        time_passed = current_time - last_time
        
        if time_passed >= cooldown_seconds:
            return None
        
        return cooldown_seconds - time_passed

    def set_cooldown(self, key: str):
        
        if key not in self.cooldowns:
            self.cooldowns[key] = {}
        
        self.cooldowns[key]["last_time"] = time.time()
        self._modified = True
        self.save_cooldowns()

    def get_data(self, key: str) -> Dict[str, Any]:
        return self.cooldowns.get(key, {})

    def set_data(self, key: str, data: Dict[str, Any]):
        self.cooldowns[key] = data
        self._modified = True
        self.save_cooldowns()

    def delete_data(self, key: str):
        if key in self.cooldowns:
            del self.cooldowns[key]
            self._modified = True
            self.save_cooldowns()

    def reset_user_cooldowns(self, user_id: int, cd_type: str = "all") -> int:
        """Сбрасывает кулдауны пользователя. Возвращает количество удаленных записей."""
        keys_to_delete = []
        user_str = str(user_id)
        
        for key in list(self.cooldowns.keys()):
            if f":{user_id}:" in key or key.endswith(f":{user_id}") or key.startswith(f"freelance_session:{user_id}"):
                if cd_type == "all":
                    keys_to_delete.append(key)
                elif cd_type in key:
                    keys_to_delete.append(key)
                    
        count = len(keys_to_delete)
        for k in keys_to_delete:
            del self.cooldowns[k]
            
        if count > 0:
            self._modified = True
            self.save_cooldowns()
            
        return count
