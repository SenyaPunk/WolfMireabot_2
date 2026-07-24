"""Менеджер состояния игр"""
import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class GameStateManager:
    _instance = None
    _initialized = False
    
    def __new__(cls, games_file: str = "games.json"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, games_file: str = "games.json"):
        if self._initialized:
            return
            
        if not Path(games_file).is_absolute():
            data_dir = Path.cwd() / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            games_file = data_dir / games_file
        
        self.games_file = Path(games_file)
        self.games: Dict[str, Any] = {}
        self._load_games()
        
        # Очередь и фоновый поток для неблокирующей и безопасной записи на диск
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(target=self._bg_writer, daemon=True)
        self._write_thread.start()
        
        GameStateManager._initialized = True
    
    def _bg_writer(self):
        while True:
            data = self._write_queue.get()
            if data is None:
                break
            try:
                # Атомарная запись во временный файл с последующей заменой основного файла
                temp_file = self.games_file.with_suffix(".tmp")
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # Повторяем попытку замены файла при блокировках Windows ( WinError 5 / WinError 32 )
                for attempt in range(5):
                    try:
                        temp_file.replace(self.games_file)
                        break
                    except PermissionError:
                        if attempt == 4:
                            raise
                        time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка сохранения игр в фоновом потоке: {e}", exc_info=True)
            finally:
                self._write_queue.task_done()

    def _load_games(self):
        try:
            if self.games_file.exists():
                file_content = self.games_file.read_text(encoding='utf-8').strip()
                if file_content:
                    self.games = json.loads(file_content)
                    logger.info(f"Loaded {len(self.games)} active games")
                else:
                    logger.info("Games file is empty, initializing with empty dict")
                    self.games = {}
                    # Для первой инициализации пишем синхронно
                    with open(self.games_file, 'w', encoding='utf-8') as f:
                        json.dump(self.games, f, ensure_ascii=False, indent=2)
            else:
                self.games = {}
                # Для первой инициализации пишем синхронно
                with open(self.games_file, 'w', encoding='utf-8') as f:
                    json.dump(self.games, f, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in games file: {e}. Resetting to empty.")
            self.games = {}
            with open(self.games_file, 'w', encoding='utf-8') as f:
                json.dump(self.games, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error loading games: {e}")
            self.games = {}
    
    def _save_games(self):
        # Отправляем снимок состояния игр в очередь записи
        snapshot = self.games.copy()
        self._write_queue.put(snapshot)
    
    def create_game(self, game_key: str, game_data: Dict[str, Any]):
        self.games[game_key] = game_data
        self._save_games()
        logger.info(f"Created game: {game_key}")
    
    def get_game(self, game_key: str) -> Optional[Dict[str, Any]]:
        return self.games.get(game_key)
    
    def update_game(self, game_key: str, game_data: Dict[str, Any]):
        if game_key in self.games:
            self.games[game_key] = game_data
            self._save_games()
            logger.info(f"Updated game: {game_key}")
    
    def delete_game(self, game_key: str):
        try:
            if game_key in self.games:
                logger.info(f"Deleting game {game_key} from memory...")
                del self.games[game_key]
                logger.info(f"Game {game_key} deleted from memory, saving to file...")
                self._save_games()
                logger.info(f"Verified: Game {game_key} successfully deleted")
            else:
                logger.warning(f"Attempted to delete non-existent game: {game_key}")
        except Exception as e:
            logger.error(f"Error in delete_game for {game_key}: {e}", exc_info=True)
            raise
    
    def game_exists(self, game_key: str) -> bool:
        return game_key in self.games
    
    def get_all_games(self) -> Dict[str, Any]:
        return self.games.copy()
