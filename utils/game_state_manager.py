"""Менеджер состояния игр"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class GameStateManager:
    
    def __init__(self, games_file: str = "games.json"):
        if not Path(games_file).is_absolute():
            data_dir = Path.cwd() / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            games_file = data_dir / games_file
        
        self.games_file = Path(games_file)
        self.games: Dict[str, Any] = {}
        self._load_games()
    
    def _load_games(self):
        try:
            if self.games_file.exists():
                with open(self.games_file, 'r', encoding='utf-8') as f:
                    self.games = json.load(f)
                logger.info(f"Loaded {len(self.games)} active games")
            else:
                self.games = {}
                self._save_games()
        except Exception as e:
            logger.error(f"Error loading games: {e}")
            self.games = {}
    
    def _save_games(self):
        try:
            logger.debug(f"Saving {len(self.games)} games to {self.games_file}")
            with open(self.games_file, 'w', encoding='utf-8') as f:
                json.dump(self.games, f, ensure_ascii=False, indent=2)
            logger.debug(f"Games saved successfully")
        except Exception as e:
            logger.error(f"Error saving games: {e}", exc_info=True)
    
    def create_game(self, game_key: str, game_data: Dict[str, Any]):
        self.games[game_key] = game_data
        self._save_games()
        logger.info(f"Created game: {game_key}")
    
    def get_game(self, game_key: str) -> Optional[Dict[str, Any]]:
        self._load_games()
        return self.games.get(game_key)
    
    def update_game(self, game_key: str, game_data: Dict[str, Any]):
        if game_key in self.games:
            self.games[game_key] = game_data
            self._save_games()
            logger.info(f"Updated game: {game_key}")
    
    def delete_game(self, game_key: str):
        try:
            self._load_games()
            
            if game_key in self.games:
                logger.info(f"Deleting game {game_key} from memory...")
                del self.games[game_key]
                logger.info(f"Game {game_key} deleted from memory, saving to file...")
                self._save_games()
                
                self._load_games()
                if game_key not in self.games:
                    logger.info(f"Verified: Game {game_key} successfully deleted")
                else:
                    logger.error(f"ERROR: Game {game_key} still exists after deletion!")
            else:
                logger.warning(f"Attempted to delete non-existent game: {game_key}")
        except Exception as e:
            logger.error(f"Error in delete_game for {game_key}: {e}", exc_info=True)
            raise
    
    def game_exists(self, game_key: str) -> bool:
        self._load_games()
        exists = game_key in self.games
        logger.info(f"[DEBUG] Checked game_exists for {game_key}: {exists} (total games: {len(self.games)})")
        return exists
    
    def get_all_games(self) -> Dict[str, Any]:
        return self.games.copy()
