#!/usr/bin/env python3
"""
Скрипт миграции для добавления реферальной системы в существующую базу данных
"""

import asyncio
import aiosqlite
import logging
from database import generate_referral_code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = "casino_bot.db"

async def migrate_database():
    """Выполняет миграцию базы данных для реферальной системы"""
    async with aiosqlite.connect(DB_NAME) as db:
        logger.info("Начинаем миграцию базы данных...")
        
        # Проверяем, существуют ли уже новые поля
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        # Добавляем новые поля в таблицу users, если их нет
        if 'referrer_id' not in column_names:
            logger.info("Добавляем поле referrer_id...")
            await db.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT NULL")
        
        if 'referral_code' not in column_names:
            logger.info("Добавляем поле referral_code...")
            await db.execute("ALTER TABLE users ADD COLUMN referral_code TEXT")
        
        if 'referrals_count' not in column_names:
            logger.info("Добавляем поле referrals_count...")
            await db.execute("ALTER TABLE users ADD COLUMN referrals_count INTEGER DEFAULT 0 NOT NULL")
        
        if 'referral_earnings' not in column_names:
            logger.info("Добавляем поле referral_earnings...")
            await db.execute("ALTER TABLE users ADD COLUMN referral_earnings INTEGER DEFAULT 0 NOT NULL")
        
        # Создаем уникальный индекс для referral_code, если его нет
        try:
            await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code)")
            logger.info("Создан уникальный индекс для referral_code...")
        except Exception as e:
            logger.warning(f"Не удалось создать уникальный индекс: {e}")
        
        # Создаем таблицу referrals, если её нет
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='referrals'")
        if not await cursor.fetchone():
            logger.info("Создаем таблицу referrals...")
            await db.execute('''
                CREATE TABLE referrals (
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
        logger.info("Миграция структуры базы данных завершена.")
        
        # Генерируем реферальные коды для существующих пользователей
        logger.info("Генерируем реферальные коды для существующих пользователей...")
        cursor = await db.execute("SELECT user_id FROM users WHERE referral_code IS NULL")
        users_without_code = await cursor.fetchall()
        
        for (user_id,) in users_without_code:
            while True:
                new_code = generate_referral_code()
                try:
                    await db.execute("UPDATE users SET referral_code = ? WHERE user_id = ?", (new_code, user_id))
                    break
                except aiosqlite.IntegrityError:
                    # Код уже существует, пробуем другой
                    continue
        
        await db.commit()
        logger.info(f"Сгенерировано {len(users_without_code)} реферальных кодов.")
        
        # Обновляем статистику рефералов
        logger.info("Обновляем статистику рефералов...")
        await db.execute("""
            UPDATE users 
            SET referrals_count = (
                SELECT COUNT(*) 
                FROM referrals 
                WHERE referrals.referrer_id = users.user_id
            )
        """)
        
        await db.execute("""
            UPDATE users 
            SET referral_earnings = (
                SELECT COALESCE(SUM(25), 0)
                FROM referrals 
                WHERE referrals.referrer_id = users.user_id 
                AND referrals.bonus_paid = TRUE
            )
        """)
        
        await db.commit()
        logger.info("Статистика рефералов обновлена.")
        
        # Показываем итоговую статистику
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referral_code IS NOT NULL")
        users_with_code = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM referrals")
        total_referrals = (await cursor.fetchone())[0]
        
        logger.info(f"Миграция завершена успешно!")
        logger.info(f"Всего пользователей: {total_users}")
        logger.info(f"Пользователей с реферальными кодами: {users_with_code}")
        logger.info(f"Всего реферальных связей: {total_referrals}")

if __name__ == "__main__":
    asyncio.run(migrate_database()) 