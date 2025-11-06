"""Менеджер состояния игр"""
import json
import logging
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
        
        GameStateManager._initialized = True
    
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
                    self._save_games()
            else:
                self.games = {}
                self._save_games()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in games file: {e}. Resetting to empty.")
            self.games = {}
            self._save_games()
        except Exception as e:
            logger.error(f"Error loading games: {e}")
            self.games = {}
    
    def _save_games(self):
        try:
            with open(self.games_file, 'w', encoding='utf-8') as f:
                json.dump(self.games, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving games: {e}", exc_info=True)
    
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
