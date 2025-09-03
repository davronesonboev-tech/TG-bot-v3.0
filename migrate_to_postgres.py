# -*- coding: utf-8 -*-
"""
Скрипт миграции данных из SQLite в PostgreSQL
"""

import sqlite3
import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import User, Task, Notification, TaskHistory, Base
from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_sqlite_to_postgres():
    """Миграция данных из SQLite в PostgreSQL"""

    # Подключаемся к SQLite
    sqlite_conn = sqlite3.connect('task_manager.db')
    sqlite_conn.row_factory = sqlite3.Row

    # Создаем подключение к PostgreSQL
    postgres_engine = create_engine(config.get_database_url())
    Base.metadata.create_all(bind=postgres_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)
    postgres_db = PostgresSession()

    try:
        logger.info("🚀 Начинаем миграцию данных из SQLite в PostgreSQL")

        # Миграция пользователей
        logger.info("📝 Миграция пользователей...")
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute('SELECT * FROM users')
        users_data = sqlite_cursor.fetchall()

        users_map = {}  # Для маппинга старых ID в новые
        for user_row in users_data:
            user = User(
                telegram_id=user_row['telegram_id'],
                username=user_row['username'],
                first_name=user_row['first_name'],
                last_name=user_row['last_name'],
                role=user_row['role'],
                is_active=user_row['is_active'],
                registered_at=datetime.fromisoformat(user_row['registered_at']) if user_row['registered_at'] else datetime.utcnow(),
                last_activity=datetime.fromisoformat(user_row['last_activity']) if user_row['last_activity'] else datetime.utcnow()
            )
            postgres_db.add(user)
            postgres_db.flush()  # Получаем ID
            users_map[user_row['id']] = user.id

        postgres_db.commit()
        logger.info(f"✅ Миграция пользователей завершена: {len(users_data)} пользователей")

        # Миграция задач
        logger.info("📋 Миграция задач...")
        sqlite_cursor.execute('SELECT * FROM tasks')
        tasks_data = sqlite_cursor.fetchall()

        tasks_map = {}  # Для маппинга старых ID в новые
        for task_row in tasks_data:
            task = Task(
                title=task_row['title'],
                description=task_row['description'],
                creator_id=users_map.get(task_row['creator_id']),
                assignee_id=users_map.get(task_row['assignee_id']) if task_row['assignee_id'] else None,
                status=task_row['status'],
                priority=task_row['priority'],
                deadline=datetime.fromisoformat(task_row['deadline']) if task_row['deadline'] else None,
                created_at=datetime.fromisoformat(task_row['created_at']) if task_row['created_at'] else datetime.utcnow(),
                updated_at=datetime.fromisoformat(task_row['updated_at']) if task_row['updated_at'] else datetime.utcnow(),
                completed_at=datetime.fromisoformat(task_row['completed_at']) if task_row['completed_at'] else None
            )
            postgres_db.add(task)
            postgres_db.flush()  # Получаем ID
            tasks_map[task_row['id']] = task.id

        postgres_db.commit()
        logger.info(f"✅ Миграция задач завершена: {len(tasks_data)} задач")

        # Миграция уведомлений
        logger.info("🔔 Миграция уведомлений...")
        sqlite_cursor.execute('SELECT * FROM notifications')
        notifications_data = sqlite_cursor.fetchall()

        for notif_row in notifications_data:
            notification = Notification(
                user_id=users_map.get(notif_row['user_id']),
                task_id=tasks_map.get(notif_row['task_id']),
                type=notif_row['type'],
                message=notif_row['message'],
                is_sent=notif_row['is_sent'],
                scheduled_at=datetime.fromisoformat(notif_row['scheduled_at']) if notif_row['scheduled_at'] else datetime.utcnow(),
                sent_at=datetime.fromisoformat(notif_row['sent_at']) if notif_row['sent_at'] else None,
                created_at=datetime.fromisoformat(notif_row['created_at']) if notif_row['created_at'] else datetime.utcnow()
            )
            postgres_db.add(notification)

        postgres_db.commit()
        logger.info(f"✅ Миграция уведомлений завершена: {len(notifications_data)} уведомлений")

        # Миграция истории задач
        logger.info("📚 Миграция истории задач...")
        sqlite_cursor.execute('SELECT * FROM task_history')
        history_data = sqlite_cursor.fetchall()

        for history_row in history_data:
            history = TaskHistory(
                task_id=tasks_map.get(history_row['task_id']),
                user_id=users_map.get(history_row['user_id']),
                action=history_row['action'],
                old_value=history_row['old_value'],
                new_value=history_row['new_value'],
                created_at=datetime.fromisoformat(history_row['created_at']) if history_row['created_at'] else datetime.utcnow()
            )
            postgres_db.add(history)

        postgres_db.commit()
        logger.info(f"✅ Миграция истории задач завершена: {len(history_data)} записей")

        logger.info("🎉 Миграция данных успешно завершена!")
        logger.info("📝 Рекомендации:")
        logger.info("   1. Проверьте работу бота с новой базой данных")
        logger.info("   2. Если все работает корректно, можете удалить файл task_manager.db")
        logger.info("   3. Обновите переменные окружения в Railway на DATABASE_TYPE=postgresql")

    except Exception as e:
        postgres_db.rollback()
        logger.error(f"❌ Ошибка при миграции: {e}")
        raise
    finally:
        sqlite_conn.close()
        postgres_db.close()

if __name__ == "__main__":
    print("🔄 Скрипт миграции данных из SQLite в PostgreSQL")
    print("=" * 50)

    # Проверяем наличие SQLite файла
    import os
    if not os.path.exists('task_manager.db'):
        print("❌ Файл task_manager.db не найден!")
        print("Убедитесь, что файл находится в текущей директории.")
        exit(1)

    # Показываем информацию о миграции
    sqlite_conn = sqlite3.connect('task_manager.db')
    sqlite_cursor = sqlite_conn.cursor()

    for table in ['users', 'tasks', 'notifications', 'task_history']:
        sqlite_cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = sqlite_cursor.fetchone()[0]
        print(f"📊 {table}: {count} записей")

    sqlite_conn.close()

    print("\n⚠️  ВНИМАНИЕ!")
    print("Этот скрипт перенесет все данные из SQLite в PostgreSQL.")
    print("Убедитесь, что:")
    print("1. PostgreSQL база данных создана и доступна")
    print("2. Переменные окружения настроены правильно")
    print("3. У вас есть резервная копия данных")

    response = input("\nПродолжить миграцию? (yes/no): ").lower().strip()
    if response == 'yes':
        migrate_sqlite_to_postgres()
    else:
        print("❌ Миграция отменена")
