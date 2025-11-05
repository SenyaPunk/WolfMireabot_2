"""Модуль игры Блекджек"""
from .game import router as game_router
from .betting import router as betting_router
from .playing import router as playing_router

from aiogram import Router

router = Router()
router.include_router(game_router)
router.include_router(betting_router)
router.include_router(playing_router)

__all__ = ["router"]
