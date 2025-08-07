from flask import Flask, render_template, request
import os
import uuid
import sqlite3
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_PATH = 'database.db'

# Создаём таблицу, если не существует
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE,
                upload_time TIMESTAMP,
                delete_after INTEGER
            )
        ''')
        conn.commit()

init_db()

# Добавление записи о файле
def add_file_record(filename, delete_after_days):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO files (filename, upload_time, delete_after) VALUES (?, ?, ?)',
                       (filename, datetime.utcnow(), delete_after_days))
        conn.commit()

# Удаление файла и записи из БД
def delete_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Удалён файл {filename}")
    except Exception as e:
        print(f"Ошибка при удалении файла {filename}: {e}")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM files WHERE filename = ?', (filename,))
        conn.commit()

# Фоновая задача для удаления просроченных файлов
def cleanup_task():
    while True:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT filename, upload_time, delete_after FROM files')
            rows = cursor.fetchall()
            now = datetime.utcnow()

            for filename, upload_time_str, delete_after_days in rows:
                upload_time = datetime.fromisoformat(upload_time_str)
                if delete_after_days > 0:
                    expiry_time = upload_time + timedelta(days=delete_after_days)
                    if now >= expiry_time:
                        delete_file(filename)
        time.sleep(60 * 60)  # Проверка каждый час

# Запуск фоновой задачи
threading.Thread(target=cleanup_task, daemon=True).start()

# Варианты сроков хранения
DELETE_OPTIONS = {
    '0': 0,
    '1': 30,
    '3': 90,
    '6': 180,
    '12': 365
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'images' not in request.files:
        return 'Нет файлов', 400

    delete_option = request.form.get('delete_after', '0')
    delete_after_days = DELETE_OPTIONS.get(delete_option, 0)

    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        return 'Файлы не выбраны', 400

    saved_filenames = []

    for file in files:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        add_file_record(filename, delete_after_days)
        saved_filenames.append(filename)

    return render_template('view_multiple.html', filenames=saved_filenames)

if __name__ == '__main__':
    app.run(debug=True)