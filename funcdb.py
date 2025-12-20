import os

import heapq
import json
import numpy as np

import sqlite3

from utilities import config_value, main_folder

# Путь к базе данных функций
def _functions_db_path() -> str:
    # Имя файла базы данных
    functions_db_name = config_value(None, 'FUNCTIONS_DB', 'db_name')
    if functions_db_name is None:
        raise Exception("Не указано имя базы данных функций")

    # Путь к файлу базы данных
    return os.path.join(main_folder(), functions_db_name)

# Соединение с базой данных функций
def _functions_db_connection():
    # Путь к файлу базы данных
    functions_db_path = _functions_db_path()
    if not os.path.exists(functions_db_path):
        raise Exception("База данных функций не найдена")

    return sqlite3.connect(functions_db_path)

# Инициализация базы данных функций
def _try_init_functions_db(cursor):
    # Проверка наличия таблицы типов функций
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='function_types'"""
    )
    if cursor.fetchone() is None:
        # Создание таблицы типов функций
        cursor.execute("""
            CREATE TABLE function_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL UNIQUE
            )"""
        )

    # Создание предопределенных типов функций
    cursor.execute("""
        INSERT OR IGNORE INTO function_types (name) VALUES
        ('Launch application')
        """
    )

    # Проверка наличия таблицы функций
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='functions'"""
    )
    if cursor.fetchone() is None:
        # Создание таблицы функций
        cursor.execute("""
            CREATE TABLE functions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                type_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                FOREIGN KEY (type_id) REFERENCES function_types(id)
            )"""
        )

    # Проверка наличия таблицы промптов
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='prompts'"""
    )
    if cursor.fetchone() is None:
        # Создание таблицы промптов
        cursor.execute("""
            CREATE TABLE prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                function_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY (function_id) REFERENCES functions(id)
            )"""
        )

    # Проверка наличия таблицы эмбеддингов
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='embeddings'"""
    )
    if cursor.fetchone() is None:
        # Создание таблицы эмбеддингов
        cursor.execute("""
            CREATE TABLE embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                function_id INTEGER NOT NULL,
                prompt_id INTEGER,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                FOREIGN KEY (function_id) REFERENCES functions(id),
                FOREIGN KEY (prompt_id) REFERENCES prompts(id)
            )"""
        )

# Удаление функции
def delete_function(function_id: int):
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()

            # Инициализация базы данных функций
            _try_init_functions_db(cursor)

            # Удаляем связанные промпты
            cursor.execute('DELETE FROM prompts WHERE function_id = ?', (function_id,))
            # Удаляем функцию
            cursor.execute('DELETE FROM functions WHERE id = ?', (function_id,))
            
            connection.commit()
        
    except Exception as e:
        raise Exception(f"Ошибка удаления функции: {e}")

# Удаление промпта
def delete_prompt(prompt_id: int):
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()
            
            # Инициализация базы данных функций
            _try_init_functions_db(cursor)
            
            # Удаляем промпт
            cursor.execute('DELETE FROM prompts WHERE id = ?', (prompt_id,))
            connection.commit()
        
    except Exception as e:
        raise Exception(f"Ошибка удаления промпта: {e}")

# Удаление "свободных" эмбеддингов
def delete_free_embeddings():
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()

            # Инициализация базы данных функций
            _try_init_functions_db(cursor)

            # Ищем "свободные" эмбеддинги
            cursor.execute('''
                SELECT
                    e.id
                FROM
                    embeddings e
                        LEFT JOIN functions f
                        ON e.function_id = f.id
                        LEFT JOIN prompts p
                        ON e.prompt_id = p.id
                WHERE
                    f.id IS NULL
                    AND p.id IS NULL'''
            )

            # Удаляем найденное
            free_ids = []

            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break
                free_ids.extend([row[0] for row in rows])

            if free_ids:
                cursor.executemany('DELETE FROM embeddings WHERE id = ?', 
                    [(id_,) for id_ in free_ids]
                )

            connection.commit()
        
    except Exception as e:
        raise Exception(f'Ошибка удаления "свободных" эмбеддингов: {e}')

# Список функций
def functions_list(function_ids: list[int] = None) -> list[tuple[int, str, str, str, str]]:
    result = []

    try:
        # Соединение с базой данных и курсор
        with _functions_db_connection() as connection:
            cursor = connection.cursor()
            
            # Инициализация базы данных функций
            _try_init_functions_db(cursor)

            # Получаем список функций
            if function_ids is None:
                cursor.execute('''
                    SELECT f.id, f.name, f.description, ft.name as type, f.command
                    FROM functions f
                    LEFT JOIN function_types ft ON f.type_id = ft.id
                    ORDER BY f.name
                ''')

            else:
                placeholders = ','.join('?' * len(function_ids))
                cursor.execute(f'''
                    SELECT f.id, f.name, f.description, ft.name as type, f.command
                    FROM functions f
                    LEFT JOIN function_types ft ON f.type_id = ft.id
                    WHERE f.id IN ({placeholders})
                    ORDER BY f.name
                ''', function_ids)
            
            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break
                for row in rows:
                    result.append(row)
        
    except Exception as e:
        raise Exception(f"Ошибка получения списка функций: {e}")

    return result

# Список типов функций
def function_types():
    result = []

    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()
            
            # Инициализация базы данных функций
            _try_init_functions_db(cursor)

            # Получаем типы функций
            cursor.execute('SELECT id, name FROM function_types ORDER BY name')

            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break
                for row in rows:
                    result.append(row)
        
    except Exception as e:
        raise Exception(f"Ошибка получения типов функций: {e}")

    return result

# Получение деталей функции
def function_details(function_id: int):
    function_data = None
    prompts = []

    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()

            # Инициализация базы данных функций
            _try_init_functions_db(cursor)

            # Получаем детали функции
            cursor.execute('''
                SELECT f.id, f.name, f.description, f.command, ft.name as type, f.type_id as type_id
                FROM functions f
                LEFT JOIN function_types ft ON f.type_id = ft.id
                WHERE f.id = ?
            ''', (function_id,))
            
            function_data = cursor.fetchone()
            
            # Получаем промпты функции
            cursor.execute('''
                SELECT id, text FROM prompts 
                WHERE function_id = ? 
                ORDER BY id
            ''', (function_id,))
            
            prompts = cursor.fetchall()
        
    except Exception as e:
        raise Exception(f"Ошибка получения деталей функции: {e}")

    return function_data, prompts

# Получение промпта
def prompt(prompt_id: int) -> str:
    result = None
    
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()
            
            # Инициализация базы данных функций
            _try_init_functions_db(cursor)
            
            # Получаем промпт
            cursor.execute('SELECT text FROM prompts WHERE id = ?', (prompt_id,))
            prompt_data = cursor.fetchone()
            
            if prompt_data:
                result = prompt_data[0]
        
    except Exception as e:
        raise Exception(f"Ошибка получения промпта: {e}")

    return result

# Пересчет эмбеддингов
def rebuild_embeddings(embeddings_operation):
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()

            # Инициализация базы данных функций
            _try_init_functions_db(cursor)
            
            # Удаляем все
            cursor.execute('DELETE FROM embeddings')
            connection.commit()
            
            # Собираем информацию для расчета
            cursor.execute('''
                SELECT id as function_id, NULL as prompt_id, description as text
                FROM functions
                WHERE description IS NOT NULL'''
            )
            # TODO На будущее, для классификатора
            #cursor.execute('''
            #    SELECT id as function_id, NULL as prompt_id, description as text
            #    FROM functions
            #    WHERE description IS NOT NULL
            #    UNION ALL
            #    SELECT function_id, id, text
            #    FROM prompts
            #    WHERE text IS NOT NULL'''
            #)

            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    break

                # Собираем всё в списки
                all_texts = []
                text_info = []  # (function_id, prompt_id, text)

                for row in rows:
                    function_id, prompt_id, text = row
                    all_texts.append(text)
                    text_info.append((function_id, prompt_id, text))

                # Вычисялем эмбеддинги по списку
                all_embeddings = embeddings_operation(all_texts)

                # Запись вычисленных эмбеддингов
                insert_data = [
                    (func_id, prompt_id, text, json.dumps(embedding))
                    for (func_id, prompt_id, text), embedding in zip(text_info, all_embeddings)
                ]

                cursor.executemany(
                    '''INSERT INTO embeddings (function_id, prompt_id, text, embedding) 
                       VALUES (?, ?, ?, ?)''',
                    insert_data
                )
            
            connection.commit()

    except Exception as e:
        raise Exception(f"Не удалось пересчитать эмбеддинги: {e}")

def top_3_similar(query_embedding: list[float], limit: int = 3, batch_size: int = 1000) -> list[tuple[int, float]]:
    # Нормализуем запрос один раз
    query_emb = np.array(query_embedding, dtype=np.float32)
    query_norm = query_emb / np.linalg.norm(query_emb)
    
    # Список для хранения только топ-N (экономим память)
    top_results = []  # [(similarity, id), ...]
    
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()

            # Инициализация базы данных функций
            _try_init_functions_db(cursor)
            
            cursor.execute('SELECT function_id, embedding FROM embeddings')
            
            while True:
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    break
                
                # Распаковываем "пачку" в два списка за один проход
                batch_ids = []
                batch_embeddings = []
                
                for emb_id, emb_json in batch:
                    try:
                        emb_array = np.array(json.loads(emb_json), dtype=np.float32)
                        batch_ids.append(emb_id)
                        batch_embeddings.append(emb_array)

                    except (json.JSONDecodeError, ValueError):
                        continue
                
                if not batch_embeddings:
                    continue
                
                # 2D-массив из списка эмбеддингов
                batch_embs = np.stack(batch_embeddings)
                # Нормализуем все эмбеддинги
                batch_norms = batch_embs / np.linalg.norm(batch_embs, axis=1, keepdims=True)
                # Скалярное произведение нормализованных вектор = косинус угла
                similarities = np.dot(batch_norms, query_norm)
                
                # Обновляем heap только лучшими результатами
                for emb_id, sim in zip(batch_ids, similarities):
                    if len(top_results) < limit:
                        heapq.heappush(top_results, (sim, emb_id))
                    elif sim > top_results[0][0]:
                        heapq.heapreplace(top_results, (sim, emb_id))
    
    except Exception as e:
        raise Exception(f"Ошибка поиска похожих эмбеддингов: {e}")
    
    if not top_results:
        return []
    
    # Возвращаем отсортированные результаты (id, similarity)
    return [(emb_id, float(sim)) for sim, emb_id in sorted(top_results, reverse=True)]

# Сохранение функции
def save_function(function_id: int = None, name: str = None, type_id: int = None, 
                description: str = None, command: str = None) -> int:
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()
            
            # Инициализация базы данных функций
            _try_init_functions_db(cursor)
            
            if function_id:  # Обновление существующей
                cursor.execute('''
                    UPDATE functions 
                    SET name = ?, type_id = ?, description = ?, command = ?
                    WHERE id = ?
                ''', (name, type_id, description, command, function_id))
                connection.commit()

                result = function_id

            else:  # Создание новой
                cursor.execute('''
                    INSERT INTO functions (name, type_id, description, command)
                    VALUES (?, ?, ?, ?)
                ''', (name, type_id, description, command))
                connection.commit()

                result =  cursor.lastrowid
            
    except Exception as e:
        raise Exception(f"Ошибка сохранения функции: {e}")

    return result

# Сохранение промпта
def save_prompt(prompt_id: int = None, function_id: int = None, text: str = None) -> int:
    try:
        with _functions_db_connection() as connection:
            cursor = connection.cursor()

            # Инициализация базы данных функций
            _try_init_functions_db(cursor)
            
            if prompt_id:  # Обновление существующего
                cursor.execute('UPDATE prompts SET text = ? WHERE id = ?', (text, prompt_id))
                connection.commit()

                result = prompt_id

            else:  # Создание нового
                cursor.execute('INSERT INTO prompts (function_id, text) VALUES (?, ?)', 
                            (function_id, text))
                connection.commit()

                result = cursor.lastrowid
            
    except Exception as e:
        raise Exception(f"Ошибка сохранения промпта: {e}")

    return result
