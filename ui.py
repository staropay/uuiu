from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🎲 Играть", callback_data="play")],
        [
            InlineKeyboardButton("💰 Баланс", callback_data="balance"),
            InlineKeyboardButton("📜 Правила", callback_data="rules")
        ],
        [
            InlineKeyboardButton("🏆 Топ игроков", callback_data="top"),
            InlineKeyboardButton("👤 Мой ник", callback_data="set_nickname")
        ],
        [
            InlineKeyboardButton("Пополнить баланс 💳", callback_data="deposit"),
            InlineKeyboardButton("📤 Вывод средств", callback_data="withdraw")
        ],
        [InlineKeyboardButton("👥 Реферальная система", callback_data="referral_system")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard_simple() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")]]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard_nested() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]]
    return InlineKeyboardMarkup(keyboard)

def get_game_choice_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🎲", callback_data="game_dice"),
            InlineKeyboardButton("🏀", callback_data="game_basketball"),
            InlineKeyboardButton("⚽", callback_data="game_football"),
            InlineKeyboardButton("🎰", callback_data="game_dart"),
        ],
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_deposit_options_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("100 ⭐", callback_data="deposit_100"),
            InlineKeyboardButton("500 ⭐", callback_data="deposit_500"),
            InlineKeyboardButton("1000 ⭐", callback_data="deposit_1000"),
        ],
        [InlineKeyboardButton("Другая сумма", callback_data="deposit_custom")],
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="main_menu_from_nested")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_post_game_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад в меню", callback_data="post_game_back_to_menu")],
        [
            InlineKeyboardButton("💰 Изменить ставку", callback_data="post_game_change_bet"),
            InlineKeyboardButton("🔄 Играть снова", callback_data="post_game_play_again")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

def get_referral_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура главного меню реферальной системы"""
    keyboard = [
        [InlineKeyboardButton("📊 Моя статистика", callback_data="show_referral_stats")],
        [InlineKeyboardButton("🔗 Моя ссылка", callback_data="generate_referral_link")],
        [InlineKeyboardButton("📋 Мои рефералы", callback_data="show_referral_list")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_start")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_referral_stats_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для страниц статистики рефералов"""
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад", callback_data="referral_system")]
    ]
    return InlineKeyboardMarkup(keyboard)