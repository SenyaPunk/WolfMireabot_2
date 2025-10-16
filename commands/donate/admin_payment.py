# """Административные команды для обработки платежей."""
# import logging
# from aiogram import Router
# from aiogram.filters import Command
# from aiogram.types import Message
# from .payment_handler import DonateManager

# router = Router()
# logger = logging.getLogger(__name__)

# donate_manager = DonateManager()


# @router.message(Command("process_payment"))
# async def process_payment_command(message: Message):
    

#     args = message.text.split()
    
#     if len(args) != 3:
#         await message.reply(
#             "❌ Неверный формат команды!\n\n"
#             "Использование: /process_payment <user_id> <donate_type>\n\n"
#             "Доступные типы донатов:\n"
#             "• 500coins - 500 монет\n"
#             "• 1000coins - 1000 монет\n"
#             "• 3000coins - 3000 монет\n"
#             "• blackjack_boost - буст блекджека\n"
#             "• slavery_slots - разблокировка слотов\n\n"
#             "Пример: /process_payment 123456789 500coins"
#         )
#         return
    
#     try:
#         user_id = int(args[1])
#         donate_type = args[2]
#     except ValueError:
#         await message.reply("❌ Неверный формат user_id! Должно быть число.")
#         return
    
#     # Обрабатываем платеж
#     result = donate_manager.process_payment(user_id, donate_type)
    
#     if result is None:
#         await message.reply(f"❌ Неизвестный тип доната: {donate_type}")
#         return
    
#     # Формируем сообщение об успешном зачислении
#     if result["type"] == "coins":
#         response = (
#             f"✅ Платеж успешно обработан!\n\n"
#             f"👤 Пользователь: {user_id}\n"
#             f"💰 Зачислено: {result['amount']} монет\n"
#             f"💎 Новый баланс: {result['new_balance']:.2f} монет"
#         )
#     else:
#         response = (
#             f"✅ Платеж успешно обработан!\n\n"
#             f"👤 Пользователь: {user_id}\n"
#             f"🎁 Активировано: {result['description']}"
#         )
    
#     await message.reply(response)
    
#     logger.info(
#         f"Администратор {message.from_user.id} обработал платеж "
#         f"для пользователя {user_id}: {donate_type}"
#     )
