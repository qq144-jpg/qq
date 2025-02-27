import telebot
import sqlite3
from datetime import datetime
import random
import string
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = '7600627967:AAHJmBLKO51uDxouKMG8vBi0iOizbAJungA'
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('fire_safety.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблицы для проверок и пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS inspections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    address TEXT,
    responsible_person TEXT,
    inspector TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    access_code TEXT
)
''')
conn.commit()

# Устанавливаем секретный код для входа (его можно поменять)
SECRET_CODE = "GOLD345"

@bot.message_handler(commands=['start'])
def start(message: Message):
    """Запуск бота и проверка авторизации"""
    user_id = message.chat.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if user:
        main_menu(message)
    else:
        bot.send_message(user_id, "🔑 Введите код доступа:")
        bot.register_next_step_handler(message, check_access_code)

def check_access_code(message: Message):
    """Проверка введенного кода"""
    user_id = message.chat.id
    if message.text == SECRET_CODE:
        cursor.execute("INSERT INTO users (user_id, access_code) VALUES (?, ?)", (user_id, SECRET_CODE))
        conn.commit()
        bot.send_message(user_id, "✅ Код верный! Добро пожаловать!")
        main_menu(message)
    else:
        bot.send_message(user_id, "❌ Неверный код! Попробуйте снова.")
        bot.register_next_step_handler(message, check_access_code)

def main_menu(message: Message):
    """Вывод главного меню"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_add = KeyboardButton("Добавить проверку")
    btn_view = KeyboardButton("Просмотреть проверки")
    markup.add(btn_add, btn_view)
    bot.send_message(message.chat.id, "🏠 Главное меню", reply_markup=markup)

# Временное хранилище для данных о проверке перед подтверждением
temp_inspections = {}

@bot.message_handler(func=lambda message: message.text == "Добавить проверку")
def start_inspection(message: Message):
    bot.send_message(message.chat.id, "Введите адрес проверки:")
    bot.register_next_step_handler(message, get_address)


def get_address(message: Message):
    address = message.text.strip()
    today_date = datetime.today().strftime('%Y-%m-%d')  # Автоматически ставим текущую дату
    bot.send_message(message.chat.id, "Введите ФИО ответственного лица:")
    bot.register_next_step_handler(message, get_responsible_person, today_date, address)


def validate_full_name(full_name: str) -> bool:
    return len(full_name.split()) == 3  # Проверяем, что введено ровно три слова


def get_responsible_person(message: Message, date, address):
    responsible_person = message.text.strip()
    if not validate_full_name(responsible_person):
        bot.send_message(message.chat.id, "⚠ Введите полное ФИО (Фамилия Имя Отчество):")
        bot.register_next_step_handler(message, get_responsible_person, date, address)
        return

    bot.send_message(message.chat.id, "Введите ФИО проверяющего:")
    bot.register_next_step_handler(message, get_inspector, date, address, responsible_person)


def get_inspector(message: Message, date, address, responsible_person):
    inspector = message.text.strip()
    if not validate_full_name(inspector):
        bot.send_message(message.chat.id, "⚠ Введите полное ФИО проверяющего (Фамилия Имя Отчество):")
        bot.register_next_step_handler(message, get_inspector, date, address, responsible_person)
        return

    confirm_inspection(message, date, address, responsible_person, inspector)


def confirm_inspection(message: Message, date, address, responsible_person, inspector):
    """Сохраняет данные во временное хранилище и отправляет кнопки подтверждения"""
    chat_id = message.chat.id
    temp_inspections[chat_id] = {
        "date": date,
        "address": address,
        "responsible_person": responsible_person,
        "inspector": inspector
    }

    markup = InlineKeyboardMarkup()
    btn_confirm = InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")
    btn_edit = InlineKeyboardButton("✏ Изменить", callback_data="edit")
    markup.add(btn_confirm, btn_edit)

    bot.send_message(
        chat_id,
        f"🔍 Проверьте данные перед сохранением:\n\n"
        f"📅 Дата: {date}\n"
        f"🏢 Адрес: {address}\n"
        f"👤 Ответственный: {responsible_person}\n"
        f"🔍 Проверяющий: {inspector}",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "confirm")
def save_inspection(call):
    """Сохраняет проверку после подтверждения"""
    chat_id = call.message.chat.id
    if chat_id not in temp_inspections:
        bot.send_message(chat_id, "❌ Ошибка: данные не найдены. Начните заново.")
        return

    data = temp_inspections.pop(chat_id)

    cursor.execute(
        "INSERT INTO inspections (date, address, responsible_person, inspector) VALUES (?, ?, ?, ?)",
        (data["date"], data["address"], data["responsible_person"], data["inspector"])
    )
    conn.commit()

    bot.send_message(chat_id, "✅ Проверка успешно сохранена!", reply_markup=main_menu(call.message))


@bot.callback_query_handler(func=lambda call: call.data == "edit")
def edit_inspection(call):
    """Позволяет пользователю заново ввести данные"""
    chat_id = call.message.chat.id
    bot.send_message(chat_id, "✏ Введите новый адрес проверки:")
    bot.register_next_step_handler(call.message, get_address)


@bot.message_handler(func=lambda message: message.text == "Вернуться в меню")
def return_to_menu(message: Message):
    bot.send_message(message.chat.id, "🔙 Возвращаемся в меню...", reply_markup=main_menu(message))


@bot.message_handler(func=lambda message: message.text == "Просмотреть проверки")
def choose_search_method(message: Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    btn_all = KeyboardButton("🔍 Показать все")
    btn_date = KeyboardButton("📅 По дате")
    btn_address = KeyboardButton("🏢 По адресу")
    btn_name = KeyboardButton("👤 По ФИО")
    btn_menu = KeyboardButton("🔙 В меню")
    markup.add(btn_all, btn_date, btn_address, btn_name, btn_menu)
    bot.send_message(message.chat.id, "Как хотите найти проверку?", reply_markup=markup)

def paginate_records(records, page):
    per_page = 10
    start = page * per_page
    end = start + per_page
    return records[start:end], len(records) > end

@bot.message_handler(func=lambda message: message.text == "🔍 Показать все")
def show_all_inspections(message: Message, page=0):
    cursor.execute("SELECT * FROM inspections")
    records = cursor.fetchall()

    if not records:
        bot.send_message(message.chat.id, "❌ Проверок пока нет.")
        return

    paginated_records, has_next = paginate_records(records, page)
    response = "📋 Список проверок:\n\n"
    for i, row in enumerate(paginated_records, start=1 + page * 10):
        response += f"{i}. 📅 {row[1]}\n🏢 {row[2]}\n👤 {row[3]}\n🔍 {row[4]}\n\n"

    markup = InlineKeyboardMarkup()
    if page > 0:
        markup.add(InlineKeyboardButton("⬅ Назад", callback_data=f"page_all_{page - 1}"))
    if has_next:
        markup.add(InlineKeyboardButton("Вперёд ➡", callback_data=f"page_all_{page + 1}"))

    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("page_all_"))
def change_page_all(call):
    page = int(call.data.split("_")[2])
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_all_inspections(call.message, page)

def search_records(message, column, value, search_type):
    cursor.execute(f"SELECT * FROM inspections WHERE {column} LIKE ?", (f"%{value}%",))
    records = cursor.fetchall()
    if not records:
        bot.send_message(message.chat.id, "❌ Ничего не найдено.")
        return
    show_search_results(message, records, search_type)

def show_search_results(message, records, search_type, page=0):
    paginated_records, has_next = paginate_records(records, page)
    response = "🔍 Найденные проверки:\n\n"
    for i, row in enumerate(paginated_records, start=1 + page * 10):
        response += f"{i}. 📅 {row[1]}\n🏢 {row[2]}\n👤 {row[3]}\n🔍 {row[4]}\n\n"

    markup = InlineKeyboardMarkup()
    if page > 0:
        markup.add(InlineKeyboardButton("⬅ Назад", callback_data=f"page_search_{search_type}_{page - 1}"))
    if has_next:
        markup.add(InlineKeyboardButton("Вперёд ➡", callback_data=f"page_search_{search_type}_{page + 1}"))

    bot.send_message(message.chat.id, response, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("page_search_"))
def change_page_search(call):
    _, search_type, page = call.data.split("_")
    page = int(page)
    bot.delete_message(call.message.chat.id, call.message.message_id)
    search_records(call.message, "date" if search_type == "date" else "address" if search_type == "address" else "responsible_person", "", search_type)

if __name__ == '__main__':
    bot.polling(none_stop=True)
