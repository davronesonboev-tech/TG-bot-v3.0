# -*- coding: utf-8 -*-
"""
Скрипт настройки Railway PostgreSQL для бота
"""

import os
from pathlib import Path

def setup_railway():
    """Настройка Railway PostgreSQL"""

    print("🚂 Настройка Railway PostgreSQL для Telegram бота")
    print("=" * 60)

    # Проверяем, есть ли уже .env файл
    env_path = Path('.env')
    if env_path.exists():
        print("⚠️  Файл .env уже существует!")
        overwrite = input("Перезаписать его? (y/N): ").lower().strip()
        if overwrite != 'y':
            print("❌ Настройка отменена")
            return

    print("\n📋 Вам нужно получить данные из Railway Dashboard:")
    print("1. Зайдите на https://railway.app/dashboard")
    print("2. Выберите ваш проект с PostgreSQL")
    print("3. Перейдите в раздел 'Variables'")
    print("4. Скопируйте значение DATABASE_URL")
    print()

    # Получаем данные от пользователя
    database_url = input("🔗 Вставьте DATABASE_URL из Railway: ").strip()
    if not database_url:
        print("❌ DATABASE_URL не может быть пустым!")
        return

    telegram_token = input("🤖 Введите токен Telegram бота: ").strip()
    if not telegram_token:
        print("❌ Токен бота не может быть пустым!")
        return

    admin_password = input("🔑 Введите пароль администратора: ").strip() or "admin123"
    user_password = input("🔑 Введите пароль пользователя: ").strip() or "user123"

    tz_offset = input("⏰ Часовой пояс (часов от UTC, по умолчанию 5): ").strip() or "5"

    # Создаем содержимое .env файла
    env_content = f"""# Конфигурация Telegram бота
TELEGRAM_TOKEN={telegram_token}

# Пароли для доступа
ADMIN_PASSWORD={admin_password}
USER_PASSWORD={user_password}

# Настройки базы данных (из Railway)
DATABASE_TYPE=postgresql
DATABASE_URL={database_url}

# Часовой пояс (в часах относительно UTC)
TZ_OFFSET_HOURS={tz_offset}
"""

    # Записываем в файл
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(env_content)

        print("\n✅ Файл .env успешно создан!")
        print("📁 Содержимое файла:")
        print("-" * 40)
        print(env_content)
        print("-" * 40)

        print("\n🧪 Теперь протестируем подключение...")
        print("Запустите: python test_railway_connection.py")

        print("\n📦 Для миграции данных запустите:")
        print("python migrate_to_postgres.py")

        print("\n🚀 Для запуска бота:")
        print("python main.py")

    except Exception as e:
        print(f"❌ Ошибка при создании файла: {e}")

if __name__ == "__main__":
    setup_railway()
