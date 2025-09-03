# -*- coding: utf-8 -*-
"""
Скрипт для тестирования подключения к Railway PostgreSQL
"""

import os
from pathlib import Path
from sqlalchemy import create_engine, text
from config import config

def test_railway_connection():
    """Тестирование подключения к Railway PostgreSQL"""

    print("🔄 Тестирование подключения к Railway PostgreSQL...")
    print("=" * 50)

    try:
        # Получаем URL базы данных
        database_url = config.get_database_url()
        print(f"📊 Database URL: {database_url}")

        # Создаем подключение
        engine = create_engine(database_url, echo=False)

        # Проверяем подключение
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Подключение успешно!")
            print(f"📋 PostgreSQL версия: {version}")

            # Проверяем, есть ли таблицы
            result = connection.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """))

            tables = result.fetchall()
            if tables:
                print(f"📋 Найденные таблицы: {[table[0] for table in tables]}")
            else:
                print("📋 Таблиц пока нет (будут созданы при первом запуске)")

        engine.dispose()
        print("🎉 Тест подключения пройден успешно!")

        return True

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("\n🔧 Возможные причины:")
        print("1. Неправильный DATABASE_URL")
        print("2. База данных Railway не запущена")
        print("3. Переменные окружения не настроены")
        print("4. Firewall блокирует подключение")
        return False

def show_current_config():
    """Показать текущую конфигурацию"""
    print("⚙️ Текущая конфигурация:")
    print(f"DATABASE_TYPE: {config.DATABASE_TYPE}")
    print(f"DATABASE_URL: {config.DATABASE_URL}")
    if not config.DATABASE_URL:
        print(f"DATABASE_HOST: {config.DATABASE_HOST}")
        print(f"DATABASE_PORT: {config.DATABASE_PORT}")
        print(f"DATABASE_NAME: {config.DATABASE_NAME}")
        print(f"DATABASE_USER: {config.DATABASE_USER}")
        print(f"DATABASE_PASSWORD: {'*' * len(config.DATABASE_PASSWORD) if config.DATABASE_PASSWORD else 'НЕ УСТАНОВЛЕН'}")

if __name__ == "__main__":
    print("🧪 Тест подключения к Railway PostgreSQL")
    print("=" * 50)

    # Показываем конфигурацию
    show_current_config()
    print()

    # Тестируем подключение
    success = test_railway_connection()

    if not success:
        print("\n💡 Инструкции по настройке:")
        print("1. Зайдите в Railway Dashboard")
        print("2. Выберите ваш проект с PostgreSQL")
        print("3. Перейдите в раздел 'Variables'")
        print("4. Скопируйте DATABASE_URL")
        print("5. Вставьте его в файл .env")
        print("6. Запустите этот скрипт снова")
