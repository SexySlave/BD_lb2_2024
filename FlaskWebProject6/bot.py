import time
import telebot
import random
import threading
import os
from flask import Flask, render_template
from SQLTable import SQLTable  # Import your SQLTable class

# Telegram Bot Token
bot = telebot.TeleBot("7910115107:AAEmiBidGiNFNTL8LKeFkGfXzCd3jkYy8-c")

# Directories and Files
HOMEDIR = 'C:\\Users\\lewdm\\source\\repos\\FlaskWebProject6\\FlaskWebProject6\\data\\'
HELLO_FILE = HOMEDIR + 'hello.txt'
FACTS_FILE = HOMEDIR + 'facts.txt'
CITIES_FILE = HOMEDIR + 'city.txt'
LOG_DIR = HOMEDIR + 'logs/'
os.makedirs(LOG_DIR, exist_ok=True)

# Database Configuration
DB_CONFIG = {
    'user': 'j1007852',
    'password': 'el|N#2}-F8',
    'host': 'mysql.j1007852.myjino.ru',
    'database': 'j1007852'
}

# Tables
USERS_TABLE = "users"
MESSAGES_TABLE = "messages"
GAMES_TABLE = "games"
COMMANDS_LOG_TABLE = "commands_log"

# SQLTable Instances
users_table = SQLTable(db_config=DB_CONFIG, table_name=USERS_TABLE)
messages_table = SQLTable(DB_CONFIG, MESSAGES_TABLE)
games_table = SQLTable(DB_CONFIG, GAMES_TABLE)
commands_log_table = SQLTable(DB_CONFIG, COMMANDS_LOG_TABLE)

# Глобальная переменная для игры в города
used_cities = set()

# Загрузка городов из файла
def load_cities():
    try:
        with open(CITIES_FILE, 'r', encoding='utf-8') as file:
            cities = set(line.strip().lower() for line in file.readlines())
        return cities
    except FileNotFoundError:
        return set()  # Если файл не найден, возвращаем пустой набор

# Чтение городов из файла
cities = load_cities()

# Flask приложение
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/report')
def report():
    user_id = 123456  # Замените на динамический user_id
    report = fetch_user_report(user_id)
    return render_template('report.html', report=report)

# Функция для логирования команды в SQL таблицу
def log_command_to_sql(user_id, command, timestamp):
    try:
        commands_log_table.insert_row({
            'user_id': user_id,
            'command': command,
            'timestamp': timestamp
        })
    except Exception as e:
        print(f"Ошибка записи команды в таблицу: {e}")

# Обработчики команд Телеграм-бота

@bot.message_handler(commands=['start'])
def start_message(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_command_to_sql(message.chat.id, '/start', timestamp)

    greeting = get_random_line(HELLO_FILE)
    bot.reply_to(message, greeting)
    log_message(message.chat.id, f"Bot: {greeting}")

    # Стартуем отправку фактов в отдельном потоке
    threading.Thread(target=send_facts, args=(message.chat.id,)).start()

@bot.message_handler(commands=['fact'])
def fact_message(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_command_to_sql(message.chat.id, '/fact', timestamp)

    fact = get_random_line(FACTS_FILE)
    bot.reply_to(message, f'Факт: {fact}')
    log_message(message.chat.id, f"Bot: Факт: {fact}")

@bot.message_handler(commands=['report'])
def report_message(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_command_to_sql(message.chat.id, '/report', timestamp)

    user_id = message.chat.id
    report = fetch_user_report(user_id)
    bot.reply_to(message, report)

@bot.message_handler(commands=['game'])
def city_start(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_command_to_sql(message.chat.id, '/game', timestamp)

    global used_cities
    used_cities.clear()
    bot.reply_to(message, "Давайте играть в города! Назовите первый город или напишите 'стоп' для выхода.")
    log_message(message.chat.id, "Bot: Давайте играть в города! Назовите первый город или напишите 'стоп' для выхода.")

    # Запись новой игры
    try:
        games_table.insert_row({
            'user_id': message.chat.id,
            'start_time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': None  # Игра еще не закончена
        })
    except Exception as e:
        print(f"Ошибка записи игры в таблицу: {e}")

@bot.message_handler(commands=['help'])
def help_message(message):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    log_command_to_sql(message.chat.id, '/help', timestamp)

    help_text = (
        "Доступные команды:\n"
        "/start - Начать общение с ботом\n"
        "/fact - Получить случайный факт\n"
        "/game - Начать играть в города\n"
        "/report - Получить отчет о вашем пользователе\n"
        "/help - Показать этот список команд"
    )
    bot.reply_to(message, help_text)
    log_message(message.chat.id, "Bot: Отправка списка команд")

# Функция для генерации отчета пользователя
def fetch_user_report(user_id):
    try:
        user = users_table.fetch_one("user_id", user_id)

        if not user:
            new_user_data = {"user_id": user_id, "username": f"User{user_id}", "last_active": "никогда"}
            users_table.insert_row(new_user_data)
            return f"Пользователь с user_id {user_id} не найден. Создан новый пользователь."

        report = f"Отчет для пользователя: {user['username']}\n"
        report += f"Последняя активность: {user['last_active']}\n\n"

        # Получаем последние 10 сообщений
        messages = messages_table.fetch_all_ordered("timestamp", ascending=False)
        user_messages = messages[messages['user_id'] == user_id].head(10)
        report += "Последние сообщения:\n"
        for msg in user_messages.to_dict(orient="records"):
            report += f"[{msg['timestamp']}] {msg['message_text']}\n"

        # Получаем последние 5 игр
        games = games_table.fetch_all_ordered("start_time", ascending=False)
        user_games = games[games['user_id'] == user_id].head(5)
        report += "\nПоследние игры:\n"
        for game in user_games.to_dict(orient="records"):
            report += f"Игра с {game['start_time']} до {game['end_time']}\n"

        return report

    except Exception as e:
        return f"Ошибка базы данных: {e}"

# Функция для получения случайной строки из файла
def get_random_line(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        return random.choice(lines).strip()
    except FileNotFoundError:
        return "Файл не найден."

# Логирование сообщений
def log_message(user_id, message):
    log_file = os.path.join(LOG_DIR, f'{user_id}.log')
    with open(log_file, 'a', encoding='utf-8') as file:
        file.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} - {message}\n')

    # Запись в таблицу messages
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        messages_table.insert_row({
            'user_id': user_id,
            'message_text': message,
            'timestamp': timestamp
        })
    except Exception as e:
        print(f"Ошибка записи сообщения в таблицу: {e}")


# Функция для отправки случайных фактов
def send_facts(chat_id):
    while True:
        fact = get_random_line(FACTS_FILE)
        bot.send_message(chat_id, f'Факт: {fact}')
        log_message(chat_id, f"Bot: Факт: {fact}")
        time.sleep(360)

# Обработка игры в города
@bot.message_handler(func=lambda message: True)
def handle_city_game(message):
    global used_cities, cities
    user_city = message.text.strip().lower()
    log_message(message.chat.id, f"User: {user_city}")

    if user_city == 'стоп':
        bot.reply_to(message, "Игра окончена. Спасибо за игру!")
        used_cities.clear()
        log_message(message.chat.id, "Bot: Игра окончена. Спасибо за игру!")
        return

    if user_city in used_cities:
        bot.reply_to(message, "Этот город уже был использован. Назовите другой город.")
        log_message(message.chat.id, "Bot: Этот город уже был использован. Назовите другой город.")
        return

    if user_city not in cities:
        bot.reply_to(message, "Я не знаю такого города. Попробуйте ещё раз.")
        log_message(message.chat.id, "Bot: Я не знаю такого города. Попробуйте ещё раз.")
        return

    used_cities.add(user_city)
    last_letter = user_city[-1]
    if last_letter in 'ьъы':
        last_letter = user_city[-2]

    possible_cities = [city for city in cities if city.startswith(last_letter) and city not in used_cities]
    if possible_cities:
        bot_city = random.choice(possible_cities)
        used_cities.add(bot_city)
        bot.reply_to(message, f"Мой город: {bot_city.capitalize()}. Теперь ваш ход!")
        log_message(message.chat.id, f"Bot: Мой город: {bot_city.capitalize()}. Теперь ваш ход!")
    else:
        bot.reply_to(message, "Вы победили! У меня закончились города.")
        used_cities.clear()
        log_message(message.chat.id, "Bot: Вы победили! У меня закончились города.")

# Запуск Flask приложения и бота в отдельных потоках
if __name__ == '__main__':
    threading.Thread(target=bot.polling, args=(None, True)).start()
    app.run(debug=True, use_reloader=False)  # Flask будет запускать веб-интерфейс



