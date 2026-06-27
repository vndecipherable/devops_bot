#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import logging
import asyncpg
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Параметры БД
DB_CONFIG = {
    'database': os.getenv('DB_NAME', 'task_bot'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432')
}

LOG_PATH = os.getenv('LOG_PATH', '/var/log/postgresql/postgresql-17-main.log')
MASTER_IP = os.getenv('MASTER_IP', '127.0.0.1')


# ========== Состояния для FSM ==========
class AddDataState(StatesGroup):
    waiting_for_text = State()


# ========== Функции работы с БД ==========
async def get_db_connection():
    """Создание подключения к БД"""
    return await asyncpg.connect(**DB_CONFIG)


async def get_emails_from_db():
    """Получение всех email из БД"""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch('SELECT id, email, created_at FROM emails ORDER BY id')
        return rows
    finally:
        await conn.close()


async def get_phones_from_db():
    """Получение всех телефонов из БД"""
    conn = await get_db_connection()
    try:
        rows = await conn.fetch('SELECT id, phone, created_at FROM phones ORDER BY id')
        return rows
    finally:
        await conn.close()


async def save_email_to_db(email: str) -> bool:
    """Сохранение email в БД"""
    conn = await get_db_connection()
    try:
        await conn.execute('INSERT INTO emails (email) VALUES ($1)', email)
        return True
    except asyncpg.UniqueViolationError:
        return False
    finally:
        await conn.close()


async def save_phone_to_db(phone: str) -> bool:
    """Сохранение телефона в БД"""
    conn = await get_db_connection()
    try:
        await conn.execute('INSERT INTO phones (phone) VALUES ($1)', phone)
        return True
    except asyncpg.UniqueViolationError:
        return False
    finally:
        await conn.close()


# ========== Функции для работы с логами ==========
def get_replication_logs(lines: int = 50):
    """Чтение последних строк из лога репликации"""
    try:
        with open(LOG_PATH, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]
            
            repl_lines = [line for line in recent_lines 
                         if 'replication' in line.lower() 
                         or 'wal' in line.lower()
                         or 'standby' in line.lower()]
            
            return repl_lines if repl_lines else recent_lines
    except FileNotFoundError:
        return [f"Лог файл не найден: {LOG_PATH}"]


def extract_emails_from_text(text: str) -> list:
    """Извлечение email-адресов из текста"""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.findall(pattern, text)


def extract_phones_from_text(text: str) -> list:
    """Извлечение номеров телефонов из текста"""
    patterns = [
        r'\+?\d[\d\s\-\(\)]{7,}\d',
        r'\+7\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}',
        r'8\s?\(?\d{3}\)?\s?\d{3}[-\s]?\d{2}[-\s]?\d{2}',
        r'\d{3}[-\s]?\d{3}[-\s]?\d{4}',
    ]
    phones = []
    for pattern in patterns:
        phones.extend(re.findall(pattern, text))
    
    unique_phones = list(set([p.strip() for p in phones if len(p.strip()) >= 10]))
    return unique_phones


# ========== Команды бота ==========
@dp.message(Command('start'))
async def cmd_start(message: Message):
    """Обработка команды /start"""
    welcome_text = """
🤖 Бот для работы с базой данных

Доступные команды:

📧 /get_emails - Показать все email-адреса из БД
📞 /get_phone_numbers - Показать все телефоны из БД
🔄 /get_repl_logs - Показать логи репликации
➕ /add_email - Добавить email в БД (бот запросит текст)
➕ /add_phone - Добавить телефон в БД (бот запросит текст)

При добавлении данных:
- Бот автоматически найдет email/телефон в вашем сообщении
- Предложит сохранить найденные данные в БД
- Можно отказаться от сохранения

О репликации:
Логи репликации читаются из файла:
/var/log/postgresql/postgresql-17-main.log
    """
    await message.answer(welcome_text)


@dp.message(Command('get_emails'))
async def cmd_get_emails(message: Message):
    """Вывод всех email из БД"""
    rows = await get_emails_from_db()
    
    if not rows:
        await message.answer("📭 В базе данных нет email-адресов.")
        return
    
    response = "📧 Список email-адресов:\n\n"
    for row in rows:
        response += f"{row['id']}. {row['email']}\n"
        response += f"   Добавлен: {row['created_at']}\n\n"
    
    if len(response) > 4000:
        response = response[:4000] + "\n\n... (обрезано)"
    
    await message.answer(response)


@dp.message(Command('get_phone_numbers'))
async def cmd_get_phones(message: Message):
    """Вывод всех телефонов из БД"""
    rows = await get_phones_from_db()
    
    if not rows:
        await message.answer("📭 В базе данных нет номеров телефонов.")
        return
    
    response = "📞 Список номеров телефонов:\n\n"
    for row in rows:
        response += f"{row['id']}. {row['phone']}\n"
        response += f"   Добавлен: {row['created_at']}\n\n"
    
    if len(response) > 4000:
        response = response[:4000] + "\n\n... (обрезано)"
    
    await message.answer(response)


@dp.message(Command('get_repl_logs'))
async def cmd_get_repl_logs(message: Message):
    """Вывод логов репликации"""
    logs = get_replication_logs(30)
    
    if not logs:
        await message.answer("📭 Логи репликации не найдены или пусты.")
        return
    
    log_text = "\n".join(logs)
    if len(log_text) > 3900:
        log_text = log_text[-3900:] + "\n\n... (обрезано)"
    
    response = f"🔄 Логи репликации (последние {len(logs)} строк):\n\n{log_text}"
    await message.answer(response)


@dp.message(Command('add_email'))
async def cmd_add_email(message: Message, state: FSMContext):
    """Начало процесса добавления email"""
    await state.update_data(data_type='email')
    await state.set_state(AddDataState.waiting_for_text)
    await message.answer(
        "📧 Отправьте текст, из которого нужно извлечь email-адрес.\n\n"
        "Я найду все email в вашем сообщении и предложу сохранить их."
    )


@dp.message(Command('add_phone'))
async def cmd_add_phone(message: Message, state: FSMContext):
    """Начало процесса добавления телефона"""
    await state.update_data(data_type='phone')
    await state.set_state(AddDataState.waiting_for_text)
    await message.answer(
        "📞 Отправьте текст, из которого нужно извлечь номер телефона.\n\n"
        "Я найду все номера в вашем сообщении и предложу сохранить их."
    )


@dp.message(AddDataState.waiting_for_text)
async def process_text_for_extraction(message: Message, state: FSMContext):
    """Обработка текста для извлечения данных"""
    data = await state.get_data()
    data_type = data.get('data_type')
    text = message.text
    
    if data_type == 'email':
        found_items = extract_emails_from_text(text)
        save_func = save_email_to_db
        type_label = "email"
    else:
        found_items = extract_phones_from_text(text)
        save_func = save_phone_to_db
        type_label = "телефон"
    
    if not found_items:
        await message.answer(
            f"❌ В указанном тексте не найдено ни одного {type_label}.\n\n"
            f"Попробуйте снова с помощью команд /add_email или /add_phone."
        )
        await state.clear()
        return
    
    # Сохраняем данные в состоянии
    await state.update_data(
        found_items=found_items,
        save_func=save_func,
        type_label=type_label,
        data_type=data_type
    )
    
    items_list = "\n".join([f"• {item}" for item in found_items])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, сохранить", callback_data="save_yes"),
            InlineKeyboardButton(text="❌ Нет, отменить", callback_data="save_no")
        ]
    ])
    
    await message.answer(
        f"🔍 Найдено {len(found_items)} {type_label}:\n\n{items_list}\n\n"
        f"Сохранить их в базу данных?",
        reply_markup=keyboard
    )


@dp.callback_query()
async def handle_save_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора: сохранить или отменить"""
    data = await state.get_data()
    
    # Проверка, что данные есть
    if not data or 'found_items' not in data:
        await callback.message.edit_text(
            "❌ Данные не найдены. Попробуйте снова через /add_email или /add_phone."
        )
        await state.clear()
        await callback.answer()
        return
    
    if callback.data == "save_yes":
        found_items = data.get('found_items', [])
        save_func = data.get('save_func')
        type_label = data.get('type_label', 'данных')
        
        saved_count = 0
        exists_count = 0
        
        for item in found_items:
            if save_func:
                success = await save_func(item)
                if success:
                    saved_count += 1
                else:
                    exists_count += 1
        
        await callback.message.edit_text(
            f"✅ Результат сохранения:\n\n"
            f"• Успешно сохранено: {saved_count}\n"
            f"• Уже существовало: {exists_count}\n"
            f"• Всего обработано: {len(found_items)}"
        )
    
    elif callback.data == "save_no":
        await callback.message.edit_text(
            f"❌ Сохранение отменено. Найденные {data.get('type_label', 'данные')} не были добавлены в БД."
        )
    
    await state.clear()
    await callback.answer()


@dp.message()
async def unknown_command(message: Message):
    """Обработка неизвестных команд"""
    await message.answer(
        "❓ Неизвестная команда.\n"
        "Используйте /start для просмотра доступных команд."
    )


# ========== Запуск бота ==========
async def main():
    """Запуск бота"""
    logger.info("Бот запускается...")
    
    try:
        conn = await get_db_connection()
        await conn.execute('SELECT 1')
        await conn.close()
        logger.info("Подключение к PostgreSQL успешно")
    except Exception as e:
        logger.error(f"Ошибка подключения к БД: {e}")
    
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
