import aiosqlite
import logging

logger = logging.getLogger(__name__)
DB_NAME = "casino_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Создание основной таблицы users
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0 NOT NULL,
                games_played INTEGER DEFAULT 0 NOT NULL,
                games_won INTEGER DEFAULT 0 NOT NULL,
                total_wagered INTEGER DEFAULT 0 NOT NULL,
                net_profit INTEGER DEFAULT 0 NOT NULL,
                nickname TEXT,
                referrer_id INTEGER DEFAULT NULL,
                referral_code TEXT UNIQUE,
                referrals_count INTEGER DEFAULT 0 NOT NULL,
                referral_earnings INTEGER DEFAULT 0 NOT NULL
            )
        ''')
        
        # Создание таблицы для отслеживания реферальных связей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bonus_paid BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                FOREIGN KEY (referred_id) REFERENCES users (user_id),
                UNIQUE(referrer_id, referred_id)
            )
        ''')
        
        await db.commit()
        logger.info("База данных и таблицы 'users', 'referrals' успешно проверены/созданы.")

async def add_user_if_not_exists(user_id: int, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not await cursor.fetchone():
            await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        else:
            await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        await db.commit()

async def get_user_balance(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def update_user_balance(user_id: int, amount: int, relative: bool = False):
    async with aiosqlite.connect(DB_NAME) as db:
        if relative:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        else:
            await db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

async def update_user_stats(user_id: int, bet: int, win_amount: int):
    is_win = 1 if win_amount > 0 else 0
    profit = win_amount - bet
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE users 
            SET games_played = games_played + 1,
                games_won = games_won + ?,
                total_wagered = total_wagered + ?,
                net_profit = net_profit + ?
            WHERE user_id = ?
        """, (is_win, bet, profit, user_id))
        await db.commit()

async def get_top_users(limit: int = 10) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT user_id, username, nickname, balance FROM users ORDER BY balance DESC LIMIT ?", (limit,))
        return await cursor.fetchall()

async def set_user_nickname(user_id: int, nickname: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET nickname = ? WHERE user_id = ?", (nickname, user_id))
        await db.commit()

async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_global_stats() -> dict | None:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT 
                COUNT(user_id) as total_users,
                SUM(balance) as total_balance,
                SUM(games_played) as total_games,
                SUM(total_wagered) as total_wager,
                SUM(net_profit) as casino_profit
            FROM users
        """)
        row = await cursor.fetchone()
        return dict(row) if row else None

# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

import secrets
import string

def generate_referral_code() -> str:
    """Генерирует уникальный реферальный код"""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))

async def get_user_by_referral_code(referral_code: str) -> int | None:
    """Находит пользователя по реферальному коду"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT user_id FROM users WHERE referral_code = ?", (referral_code,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def add_referral_relationship(referrer_id: int, referred_id: int) -> bool:
    """Создает реферальную связь между пользователями"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO referrals (referrer_id, referred_id) 
                VALUES (?, ?)
            """, (referrer_id, referred_id))
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        # Связь уже существует
        return False

async def get_user_referrals(user_id: int) -> list[aiosqlite.Row]:
    """Получает список рефералов пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT r.referred_id, u.username, u.nickname, r.created_at
            FROM referrals r
            JOIN users u ON r.referred_id = u.user_id
            WHERE r.referrer_id = ?
            ORDER BY r.created_at DESC
        """, (user_id,))
        return await cursor.fetchall()

async def update_referral_stats(user_id: int):
    """Обновляет статистику рефералов пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Подсчитываем количество рефералов
        cursor = await db.execute("""
            SELECT COUNT(*) FROM referrals WHERE referrer_id = ?
        """, (user_id,))
        referrals_count = (await cursor.fetchone())[0]
        
        # Обновляем статистику
        await db.execute("""
            UPDATE users 
            SET referrals_count = ?
            WHERE user_id = ?
        """, (referrals_count, user_id))
        await db.commit()

async def pay_referral_bonuses(referrer_id: int, referred_id: int) -> bool:
    """Начисляет бонусы за реферала"""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            # Начисляем 50 звезд новому пользователю
            await db.execute("""
                UPDATE users 
                SET balance = balance + 50 
                WHERE user_id = ?
            """, (referred_id,))
            
            # Начисляем 25 звезд рефереру
            await db.execute("""
                UPDATE users 
                SET balance = balance + 25,
                    referral_earnings = referral_earnings + 25
                WHERE user_id = ?
            """, (referrer_id,))
            
            # Отмечаем, что бонусы выплачены
            await db.execute("""
                UPDATE referrals 
                SET bonus_paid = TRUE 
                WHERE referrer_id = ? AND referred_id = ?
            """, (referrer_id, referred_id))
            
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"Ошибка при начислении реферальных бонусов: {e}")
        return False

async def get_user_referral_info(user_id: int) -> dict | None:
    """Получает информацию о рефералах пользователя"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT referral_code, referrals_count, referral_earnings
            FROM users 
            WHERE user_id = ?
        """, (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def ensure_referral_code(user_id: int) -> str:
    """Убеждается, что у пользователя есть реферальный код, создает если нет"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT referral_code FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        
        if row and row[0]:
            return row[0]
        
        # Генерируем новый код
        while True:
            new_code = generate_referral_code()
            try:
                await db.execute("UPDATE users SET referral_code = ? WHERE user_id = ?", (new_code, user_id))
                await db.commit()
                return new_code
            except aiosqlite.IntegrityError:
                # Код уже существует, пробуем другой
                continue