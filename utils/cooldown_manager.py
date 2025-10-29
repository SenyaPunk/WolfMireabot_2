"""Модуль для управления кулдаунами команд."""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class CooldownManager:
    def __init__(self, cooldown_file: str = "cooldowns.json"):
        data_dir = Path.cwd() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        cooldown_path = Path(cooldown_file)
        if not cooldown_path.is_absolute():
            cooldown_path = data_dir / cooldown_path

        self.cooldown_file: Path = cooldown_path
        self.cooldowns: Dict[str, Any] = {}
        self.load_cooldowns()

    def load_cooldowns(self):
        try:
            if self.cooldown_file.exists():
                with self.cooldown_file.open('r', encoding='utf-8') as f:
                    self.cooldowns = json.load(f)
                    logger.info(f"Загружено {len(self.cooldowns)} кулдаунов из {self.cooldown_file}")
            else:
                logger.info(f"Файл кулдаунов {self.cooldown_file} не найден, создаем новый")
                self.save_cooldowns()
        except Exception as e:
            logger.error(f"Ошибка загрузки кулдаунов: {e}")
            self.cooldowns = {}

    def save_cooldowns(self):
        try:
            with self.cooldown_file.open('w', encoding='utf-8') as f:
                json.dump(self.cooldowns, f, ensure_ascii=False, indent=2)
            logger.debug(f"Сохранено {len(self.cooldowns)} кулдаунов в {self.cooldown_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения кулдаунов: {e}")

    def check_cooldown(self, key: str, cooldown_seconds: float) -> Optional[float]:
        self.load_cooldowns()
        
        if key not in self.cooldowns:
            return None
        
        last_time = self.cooldowns[key].get("last_time", 0)
        current_time = time.time()
        time_passed = current_time - last_time
        
        if time_passed >= cooldown_seconds:
            return None
        
        return cooldown_seconds - time_passed

    def set_cooldown(self, key: str):
        self.load_cooldowns()
        
        if key not in self.cooldowns:
            self.cooldowns[key] = {}
        
        self.cooldowns[key]["last_time"] = time.time()
        self.save_cooldowns()

    def get_data(self, key: str) -> Dict[str, Any]:
        self.load_cooldowns()
        return self.cooldowns.get(key, {})

    def set_data(self, key: str, data: Dict[str, Any]):
        self.load_cooldowns()
        self.cooldowns[key] = data
        self.save_cooldowns()

    def delete_data(self, key: str):
        self.load_cooldowns()
        if key in self.cooldowns:
            del self.cooldowns[key]
            self.save_cooldowns()
