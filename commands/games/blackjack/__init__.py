"""Модуль игры Блекджек"""
from .game import router as game_router
from .betting import router as betting_router
from .playing import router as playing_router

from aiogram import Router
from middlewares.casino_schedule import CasinoScheduleMiddleware

router = Router()
casino_middleware = CasinoScheduleMiddleware()
router.message.middleware(casino_middleware)
router.callback_query.middleware(casino_middleware)

router.include_router(game_router)
router.include_router(betting_router)
router.include_router(playing_router)

__all__ = ["router"]

