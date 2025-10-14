# """Команды экономики бота."""
# import logging
# from aiogram import Router, F
# from aiogram.filters import Command
# from aiogram.types import Message

# from utils.economy_manager import EconomyManager
# from utils.admin_manager import AdminManager
# from utils.user_storage import UserStorage
# from utils.user_link import get_user_link

# router = Router()
# logger = logging.getLogger(__name__)

# economy_manager = EconomyManager()
# admin_manager = AdminManager()
# user_storage = UserStorage()

# # Команда /balance
# @router.message(Command("balance"))
# async def balance_command(message: Message):
#     """Показать баланс пользователя."""
#     if message.chat.type == "private":
#         await message.reply("❌ Эта команда доступна только в групповых чатах.")
#         return
    
#     target_user_id = None
#     target_name = None
    
#     # Проверяем ответ на сообщение
#     if message.reply_to_message:
#         target_user_id = message.reply_to_message.from_user.id
#         target_name = user_storage.get_display_name(target_user_id)
#     else:
#         # Проверяем аргументы команды
#         args = message.text.split()
#         if len(args) > 1:
#             username = args[1].lstrip('@')
#             target_user_id = user_storage.get_user_id(username)
            
#             if target_user_id:
#                 target_name = user_storage.get_display_name(target_user_id)
#             else:
#                 await message.reply(
#                     f"❌ Пользователь @{username} не найден в базе данных.\n"
#                     "Убедитесь, что пользователь писал сообщения в этом чате."
#                 )
#                 return
#         else:
#             # Показываем баланс самого пользователя
#             target_user_id = message.from_user.id
#             target_name = user_storage.get_display_name(target_user_id)
    
#     balance = economy_manager.get_balance(target_user_id)
#     total_wealth = 1000 + balance + (balance * 0.3)
#     user_link = get_user_link(target_user_id)
    
#     await message.reply(
#         f"💰 Баланс {user_link}: <b>{balance:.2f}</b> монет\n"
#         f"💎 Общее состояние: <b>{total_wealth:.2f}</b>",
#         parse_mode="HTML",
#         disable_web_page_preview=True,
#     )

# # Команда /add_money
# @router.message(Command("add_money"))
# async def add_money_command(message: Message):
#     """Добавить деньги пользователю (только для админов)."""
#     if not admin_manager.is_admin(message.from_user.id):
#         await message.reply("❌ Только администраторы могут использовать эту команду.")
#         return
    
#     if message.chat.type == "private":
#         await message.reply("❌ Эта команда доступна только в групповых чатах.")
#         return
    
#     target_user_id = None
#     target_name = None
#     amount = None
    
#     args = message.text.split()
    
#     # Проверяем ответ на сообщение
#     if message.reply_to_message:
#         target_user_id = message.reply_to_message.from_user.id
#         target_name = user_storage.get_display_name(target_user_id)
        
#         # Сумма должна быть в аргументах
#         if len(args) > 1:
#             try:
#                 amount = float(args[1])
#             except ValueError:
#                 await message.reply("❌ Неверный формат суммы. Используйте число.")
#                 return
#         else:
#             await message.reply("❌ Укажите сумму.\nПример: /add_money 100")
#             return
#     else:
#         # Проверяем аргументы команды
#         if len(args) == 2:
#             # /add_money 100 - добавить себе
#             try:
#                 amount = float(args[1])
#                 target_user_id = message.from_user.id
#                 target_name = user_storage.get_display_name(target_user_id)
#             except ValueError:
#                 await message.reply("❌ Неверный формат суммы. Используйте число.")
#                 return
#         elif len(args) >= 3:
#             # /add_money @user 100
#             username = args[1].lstrip('@')
#             target_user_id = user_storage.get_user_id(username)
            
#             if not target_user_id:
#                 await message.reply(
#                     f"❌ Пользователь @{username} не найден в базе данных.\n"
#                     "Убедитесь, что пользователь писал сообщения в этом чате."
#                 )
#                 return
            
#             target_name = user_storage.get_display_name(target_user_id)
            
#             try:
#                 amount = float(args[2])
#             except ValueError:
#                 await message.reply("❌ Неверный формат суммы. Используйте число.")
#                 return
#         else:
#             await message.reply(
#                 "❌ Неверный формат команды.\n\n"
#                 "Примеры использования:\n"
#                 "• /add_money 100 - добавить себе\n"
#                 "• /add_money @username 100 - добавить пользователю\n"
#                 "• Ответить на сообщение: /add_money 100"
#             )
#             return
    
#     if amount <= 0:
#         await message.reply("❌ Сумма должна быть положительной.")
#         return
    
#     new_balance = economy_manager.add_money(target_user_id, amount)
#     user_link = get_user_link(target_user_id)
    
#     await message.reply(
#         f"✅ Добавлено <b>{amount:.2f}</b> монет пользователю {user_link}\n"
#         f"💰 Новый баланс: <b>{new_balance:.2f}</b> монет",
#         parse_mode="HTML",
#         disable_web_page_preview=True,

#     )

# # Команда /remove_money
# @router.message(Command("remove_money"))
# async def remove_money_command(message: Message):
#     """Убрать деньги у пользователя (только для админов)."""
#     if not admin_manager.is_admin(message.from_user.id):
#         await message.reply("❌ Только администраторы могут использовать эту команду.")
#         return
    
#     if message.chat.type == "private":
#         await message.reply("❌ Эта команда доступна только в групповых чатах.")
#         return
    
#     target_user_id = None
#     target_name = None
#     amount = None
    
#     args = message.text.split()
    
#     # Проверяем ответ на сообщение
#     if message.reply_to_message:
#         target_user_id = message.reply_to_message.from_user.id
#         target_name = user_storage.get_display_name(target_user_id)
        
#         # Сумма должна быть в аргументах
#         if len(args) > 1:
#             try:
#                 amount = float(args[1])
#             except ValueError:
#                 await message.reply("❌ Неверный формат суммы. Используйте число.")
#                 return
#         else:
#             await message.reply("❌ Укажите сумму.\nПример: /remove_money 100")
#             return
#     else:
#         # Проверяем аргументы команды
#         if len(args) == 2:
#             # /remove_money 100 - убрать у себя
#             try:
#                 amount = float(args[1])
#                 target_user_id = message.from_user.id
#                 target_name = user_storage.get_display_name(target_user_id)
#             except ValueError:
#                 await message.reply("❌ Неверный формат суммы. Используйте число.")
#                 return
#         elif len(args) >= 3:
#             # /remove_money @user 100
#             username = args[1].lstrip('@')
#             target_user_id = user_storage.get_user_id(username)
            
#             if not target_user_id:
#                 await message.reply(
#                     f"❌ Пользователь @{username} не найден в базе данных.\n"
#                     "Убедитесь, что пользователь писал сообщения в этом чате."
#                 )
#                 return
            
#             target_name = user_storage.get_display_name(target_user_id)
            
#             try:
#                 amount = float(args[2])
#             except ValueError:
#                 await message.reply("❌ Неверный формат суммы. Используйте число.")
#                 return
#         else:
#             await message.reply(
#                 "❌ Неверный формат команды.\n\n"
#                 "Примеры использования:\n"
#                 "• /remove_money 100 - убрать у себя\n"
#                 "• /remove_money @username 100 - убрать у пользователя\n"
#                 "• Ответить на сообщение: /remove_money 100"
#             )
#             return
    
#     if amount <= 0:
#         await message.reply("❌ Сумма должна быть положительной.")
#         return
    
#     new_balance = economy_manager.remove_money(target_user_id, amount)
#     user_link = get_user_link(target_user_id)
    
#     await message.reply(
#         f"✅ Убрано <b>{amount:.2f}</b> монет у пользователя {user_link}\n"
#         f"💰 Новый баланс: <b>{new_balance:.2f}</b> монет",
#         parse_mode="HTML",
#         disable_web_page_preview=True,

#     )

# # Команда /top
# @router.message(Command("top"))
# async def top_command(message: Message):
#     """Показать топ пользователей по балансу."""
#     if message.chat.type == "private":
#         await message.reply("❌ Эта команда доступна только в групповых чатах.")
#         return
    
#     top_users = economy_manager.get_top_users(limit=10)
    
#     if not top_users:
#         await message.reply("📊 Топ пользователей пуст. Никто еще не заработал монеты!")
#         return
    
#     top_list = []
#     for index, (user_id, balance) in enumerate(top_users, start=1):
#         user_link = get_user_link(user_id)
        
#         # Добавляем медали для топ-3
#         if index == 1:
#             medal = "🥇"
#         elif index == 2:
#             medal = "🥈"
#         elif index == 3:
#             medal = "🥉"
#         else:
#             medal = f"{index}."
        
#         top_list.append(f"{medal} {user_link} — <b>{balance:.2f}</b> монет")
    
#     top_text = "\n".join(top_list)
    
#     await message.reply(
#         f"📊 <b>Топ пользователей по балансу:</b>\n\n{top_text}",
#         parse_mode="HTML",
#         disable_web_page_preview=True,
#     )
