"""Модуль команд экономики."""
from aiogram import Router

router = Router()

from .balance import router as balance_router
from .money_management import router as money_router
from .top import router as top_router
from .transfer import router as transfer_router
from .work import router as work_router

router.include_router(balance_router)
router.include_router(money_router)
router.include_router(top_router)
router.include_router(transfer_router)
router.include_router(work_router)
