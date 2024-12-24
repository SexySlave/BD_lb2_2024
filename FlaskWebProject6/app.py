from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import threading
import os
from bot import bot, fetch_user_report, log_message, get_random_line
from SQLTable import SQLTable
import pandas as pd


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Конфигурация базы данных
DB_CONFIG = {
    'user': 'j1007852',
    'password': 'el|N#2}-F8',
    'host': 'mysql.j1007852.myjino.ru',
    'database': 'j1007852',
    'charset': 'utf8mb4'
}

# Файлы данных
HOMEDIR = 'C:\\Users\\lewdm\\source\\repos\\FlaskWebProject6\\FlaskWebProject6\\data\\'
HELLO_FILE = os.path.join(HOMEDIR, 'hello.txt')
FACTS_FILE = os.path.join(HOMEDIR, 'facts.txt')

# Инициализация таблиц
users_table = SQLTable(DB_CONFIG, "user_roles")
messages_table = SQLTable(DB_CONFIG, "messages")
games_table = SQLTable(DB_CONFIG, "games")
commands_log_table = SQLTable(DB_CONFIG, "commands_log")

# Роли пользователей
roles = {
    'manager': 'Управляющий',
    'supervisor': 'Руководитель'
}

# --- Вспомогательные функции ---
def get_user_role(username):
    user = users_table.fetch_one("username", username)
    return user.get('role') if user else None

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def role_access_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            username = session.get('username')
            user_role = get_user_role(username)
            if not username or user_role not in allowed_roles:
                return "Access Denied", 403
            return f(*args, **kwargs)
        return wrapped
    return decorator

# --- Роуты приложения ---
@app.route("/")
def start():
    if 'username' in session:
        return redirect(url_for('index'))
    return render_template('start.html')

@app.route('/index')
@login_required
def index():
    return render_template('index.html', role=get_user_role(session['username']))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['user_id']
        password = request.form['password']
        user = users_table.fetch_one("username", username)
        if user and check_password_hash(user.get('password_hash'), password):
            session['username'] = username
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Неверные данные для входа")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['user_id']
        password = request.form['password']
        role = 'manager'  # Новые пользователи по умолчанию получают роль "manager"
        password_hash = generate_password_hash(password)
        try:
            users_table.insert_row({
                "username": username,
                "password_hash": password_hash,
                "role": role
            })
            return redirect(url_for('login'))
        except Exception as e:
            return render_template('register.html', error=f"Ошибка регистрации: {e}")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/assign_role', methods=['POST'])
@login_required
@role_access_required('supervisor')
def assign_role():
    try:
        username = request.form['username']
        role = request.form['role']
        if role not in roles:
            return "Неверная роль", 400
        users_table.update_row("username", username, {"role": role})
        return "Роль успешно назначена!"
    except Exception as e:
        return f"Ошибка назначения роли: {e}"

@app.route('/facts', methods=['GET', 'POST'])
@login_required
@role_access_required('manager', 'supervisor')
def facts():
    if request.method == 'POST':
        try:
            fact = request.form['fact']
            with open(FACTS_FILE, 'a', encoding='utf-8') as f:
                f.write(fact + '\n')
            return redirect(url_for('facts'))
        except Exception as e:
            return f"Ошибка сохранения факта: {e}"
    try:
        with open(FACTS_FILE, 'r', encoding='utf-8') as f:
            facts = f.readlines()
    except Exception as e:
        facts = []
        print(f"Ошибка чтения фактов: {e}")
    return render_template('facts.html', facts=facts)

@app.route('/hello', methods=['GET', 'POST'])
@login_required
@role_access_required('manager', 'supervisor')
def hello():
    if request.method == 'POST':
        try:
            greeting = request.form['greeting']
            with open(HELLO_FILE, 'a', encoding='utf-8') as f:
                f.write(greeting + '\n')
            return redirect(url_for('hello'))
        except Exception as e:
            return f"Ошибка сохранения приветствия: {e}"
    try:
        with open(HELLO_FILE, 'r', encoding='utf-8') as f:
            greetings = f.readlines()
    except Exception as e:
        greetings = []
        print(f"Ошибка чтения приветствий: {e}")
    return render_template('hello.html', greetings=greetings)

@app.route('/users')
@login_required
@role_access_required('supervisor')
def all_users():
    try:
        df_users = users_table.fetch_all()
        users = df_users.to_dict(orient="records")
        return render_template('users.html', users=users)
    except Exception as e:
        return f"Ошибка получения пользователей: {e}"

@app.route('/message_statistics')
@login_required
@role_access_required('supervisor')
def message_statistics():
    try:
        # Получение параметров фильтра
        user_id = request.args.get('user_id')
        command = request.args.get('command')
        date = request.args.get('date')

        # Получение данных
        df_commands = commands_log_table.fetch_all()

        # Применение фильтров
        if user_id:
            df_commands = df_commands[df_commands['user_id'].astype(str) == user_id]
        if command:
            df_commands = df_commands[df_commands['command'].str.contains(command, case=False, na=False)]
        if date:
            df_commands = df_commands[df_commands['timestamp'].dt.date == pd.to_datetime(date).date()]
        
        # Общая статистика
        total_commands = len(df_commands)
        commands = df_commands.to_dict(orient='records')
        
        # Группировка данных по командам
        command_counts = df_commands.groupby('command')['command'].count().to_dict()
        
        # Топ пользователей
        top_users = (
            df_commands.groupby('user_id')
            .size()
            .reset_index(name='command_count')
            .sort_values(by='command_count', ascending=False)
            .head(5)
            .to_dict(orient='records')
        )
        
        # Статистика за день
        daily_counts = (
            df_commands.groupby(df_commands['timestamp'].dt.date)
            .size()
            .reset_index(name='daily_command_count')
            .to_dict(orient='records')
        )
        
        return render_template(
            'message_statistics.html',
            commands=commands,
            total_commands=total_commands,
            command_counts=command_counts,
            top_users=top_users,
            daily_counts=daily_counts
        )
    except Exception as e:
        return f"Ошибка получения статистики: {e}"


@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@role_access_required('supervisor')
def delete_user(user_id):
    try:
        users_table.delete_row("username", user_id)
        return redirect(url_for('all_users'))
    except Exception as e:
        return f"Ошибка удаления пользователя: {e}"

@app.route('/edit_response', methods=['POST'])
@login_required
@role_access_required('manager', 'supervisor')
def edit_response():
    try:
        response_id = request.form['response_id']
        new_text = request.form['new_text']
        bot.update_response(response_id, new_text)
        return "Ответ успешно обновлен!"
    except Exception as e:
        return f"Ошибка редактирования ответа: {e}"

# --- Запуск приложения ---
def run_bot():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    app.run(debug=True, use_reloader=False)
