import asyncio
import os
import importlib
import pkgutil
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram import F
from aiogram.types import Message

from utils.user_storage import UserStorage
from middlewares.user_tracking import UserTrackingMiddleware
from middlewares.ignore_old_updates import IgnoreOldUpdatesMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.client.default import DefaultBotProperties

proxy = os.getenv("TELEGRAM_PROXY")
api_server = os.getenv("TELEGRAM_API_SERVER")

default_properties = DefaultBotProperties(link_preview_is_disabled=True)

if api_server:
    logging.info(f"Используется кастомный сервер Telegram API: {api_server}")
    session = AiohttpSession(api=TelegramAPIServer.from_base(api_server))
    bot = Bot(token=os.getenv("BOT_TOKEN"), session=session, default=default_properties)
elif proxy:
    logging.info(f"Используется прокси для Telegram: {proxy}")
    session = AiohttpSession(proxy=proxy)
    bot = Bot(token=os.getenv("BOT_TOKEN"), session=session, default=default_properties)
else:
    bot = Bot(token=os.getenv("BOT_TOKEN"), default=default_properties)

dp = Dispatcher()

user_storage = UserStorage()

dp.update.outer_middleware(IgnoreOldUpdatesMiddleware())
dp.update.outer_middleware(UserTrackingMiddleware(user_storage))

# Регистрируем все команды (file manager)
def register_all(package_name="commands"):
    registered_packages = set()
    
    pkg = importlib.import_module(package_name)
    for finder, name, ispkg in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        parent_pkg = '.'.join(name.split('.')[:-1])
        if parent_pkg in registered_packages:
            continue
            
        mod = importlib.import_module(name)
        if hasattr(mod, "router"):
            router = getattr(mod, "router")
            dp.include_router(router)
            if ispkg:
                registered_packages.add(name)

register_all("commands")


async def game_lifetime_monitor(bot: Bot):
    # Даем боту время на запуск и прогрузку
    await asyncio.sleep(60)
    while True:
        try:
            from utils.game_state_manager import GameStateManager
            from utils.economy_manager import EconomyManager
            import time
            
            gsm = GameStateManager()
            em = EconomyManager()
            
            game_keys = list(gsm.games.keys())
            
            for game_key in game_keys:
                game_data = gsm.games.get(game_key)
                if not game_data:
                    continue
                
                started_at = game_data.get("started_at", 0)
                # Лимит - 5 минут (300 секунд)
                if started_at > 0 and (time.time() - started_at > 300):
                    chat_id = game_data.get("chat_id")
                    bets = game_data.get("bets", {})
                    
                    # 1. Возвращаем все ставки игрокам
                    refunded_players = []
                    for player in game_data.get("players", []):
                        user_id = player["user_id"] if isinstance(player, dict) else player
                        bet_amount = bets.get(user_id, bets.get(str(user_id), 0))
                        if bet_amount > 0:
                            em.add_money(user_id, bet_amount)
                            username = player.get("username") or player.get("first_name") or f"ID{user_id}" if isinstance(player, dict) else f"ID{user_id}"
                            refunded_players.append(f"• 👤 <b>{username}</b>: {bet_amount} монет")
                    
                    # 2. Отправляем уведомление в чат
                    if chat_id:
                        refund_list = "\n".join(refunded_players) if refunded_players else "Ставок не было."
                        msg_text = (
                            f"⚠️ <b>ПРИНУДИТЕЛЬНОЕ ЗАВЕРШЕНИЕ ИГРЫ</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━\n\n"
                            f"Сессия игры Блекджек превысила лимит времени (5 минут) и была остановлена.\n\n"
                            f"💰 <b>Возвращенные ставки:</b>\n{refund_list}"
                        )
                        try:
                            await bot.send_message(chat_id=chat_id, text=msg_text, parse_mode="HTML")
                        except Exception as e:
                            logging.error(f"Failed to send refund notice to chat {chat_id}: {e}")
                    
                    # 3. Отменяем активные таймеры хода
                    try:
                        from commands.games.blackjack.playing import cancel_player_timer
                        cancel_player_timer(game_key)
                    except Exception as e:
                        logging.warning(f"Could not cancel timer for stuck game {game_key}: {e}")
                    
                    # 4. Удаляем сессию игры из базы данных
                    gsm.delete_game(game_key)
                    logging.info(f"Forced cleanup and refund for stuck game {game_key}")
                    
        except Exception as e:
            logging.error(f"Error in game_lifetime_monitor: {e}", exc_info=True)
            
        # Проверка каждые 30 секунд
        await asyncio.sleep(30)


async def main():
    # Безопасный возврат ставок и очистка неверных сессий при перезапуске бота
    try:
        from utils.game_state_manager import GameStateManager
        from utils.economy_manager import EconomyManager
        gsm = GameStateManager()
        em = EconomyManager()
        
        if gsm.games:
            for game_key, game_data in list(gsm.games.items()):
                if not isinstance(game_data, dict):
                    continue
                chat_id = game_data.get("chat_id")
                bets = game_data.get("bets", {})
                refunds = []
                
                for player in game_data.get("players", []):
                    user_id = player.get("user_id") if isinstance(player, dict) else player
                    if not user_id:
                        continue
                    bet_amount = bets.get(user_id, bets.get(str(user_id), 0))
                    if bet_amount > 0:
                        em.add_money(user_id, bet_amount)
                        uname = player.get("first_name") or f"ID{user_id}" if isinstance(player, dict) else f"ID{user_id}"
                        refunds.append(f"• 👤 <b>{uname}</b>: {bet_amount} монет")
                
                if chat_id:
                    if refunds:
                        refund_msg = (
                            f"⚠️ <b>ПЕРЕЗАПУСК БОТА / ОБНОВЛЕНИЕ</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"Предыдущая сессия игры в Блекджек была остановлена из-за обновления бота.\n\n"
                            f"💰 <b>Все сделанные ставки успешно возвращены:</b>\n" + "\n".join(refunds) + "\n\n"
                            f"💡 <i>Вы можете запустить новую игру через команду /blackjack</i>"
                        )
                    else:
                        refund_msg = (
                            f"⚠️ <b>ПЕРЕЗАПУСК БОТА / ОБНОВЛЕНИЕ</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━\n"
                            f"Предыдущий набор на игру в Блекджек был сброшен из-за обновления бота.\n\n"
                            f"💡 <i>Вы можете начать новую игру через команду /blackjack</i>"
                        )
                    try:
                        await bot.send_message(chat_id=chat_id, text=refund_msg, parse_mode="HTML")
                    except Exception as e:
                        logging.warning(f"Не удалось отправить сообщение о возврате ставок в чат {chat_id}: {e}")

        gsm.games = {}
        gsm._save_games()
        logging.info("База активных игр успешно очищена, ставки возвращены.")
    except Exception as e:
        logging.error(f"Ошибка безопасной очистки игр на старте бота: {e}")

    # Запуск фонового мониторинга жизненного цикла игр и порки рабов
    asyncio.create_task(game_lifetime_monitor(bot))
    from utils.whip_monitor import whip_monitor
    asyncio.create_task(whip_monitor(bot))

    # Установка списка команд для отображения в Telegram с тегом @WolfMIREA_bot
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="help", description="Показать список команд"),
        BotCommand(command="work", description="Начать работать"),
        BotCommand(command="balance", description="Проверить игровой баланс"),
        BotCommand(command="top", description="Топ богатых игроков"),
        BotCommand(command="transfer", description="Передать монеты другому игроку"),
        BotCommand(command="drink", description="Выпить в баре"),
        BotCommand(command="selfcare", description="Сделать себе приятно"),
        BotCommand(command="buy_slave", description="Купить раба"),
        BotCommand(command="whip", description="Отхлестать раба плеткой"),
        BotCommand(command="my_slaves", description="Посмотреть ваших рабов"),
        BotCommand(command="free_slave", description="Освободить раба"),
        BotCommand(command="my_master", description="Посмотреть хозяина"),
        BotCommand(command="buyout", description="Выкупить себя"),
        BotCommand(command="roulette", description="Сыграть в рулетку"),
        BotCommand(command="blackjack", description="Начать игру блекджек"),
        BotCommand(command="donate", description="Донат меню"),
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Список команд успешно зарегистрирован в Telegram.")
    except Exception as e:
        logging.error(f"Ошибка регистрации команд в Telegram: {e}")

    try:
        await dp.start_polling(bot)
    finally:
        pass

if __name__ == "__main__":
    asyncio.run(main())
