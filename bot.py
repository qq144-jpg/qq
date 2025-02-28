import telebot
import sqlite3
import random
import string
import threading
from datetime import datetime, timedelta
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
    access_code TEXT,
    code_expiry TEXT
)
''')
conn.commit()

def generate_secret_code():
    """Генерация случайного кода доступа"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def remove_expired_code(user_id):
    try:
        cursor.execute("SELECT code_expiry FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            try:
                expiry_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return  # Если ошибка в формате даты

            if datetime.now() >= expiry_time:
                cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                conn.commit()
                bot.send_message(user_id, "⏳ Время для ввода кода истекло. Попробуйте снова.")
    except:
        bot.send_message("❌ Произошла ошибка")

@bot.message_handler(commands=['start'])
def start(message: Message):
    try:
        """Запуск бота и проверка авторизации"""
        user_id = message.chat.id
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()

        if user:
            main_menu(message)
        else:
            secret_code = generate_secret_code()
            print(secret_code)
            expiry_time = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO users (user_id, access_code, code_expiry) VALUES (?, ?, ?)",
                           (user_id, secret_code, expiry_time))
            conn.commit()

            bot.send_message(user_id, f"🔑 Введите код доступа:")
            bot.register_next_step_handler(message, check_access_code)

            # Запуск таймера на удаление кода
            threading.Timer(300, remove_expired_code, args=[user_id]).start()
    except:
        bot.send_message("❌ Произошла ошибка")

def check_access_code(message: Message):
    try:
        """Проверка введенного кода"""
        user_id = message.chat.id
        cursor.execute("SELECT access_code FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result and message.text == result[0]:
            bot.send_message(user_id, "✅ Код верный! Добро пожаловать!")
            main_menu(message)
        else:
            bot.send_message(user_id, "❌ Неверный код! Попробуйте снова.")
            bot.register_next_step_handler(message, check_access_code)
    except:
        bot.send_message("❌ Произошла ошибка")

def main_menu(message: Message):
    try:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn_edit = KeyboardButton("Редактирование проверок")
        btn_view = KeyboardButton("Просмотреть проверки")
        markup.add(btn_edit, btn_view)
        bot.send_message(message.chat.id, "🏠 Главное меню:\nВыберите действие.", reply_markup=markup)
    except:
        bot.send_message("❌ Произошла ошибка")

@bot.message_handler(func=lambda message: message.text == "Редактирование проверок")
def edit_menu(message: Message):
    try:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn_add = KeyboardButton("➕ Добавить проверку")
        btn_edit = KeyboardButton("✏ Изменить проверку")
        btn_delete = KeyboardButton("❌ Удалить проверку")
        btn_menu = KeyboardButton("В меню")
        markup.add(btn_add, btn_edit, btn_delete, btn_menu)
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)
    except:
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "✏ Изменить проверку")
def edit_inspection(message: Message):
    try:
        bot.send_message(message.chat.id, "Введите ID проверки для редактирования:")
        bot.register_next_step_handler(message, get_edit_id)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)
def get_edit_id(message: Message):
    try:
        inspection_id = int(message.text)
        cursor.execute("SELECT * FROM inspections WHERE id = ?", (inspection_id,))
        record = cursor.fetchone()
        if record:
            bot.send_message(message.chat.id, f"Текущие данные проверки:\n\nid проверки: {record[0]}\n📅 Дата: {record[1]}\n🏢 Адрес: {record[2]}\n👤 Ответственный: {record[3]}\n🔍 Проверяющий: {record[4]}\n\nВведите новый адрес (или - для пропуска):")
            bot.register_next_step_handler(message, lambda msg: edit_address(msg, inspection_id, record))
        else:
            bot.send_message(message.chat.id, "❌ Проверка не найдена!")
    except ValueError:
        bot.send_message(message.chat.id, "⚠ Введите корректный ID!")

def edit_address(message: Message, inspection_id, old_data):
    try:
        new_address = message.text if message.text != "-" else old_data[2]
        bot.send_message(message.chat.id, "Введите новое ФИО ответственного (или - для пропуска):")
        bot.register_next_step_handler(message, lambda msg: edit_responsible(msg, inspection_id, new_address, old_data))
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

def edit_responsible(message: Message, inspection_id, new_address, old_data):
    try:
        new_responsible = message.text if message.text != "-" else old_data[3]
        bot.send_message(message.chat.id, "Введите новое ФИО проверяющего (или - для пропуска):")
        bot.register_next_step_handler(message, lambda msg: save_edit(msg, inspection_id, new_address, new_responsible, old_data))
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)
def save_edit(message: Message, inspection_id, new_address, new_responsible, old_data):
    try:
        new_inspector = message.text if message.text != "-" else old_data[4]
        cursor.execute("UPDATE inspections SET address = ?, responsible_person = ?, inspector = ? WHERE id = ?", (new_address, new_responsible, new_inspector, inspection_id))
        conn.commit()
        bot.send_message(message.chat.id, "✅ Проверка обновлена!")
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "❌ Удалить проверку")
def delete_inspection(message: Message):
    try:
        bot.send_message(message.chat.id, "Введите ID проверки для удаления:")
        bot.register_next_step_handler(message, confirm_delete)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

def confirm_delete(message: Message):
    try:
        inspection_id = int(message.text)
        cursor.execute("DELETE FROM inspections WHERE id = ?", (inspection_id,))
        conn.commit()
        bot.send_message(message.chat.id, "✅ Проверка удалена!")
    except ValueError:
        bot.send_message(message.chat.id, "⚠ Введите корректный ID!")

# Временное хранилище для данных о проверке перед подтверждением
temp_inspections = {}

@bot.message_handler(func=lambda message: message.text == "➕ Добавить проверку")
def start_inspection(message: Message):
    try:
        bot.send_message(message.chat.id, "Введите адрес проверки:")
        bot.register_next_step_handler(message, get_address)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

def get_address(message: Message):
    try:
        address = message.text.strip()
        today_date = datetime.today().strftime('%Y-%m-%d')  # Автоматически ставим текущую дату
        bot.send_message(message.chat.id, "Введите ФИО ответственного лица:")
        bot.register_next_step_handler(message, get_responsible_person, today_date, address)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

def validate_full_name(full_name: str) -> bool:
    return len(full_name.split()) == 3  # Проверяем, что введено ровно три слова

def get_responsible_person(message: Message, date, address):
    try:
        responsible_person = message.text.strip()
        if not validate_full_name(responsible_person):
            bot.send_message(message.chat.id, "⚠ Введите полное ФИО (Фамилия Имя Отчество):")
            bot.register_next_step_handler(message, get_responsible_person, date, address)
            return

        bot.send_message(message.chat.id, "Введите ФИО проверяющего:")
        bot.register_next_step_handler(message, get_inspector, date, address, responsible_person)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)
def get_inspector(message: Message, date, address, responsible_person):
    try:
        inspector = message.text.strip()
        if not validate_full_name(inspector):
            bot.send_message(message.chat.id, "⚠ Введите полное ФИО проверяющего (Фамилия Имя Отчество):")
            bot.register_next_step_handler(message, get_inspector, date, address, responsible_person)
            return

        confirm_inspection(message, date, address, responsible_person, inspector)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)
def confirm_inspection(message: Message, date, address, responsible_person, inspector):
    try:
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
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm")
def save_inspection(call):
    try:
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

        bot.send_message(chat_id, "✅ Проверка успешно сохранена!", main_menu(call.message))
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "edit")
def edit_inspection(call):
    try:
        """Позволяет пользователю заново ввести данные"""
        chat_id = call.message.chat.id
        bot.send_message(chat_id, "✏ Введите новый адрес проверки:")
        bot.register_next_step_handler(call.message, get_address)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "В меню")
def return_to_menu(message: Message):
    bot.send_message(message.chat.id, "🔙 Возвращаемся в меню...", reply_markup=main_menu(message))

@bot.message_handler(func=lambda message: message.text == "Просмотреть проверки")
def choose_search_method(message: Message):
    try:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn_all = KeyboardButton("🔍 Показать все")
        btn_date = KeyboardButton("📅 По дате")
        btn_address = KeyboardButton("🏢 По адресу")
        btn_name = KeyboardButton("👤 По ФИО")
        btn_menu = KeyboardButton("В меню")
        markup.add(btn_all, btn_date, btn_address, btn_name, btn_menu)
        bot.send_message(message.chat.id, "Как хотите найти проверку?", reply_markup=markup)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)
def paginate_records(records, page):
    per_page = 10
    start = page * per_page
    end = start + per_page
    return records[start:end], len(records) > end

@bot.message_handler(func=lambda message: message.text == "🔍 Показать все")
def show_all_inspections(message: Message, page=0):
    try:
        cursor.execute("SELECT * FROM inspections")
        records = cursor.fetchall()

        if not records:
            bot.send_message(message.chat.id, "❌ Проверок пока нет.")
            return

        show_search_results(message, records, "all", page)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📅 По дате")
def search_by_date(message: Message):
    try:
        bot.send_message(message.chat.id, "Введите дату (ГГГГ-ММ-ДД):")
        bot.register_next_step_handler(message, lambda msg: search_records(msg, "date", msg.text, "date"))
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🏢 По адресу")
def search_by_address(message: Message):
    try:
        bot.send_message(message.chat.id, "Введите адрес:")
        bot.register_next_step_handler(message, lambda msg: search_records(msg, "address", msg.text, "address"))
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "👤 По ФИО")
def search_by_responsible(message: Message):
    try:
        bot.send_message(message.chat.id, "Введите ФИО ответственного:")
        bot.register_next_step_handler(message, lambda msg: search_records(msg, "responsible_person", msg.text, "name"))
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)
def search_records(message, column, value, search_type, page=0):
    try:
        cursor.execute(f"SELECT * FROM inspections WHERE {column} LIKE ?", (f"%{value}%",))
        records = cursor.fetchall()
        if not records:
            bot.send_message(message.chat.id, "❌ Ничего не найдено.")
            return
        show_search_results(message, records, search_type, page)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

def show_search_results(message, records, search_type, page=0):
    try:
        paginated_records, has_next = paginate_records(records, page)
        response = "🔍 Найденные проверки:\n\n"
        for i, row in enumerate(paginated_records, start=1 + page * 10):
            response += f"{i}.\nid проверки: {row[0]}\n📅 {row[1]}\n🏢 {row[2]}\n👤 {row[3]}\n🔍 {row[4]}\n\n"

        markup = InlineKeyboardMarkup()
        if page > 0:
            markup.add(InlineKeyboardButton("⬅ Назад", callback_data=f"page_search_{search_type}_{page - 1}"))
        if has_next:
            markup.add(InlineKeyboardButton("Вперёд ➡", callback_data=f"page_search_{search_type}_{page + 1}"))

        bot.send_message(message.chat.id, response, reply_markup=markup)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("page_search_"))
def change_page_search(call):
    try:
        _, search_type, page = call.data.split("_")
        page = int(page)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        search_records(call.message, "date" if search_type == "date" else "address" if search_type == "address" else "responsible_person", call.message.text, search_type, page)
    except:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        btn = KeyboardButton("В меню")
        markup.add(btn)
        bot.send_message("❌ Произошла ошибка", reply_markup=markup)

if __name__ == '__main__':
    bot.polling(none_stop=True)
