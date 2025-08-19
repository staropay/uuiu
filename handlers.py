import logging
import asyncio
import re
from html import escape
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import database
from config import MIN_BET, MAX_BET, MIN_WITHDRAWAL, ADMIN_CHAT_ID
from ui import get_main_menu_keyboard, get_game_choice_keyboard, get_back_to_menu_keyboard_nested, get_back_to_menu_keyboard_simple, get_post_game_keyboard

logger = logging.getLogger(__name__)

MAIN_MENU, GAME_CHOICE, BET_PLACEMENT, RESULT_SHOWN, POST_GAME_CHOICE, CHANGE_BET, WITHDRAW_AMOUNT, REQUEST_SENT, SETTING_NICKNAME, NICKNAME_SET, REFERRAL_MENU = range(11)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await database.add_user_if_not_exists(user.id, user.username)
    
    # Обработка реферальных параметров
    referral_bonus_text = ""
    if update.message and update.message.text:
        # Парсим параметры из команды /start?ref=CODE
        import re
        ref_match = re.search(r'/start\s+(\w+)', update.message.text)
        if ref_match:
            referral_code = ref_match.group(1)
            await process_referral_registration(user.id, referral_code, context)
            referral_bonus_text = "\n\n🎁 <b>Бонус за регистрацию по реферальной ссылке: +50 ⭐</b>"
    
    logger.info(f"Пользователь {user.id} ({user.username}) запустил/перезапустил бота.")
    
    text = f"👋 Привет, {user.mention_html()}!\n\nДобро пожаловать в наше казино! Выбери действие:{referral_bonus_text}"
    reply_markup = get_main_menu_keyboard()
    
    if update.message:
        await update.message.reply_html(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')

    return MAIN_MENU

async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await start(update, context)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    text = f"👋 Привет, {user.mention_html()}!\n\nВы в главном меню. Выбери действие:"
    reply_markup = get_main_menu_keyboard()
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    return ConversationHandler.END

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user_balance = await database.get_user_balance(user_id)
    text = f"💰 Ваш текущий баланс: <b>{user_balance}</b> ⭐"
    
    await query.edit_message_text(text, reply_markup=get_back_to_menu_keyboard_simple(), parse_mode='HTML')

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    rules_text = (
        "<b>📜 Правила Игры и Коэффициенты</b>\n\n"
        f"<b>Ставки:</b> от {MIN_BET} до {MAX_BET} ⭐.\n"
        f"<b>Вывод:</b> от {MIN_WITHDRAWAL} ⭐.\n\n"
        "<b>🎰 Слот-машина:</b>\n"
        "  7️⃣7️⃣7️⃣ (Джекпот): <b>x50</b>\n"
        "  🍇🍇🍇 (Три винограда): <b>x20</b>\n"
        "  🍋🍋🍋 (Три лимона): <b>x10</b>\n"
        "  🅱️🅱️🅱️ (Три BAR): <b>x5</b>\n\n"
        "<b>🎲 Кости:</b>\n"
        "  Выпало 6: <b>x3</b>\n"
        "  Выпало 5: <b>x2</b>\n\n"
        "<b>🏀/⚽ Баскетбол/Футбол:</b>\n"
        "  Мяч в цели (попадание): <b>x2.5</b>\n"
        "  Почти попал (рядом): <b>x1 (возврат ставки)</b>"
    )
    await query.edit_message_text(rules_text, reply_markup=get_back_to_menu_keyboard_simple(), parse_mode='HTML')

async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Выберите игру:", reply_markup=get_game_choice_keyboard())
    return GAME_CHOICE

async def choose_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["game"] = query.data.split('_')[1]
    await query.edit_message_text(f"Вы выбрали игру. Теперь введите вашу ставку (от {MIN_BET} до {MAX_BET} ⭐):")
    return BET_PLACEMENT

async def place_bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    try:
        bet = int(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=get_back_to_menu_keyboard_nested())
        return RESULT_SHOWN

    user_balance = await database.get_user_balance(user.id)

    if not (MIN_BET <= bet <= MAX_BET) or bet > user_balance:
        await update.message.reply_text(f"Некорректная ставка. Ваш баланс: {user_balance} ⭐.", reply_markup=get_back_to_menu_keyboard_nested())
        return RESULT_SHOWN

    await database.update_user_balance(user.id, -bet, relative=True)
    
    game_emoji = {"dice": "🎲", "basketball": "🏀", "football": "⚽", "dart": "🎰"}[context.user_data["game"]]
    
    msg = await context.bot.send_dice(chat_id=update.effective_chat.id, emoji=game_emoji)
    
    await asyncio.sleep(3.5)
    
    dice_value = msg.dice.value
    win_amount = 0
    result_text = "К сожалению, вы проиграли."
    game = context.user_data["game"]

    if game == 'dart':
        if dice_value == 64: win_amount, result_text = bet * 50, "ДЖЕКПОТ! 7️⃣7️⃣7️⃣"
        elif dice_value == 43: win_amount, result_text = bet * 10, "Неплохо! Три лимона! 🍋🍋🍋"
        elif dice_value == 22: win_amount, result_text = bet * 20, "Отлично! Три винограда! 🍇🍇🍇"
        elif dice_value == 1: win_amount, result_text = bet * 5, "Выигрыш! Три BAR! 🅱️🅱️🅱️"
    elif game == 'dice':
        if dice_value == 6: win_amount, result_text = bet * 3, "Выпало 6! Ваш выигрыш!"
        elif dice_value == 5: win_amount, result_text = bet * 2, "Выпало 5! Вы победили!"
    elif game in ['basketball', 'football']:
        if dice_value == 5: win_amount, result_text = int(bet * 2.5), "ГОЛ! Вы победили!"
        elif dice_value == 4: win_amount, result_text = bet, "Почти! Ваша ставка возвращена."

    if win_amount > 0:
        await database.update_user_balance(user.id, win_amount, relative=True)
    
    await database.update_user_stats(user.id, bet, win_amount)
    
    final_balance = await database.get_user_balance(user.id)
    
    # Сохраняем данные игры для повторного использования
    context.user_data["current_game"] = game
    context.user_data["current_bet"] = bet
    
    text = (f"{result_text}\n\n"
            f"Ваша ставка: {bet} ⭐ | Выигрыш: {win_amount} ⭐\n"
            f"Ваш новый баланс: <b>{final_balance}</b> ⭐")
    
    await update.message.reply_html(text, reply_markup=get_post_game_keyboard())
    return POST_GAME_CHOICE

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user_balance = await database.get_user_balance(user_id)

    if user_balance < MIN_WITHDRAWAL:
        await query.edit_message_text(f"❌ Ошибка: минимальная сумма для вывода {MIN_WITHDRAWAL} ⭐. У вас на балансе {user_balance} ⭐.", reply_markup=get_back_to_menu_keyboard_nested())
        return REQUEST_SENT
    
    await query.edit_message_text(f"Ваш баланс: {user_balance} ⭐. Введите сумму, которую хотите вывести:")
    return WITHDRAW_AMOUNT

async def process_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    try:
        amount = int(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text("Пожалуйста, введите числовое значение.", reply_markup=get_back_to_menu_keyboard_nested())
        return REQUEST_SENT

    user_balance = await database.get_user_balance(user.id)

    if amount < MIN_WITHDRAWAL or amount > user_balance:
        await update.message.reply_text(f"Некорректная сумма. Ваш баланс: {user_balance} ⭐.", reply_markup=get_back_to_menu_keyboard_nested())
        return REQUEST_SENT

    await database.update_user_balance(user.id, -amount, relative=True)
    new_balance = await database.get_user_balance(user.id)

    admin_message = (f"❗️ <b>Новый запрос на вывод</b> ❗️\n\n"
                     f"Пользователь: {user.mention_html()} ({user.id})\n"
                     f"Сумма: <b>{amount}</b> ⭐\n"
                     f"Баланс после: {new_balance} ⭐")
    
    try:
        if ADMIN_CHAT_ID:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message, parse_mode='HTML')
            await update.message.reply_text(f"✅ Ваш запрос на вывод {amount} ⭐ принят.", reply_markup=get_back_to_menu_keyboard_nested())
        else:
            await update.message.reply_text("Ошибка: не удалось отправить запрос.", reply_markup=get_back_to_menu_keyboard_nested())
            await database.update_user_balance(user.id, amount, relative=True)
    except Exception as e:
        logger.error(f"Ошибка вывода: {e}")
        await update.message.reply_text("Ошибка: не удалось отправить запрос.", reply_markup=get_back_to_menu_keyboard_nested())
        await database.update_user_balance(user.id, amount, relative=True)

    return REQUEST_SENT

async def show_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
        
    top_users = await database.get_top_users(10)
    
    if not top_users:
        text = "🏆 Таблица лидеров пока пуста."
    else:
        text = "<b>🏆 Топ-10 игроков по балансу:</b>\n\n"
        for i, user in enumerate(top_users):
            rank = i + 1
            display_name = user['nickname'] if user['nickname'] else user['username']
            safe_display_name = escape(display_name) if display_name else f"User {user['user_id']}"
            balance = user['balance']
            
            line = f"<b>{rank}.</b> {safe_display_name} — <code>{balance}</code> ⭐\n"
            if user['user_id'] == update.effective_user.id:
                line = f"➡️ {line}"
            text += line
            
    reply_markup = get_back_to_menu_keyboard_simple()
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_html(text, reply_markup=reply_markup)

async def request_nickname_from_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите ваш новый никнейм (3-15 символов, буквы, цифры, _-):")
    return SETTING_NICKNAME

async def request_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите ваш новый никнейм (3-15 символов, буквы, цифры, _-):")
    return SETTING_NICKNAME

async def save_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    nickname = update.message.text
    if not (3 <= len(nickname) <= 15 and re.match(r'^[a-zA-Z0-9_-]+$', nickname)):
        await update.message.reply_html(
            "❌ <b>Ошибка:</b> Никнейм должен быть длиной от 3 до 15 символов и содержать только латинские буквы, цифры, знаки подчеркивания (_) или дефисы (-)."
        )
        return SETTING_NICKNAME

    user_id = update.effective_user.id
    await database.set_user_nickname(user_id, nickname)
    
    await update.message.reply_html(
        f"✅ Ваш никнейм успешно изменен на: <b>{escape(nickname)}</b>",
        reply_markup=get_back_to_menu_keyboard_nested()
    )
    return NICKNAME_SET

# Новые обработчики для пост-игрового меню
async def handle_post_game_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Назад в меню' после игры"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    text = f"👋 Привет, {user.mention_html()}!\n\nВы в главном меню. Выбери действие:"
    reply_markup = get_main_menu_keyboard()
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='HTML')
    
    # Очищаем данные игры
    context.user_data.pop("current_game", None)
    context.user_data.pop("current_bet", None)
    
    return ConversationHandler.END

async def handle_post_game_change_bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Изменить ставку' после игры"""
    query = update.callback_query
    await query.answer()
    
    current_game = context.user_data.get("current_game")
    if not current_game:
        await query.edit_message_text("Ошибка: игра не найдена.", reply_markup=get_back_to_menu_keyboard_nested())
        return ConversationHandler.END
    
    game_names = {"dice": "кости", "basketball": "баскетбол", "football": "футбол", "dart": "слот-машина"}
    game_name = game_names.get(current_game, current_game)
    
    await query.edit_message_text(
        f"Вы играете в {game_name}. Введите новую ставку (от {MIN_BET} до {MAX_BET} ⭐):",
        reply_markup=get_back_to_menu_keyboard_nested()
    )
    return CHANGE_BET

async def handle_post_game_play_again(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки 'Играть снова' после игры"""
    query = update.callback_query
    await query.answer()
    
    current_game = context.user_data.get("current_game")
    current_bet = context.user_data.get("current_bet")
    
    if not current_game or not current_bet:
        await query.edit_message_text("Ошибка: данные игры не найдены.", reply_markup=get_back_to_menu_keyboard_nested())
        return ConversationHandler.END
    
    user = update.effective_user
    user_balance = await database.get_user_balance(user.id)
    
    # Проверяем, достаточно ли средств для повторной игры
    if current_bet > user_balance:
        await query.edit_message_text(
            f"Недостаточно средств для повторной игры. Ваш баланс: {user_balance} ⭐",
            reply_markup=get_back_to_menu_keyboard_nested()
        )
        return ConversationHandler.END
    
    # Запускаем игру с той же ставкой
    return await play_game_with_bet(update, context, current_bet)

async def handle_change_bet_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик ввода новой ставки"""
    user = update.effective_user
    try:
        new_bet = int(update.message.text)
    except (ValueError, TypeError):
        await update.message.reply_text(
            "Пожалуйста, введите числовое значение.",
            reply_markup=get_back_to_menu_keyboard_nested()
        )
        return CHANGE_BET

    user_balance = await database.get_user_balance(user.id)

    if not (MIN_BET <= new_bet <= MAX_BET) or new_bet > user_balance:
        await update.message.reply_text(
            f"Некорректная ставка. Ваш баланс: {user_balance} ⭐.",
            reply_markup=get_back_to_menu_keyboard_nested()
        )
        return CHANGE_BET

    # Запускаем игру с новой ставкой
    return await play_game_with_bet(update, context, new_bet)

async def play_game_with_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, bet: int) -> int:
    """Вспомогательная функция для запуска игры с заданной ставкой"""
    user = update.effective_user
    game = context.user_data.get("current_game")
    
    if not game:
        if update.message:
            await update.message.reply_text("Ошибка: игра не найдена.", reply_markup=get_back_to_menu_keyboard_nested())
        else:
            query = update.callback_query
            await query.edit_message_text("Ошибка: игра не найдена.", reply_markup=get_back_to_menu_keyboard_nested())
        return ConversationHandler.END
    
    await database.update_user_balance(user.id, -bet, relative=True)
    
    game_emoji = {"dice": "🎲", "basketball": "🏀", "football": "⚽", "dart": "🎰"}[game]
    
    msg = await context.bot.send_dice(chat_id=update.effective_chat.id, emoji=game_emoji)
    
    await asyncio.sleep(3.5)
    
    dice_value = msg.dice.value
    win_amount = 0
    result_text = "К сожалению, вы проиграли."

    if game == 'dart':
        if dice_value == 64: win_amount, result_text = bet * 50, "ДЖЕКПОТ! 7️⃣7️⃣7️⃣"
        elif dice_value == 43: win_amount, result_text = bet * 10, "Неплохо! Три лимона! 🍋🍋🍋"
        elif dice_value == 22: win_amount, result_text = bet * 20, "Отлично! Три винограда! 🍇🍇🍇"
        elif dice_value == 1: win_amount, result_text = bet * 5, "Выигрыш! Три BAR! 🅱️🅱️🅱️"
    elif game == 'dice':
        if dice_value == 6: win_amount, result_text = bet * 3, "Выпало 6! Ваш выигрыш!"
        elif dice_value == 5: win_amount, result_text = bet * 2, "Выпало 5! Вы победили!"
    elif game in ['basketball', 'football']:
        if dice_value == 5: win_amount, result_text = int(bet * 2.5), "ГОЛ! Вы победили!"
        elif dice_value == 4: win_amount, result_text = bet, "Почти! Ваша ставка возвращена."

    if win_amount > 0:
        await database.update_user_balance(user.id, win_amount, relative=True)
    
    await database.update_user_stats(user.id, bet, win_amount)
    
    final_balance = await database.get_user_balance(user.id)
    
    # Обновляем сохраненную ставку
    context.user_data["current_bet"] = bet
    
    text = (f"{result_text}\n\n"
            f"Ваша ставка: {bet} ⭐ | Выигрыш: {win_amount} ⭐\n"
            f"Ваш новый баланс: <b>{final_balance}</b> ⭐")
    
    # Отправляем результат в зависимости от типа обновления
    if update.message:
        await update.message.reply_html(text, reply_markup=get_post_game_keyboard())
    else:
        # Если это callback_query, отправляем новое сообщение
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=get_post_game_keyboard(),
            parse_mode='HTML'
        )
    
    return POST_GAME_CHOICE

# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

async def process_referral_registration(user_id: int, referral_code: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Обрабатывает регистрацию по реферальной ссылке"""
    try:
        # Находим реферера по коду
        referrer_id = await database.get_user_by_referral_code(referral_code)
        if not referrer_id:
            logger.warning(f"Не найден пользователь с реферальным кодом: {referral_code}")
            return False
        
        # Проверяем, что пользователь не регистрируется по своей ссылке
        if referrer_id == user_id:
            logger.warning(f"Пользователь {user_id} пытается зарегистрироваться по своей ссылке")
            return False
        
        # Проверяем, что пользователь еще не был приглашен
        cursor = await database.get_user_referrals(referrer_id)
        for referral in cursor:
            if referral['referred_id'] == user_id:
                logger.warning(f"Пользователь {user_id} уже был приглашен пользователем {referrer_id}")
                return False
        
        # Создаем реферальную связь
        success = await database.add_referral_relationship(referrer_id, user_id)
        if not success:
            logger.error(f"Не удалось создать реферальную связь: {referrer_id} -> {user_id}")
            return False
        
        # Начисляем бонусы
        bonus_success = await database.pay_referral_bonuses(referrer_id, user_id)
        if not bonus_success:
            logger.error(f"Не удалось начислить реферальные бонусы: {referrer_id} -> {user_id}")
            return False
        
        # Обновляем статистику
        await database.update_referral_stats(referrer_id)
        
        logger.info(f"Успешная реферальная регистрация: {referrer_id} -> {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обработке реферальной регистрации: {e}")
        return False

async def referral_system(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик кнопки реферальной системы"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    text = f"👥 <b>Реферальная система</b>\n\nПриглашай друзей и получай бонусы!\n\n"
    text += "🎁 <b>Бонусы:</b>\n"
    text += "• Новый пользователь получает <b>50 ⭐</b>\n"
    text += "• Вы получаете <b>25 ⭐</b> за каждого приглашённого\n\n"
    text += "Выберите действие:"
    
    from ui import get_referral_menu_keyboard
    reply_markup = get_referral_menu_keyboard()
    
    # Удаляем старое сообщение и отправляем новое
    await query.delete_message()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return REFERRAL_MENU

async def show_referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает статистику рефералов пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    referral_info = await database.get_user_referral_info(user_id)
    
    if not referral_info:
        text = "❌ Ошибка получения статистики рефералов"
        await query.delete_message()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=get_back_to_menu_keyboard_simple(),
            parse_mode='HTML'
        )
        return MAIN_MENU
    
    text = f"📊 <b>Ваша реферальная статистика</b>\n\n"
    text += f"👥 Приглашённых пользователей: <b>{referral_info['referrals_count']}</b>\n"
    text += f"💰 Заработано с рефералов: <b>{referral_info['referral_earnings']} ⭐</b>\n\n"
    
    if referral_info['referrals_count'] > 0:
        text += "📋 <b>Ваши рефералы:</b>\n"
        referrals = await database.get_user_referrals(user_id)
        for i, referral in enumerate(referrals[:5], 1):  # Показываем только первые 5
            name = referral['nickname'] or referral['username'] or f"Пользователь {referral['referred_id']}"
            text += f"{i}. {name}\n"
        
        if len(referrals) > 5:
            text += f"... и ещё {len(referrals) - 5} пользователей\n"
    
    from ui import get_referral_stats_keyboard
    reply_markup = get_referral_stats_keyboard()
    
    # Удаляем старое сообщение и отправляем новое
    await query.delete_message()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return REFERRAL_MENU

async def generate_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Генерирует и показывает реферальную ссылку пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    referral_code = await database.ensure_referral_code(user_id)
    
    # Получаем информацию о боте
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    
    referral_link = f"https://t.me/{bot_username}?start={referral_code}"
    
    text = f"🔗 <b>Ваша реферальная ссылка</b>\n\n"
    text += f"<code>{referral_link}</code>\n\n"
    text += "📋 Скопируйте эту ссылку и отправьте друзьям!\n\n"
    text += "🎁 <b>Бонусы:</b>\n"
    text += "• Ваш друг получит <b>50 ⭐</b> за регистрацию\n"
    text += "• Вы получите <b>25 ⭐</b> за каждого приглашённого"
    
    from ui import get_referral_stats_keyboard
    reply_markup = get_referral_stats_keyboard()
    
    # Удаляем старое сообщение и отправляем новое
    await query.delete_message()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return REFERRAL_MENU

async def show_referral_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает список рефералов пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    referrals = await database.get_user_referrals(user_id)
    
    if not referrals:
        text = "📋 <b>Ваши рефералы</b>\n\nУ вас пока нет приглашённых пользователей.\n\n"
        text += "🔗 Поделитесь своей реферальной ссылкой с друзьями!"
    else:
        text = f"📋 <b>Ваши рефералы</b>\n\n"
        text += f"Всего приглашённых: <b>{len(referrals)}</b>\n\n"
        
        for i, referral in enumerate(referrals, 1):
            name = referral['nickname'] or referral['username'] or f"Пользователь {referral['referred_id']}"
            date = referral['created_at'].split()[0] if referral['created_at'] else "Неизвестно"
            text += f"{i}. <b>{name}</b> - {date}\n"
    
    from ui import get_referral_stats_keyboard
    reply_markup = get_referral_stats_keyboard()
    
    # Удаляем старое сообщение и отправляем новое
    await query.delete_message()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return REFERRAL_MENU