import logging
import asyncio
import time
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from config import ADMIN_ID
import database

logger = logging.getLogger(__name__)

def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if str(user_id) != ADMIN_ID:
            await update.message.reply_text("У вас нет прав для выполнения этой команды.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>Админ-панель</b>\n\n"
        "/check_balance <code>[user_id]</code> - Проверить баланс\n"
        "/add_balance <code>[user_id] [amount]</code> - Начислить баланс\n"
        "/sub_balance <code>[user_id] [amount]</code> - Списать баланс\n"
        "/broadcast <code>[message]</code> - Сделать рассылку\n"
        "/server_stats - Показать статистику сервера"
    )
    await update.message.reply_html(text)

@admin_only
async def check_user_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(context.args[0])
        balance = await database.get_user_balance(target_id)
        await update.message.reply_text(f"Баланс пользователя {target_id}: {balance} ⭐")
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /check_balance [user_id]")

@admin_only
async def add_to_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        await database.update_user_balance(target_id, amount, relative=True)
        new_balance = await database.get_user_balance(target_id)
        await update.message.reply_text(f"Баланс пользователя {target_id} пополнен на {amount}. Новый баланс: {new_balance} ⭐")
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /add_balance [user_id] [amount]")

@admin_only
async def subtract_from_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        await database.update_user_balance(target_id, -amount, relative=True)
        new_balance = await database.get_user_balance(target_id)
        await update.message.reply_text(f"С баланса пользователя {target_id} списано {amount}. Новый баланс: {new_balance} ⭐")
    except (IndexError, ValueError):
        await update.message.reply_text("Использование: /sub_balance [user_id] [amount]")

async def send_message_to_user(bot, user_id: int, message: str) -> bool:
    try:
        await bot.send_message(chat_id=user_id, text=message, parse_mode='HTML')
        return True
    except TelegramError as e:
        logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        return False

@admin_only
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_to_send = " ".join(context.args)
    if not message_to_send:
        await update.message.reply_text("Пожалуйста, укажите текст для рассылки. /broadcast [текст]")
        return

    await update.message.reply_text("⏳ Начинаю рассылку...")
    start_time = time.time()
    
    user_ids = await database.get_all_user_ids()
    tasks = [send_message_to_user(context.bot, user_id, message_to_send) for user_id in user_ids]
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    duration = end_time - start_time
    
    success_count = sum(results)
    fail_count = len(user_ids) - success_count
    
    await update.message.reply_text(
        f"✅ Рассылка завершена за {duration:.2f} сек.\n"
        f"Успешно отправлено: {success_count}\n"
        f"Не удалось отправить: {fail_count}"
    )

@admin_only
async def show_server_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = await database.get_global_stats()
    
    if not stats or stats['total_users'] == 0:
        await update.message.reply_text("Статистика сервера пока пуста.")
        return
        
    total_users = stats['total_users']
    avg_balance = (stats['total_balance'] / total_users) if total_users > 0 else 0
    avg_games = (stats['total_games'] / total_users) if total_users > 0 else 0
    
    casino_profit = -stats['casino_profit']
    profit_sign = "+" if casino_profit >= 0 else ""
    profit_emoji = "📈" if casino_profit >= 0 else "📉"
    
    text = (
        f"<b>⚙️ Статистика Сервера</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🕹️ Всего сыграно игр: <b>{stats['total_games'] or 0}</b>\n"
        f"💸 Общий оборот (сумма ставок): <b>{stats['total_wager'] or 0}</b> ⭐\n"
        f"🏦 Общий баланс пользователей: <b>{stats['total_balance'] or 0}</b> ⭐\n"
        f"{profit_emoji} Прибыль казино: <b>{profit_sign}{casino_profit}</b> ⭐\n\n"
        f"<b>Аналитика:</b>\n"
        f"💰 Средний баланс на игрока: <b>{avg_balance:.2f}</b> ⭐\n"
        f"🎮 Среднее кол-во игр на игрока: <b>{avg_games:.2f}</b>"
    )
    
    await update.message.reply_html(text)