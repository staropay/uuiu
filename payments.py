import logging
import time
from telegram import Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import database
from ui import get_deposit_options_keyboard, get_back_to_menu_keyboard_nested

logger = logging.getLogger(__name__)

CHOOSE_AMOUNT, CUSTOM_AMOUNT, LINK_SENT = range(3)

async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Выберите или введите сумму для пополнения баланса звездами ⭐:",
        reply_markup=get_deposit_options_keyboard()
    )
    return CHOOSE_AMOUNT

async def select_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    amount_str = query.data.split('_')[1]

    if amount_str == 'custom':
        await query.edit_message_text("Введите сумму пополнения в звездах (например, 150, мин. 1, макс. 10000):")
        return CUSTOM_AMOUNT
    else:
        amount = int(amount_str)
        return await create_and_send_payment_link(update, context, amount)

async def process_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = int(update.message.text)
        if not (1 <= amount <= 10000):
            await update.message.reply_text("Неверная сумма. Введите число от 1 до 10000.", reply_markup=get_back_to_menu_keyboard_nested())
            return LINK_SENT
    except (ValueError, TypeError):
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=get_back_to_menu_keyboard_nested())
        return LINK_SENT
    
    await update.message.delete()
    return await create_and_send_payment_link(update, context, amount)

async def create_and_send_payment_link(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int) -> int:
    title = "Пополнение баланса казино"
    description = f"Пополнение вашего игрового счета на {amount} ⭐"
    
    timestamp = int(time.time())
    payload = f"casino-deposit-{update.effective_user.id}-{timestamp}"
    
    currency = "XTR"
    prices = [LabeledPrice("Игровые звезды", amount)]

    try:
        link = await context.bot.create_invoice_link(title, description, payload, currency, prices)
        
        text = (f"Для пополнения баланса на <b>{amount} ⭐</b>, нажмите кнопку ниже.\n\n"
                "<i>Ссылка действительна в течение ограниченного времени.</i>")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💳 Оплатить {amount} ⭐", url=link)],
            [InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]
        ])

        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode='HTML')
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=keyboard, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Ошибка при создании ссылки на оплату: {e}")
        text = "Не удалось создать ссылку на оплату. Пожалуйста, попробуйте позже."
        reply_markup = get_back_to_menu_keyboard_nested()
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup)
    
    return LINK_SENT

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    if not query.invoice_payload.startswith('casino-deposit-'):
        await query.answer(ok=False, error_message="Что-то пошло не так...")
    else:
        await query.answer(ok=True)
        logger.info(f"Подтвержден pre-checkout для пользователя {query.from_user.id}")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    payment = update.message.successful_payment
    amount = payment.total_amount
    
    await database.update_user_balance(user.id, amount, relative=True)
    new_balance = await database.get_user_balance(user.id)
    
    logger.info(f"Пользователь {user.id} успешно пополнил баланс на {amount} ⭐.")
    await context.bot.send_message(
        chat_id=user.id,
        text=f"✅ Оплата прошла успешно!\n\nНа ваш счет зачислено: <b>{amount}</b> ⭐\nВаш новый баланс: <b>{new_balance}</b> ⭐",
        parse_mode='HTML'
    )