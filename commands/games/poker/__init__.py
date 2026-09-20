"""Модуль игры Покер (Техасский Холдем)."""
from aiogram import Router
from .game import router as game_router
from .betting import router as betting_router
from .rules import router as rules_router

router = Router()
router.include_router(game_router)
router.include_router(betting_router)
router.include_router(rules_router)

__all__ = ["router"]
