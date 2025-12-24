import os

import uuid

import configparser
from zipfile import ZipFile

from funcdb import functions_db_path
from utilities import set_main_folder

# Пути к папке скрипта
script_path = os.path.dirname(os.path.abspath(__file__))

# Устанавливаем основную папку проекта
set_main_folder(script_path)

###############################################################################
# Установка сторонних пакетов

# Путь к архиву сторонних пакетов и папке для распаковки
zip_path = os.path.join(script_path, 'amd64', 'Lib', 'site-packages.zip')
extract_path = os.path.dirname(zip_path)

# Сборка архива сторонних пакетов из частей (обходим ограничение GitHub)
with open(zip_path, 'wb') as zip_file:
    part = 1
    while True:
        part_path = f'{zip_path}.{part:03d}'
        if not os.path.exists(part_path):
            break

        with open(part_path, 'rb') as part_file:
            zip_file.write(part_file.read())

        os.remove(part_path)

        part += 1

# Распаковка сторонних пакетов
with ZipFile(zip_path, 'r') as zip_file:
    members = zip_file.namelist()
    total = len(members)
    for i, member in enumerate(members):
        print(f'\rРаспаковка: {i + 1} из {total} ({100 * (i + 1) / total:.0f}%)', end='')
        zip_file.extract(member, extract_path)

# Удаление архива
os.remove(zip_path)

###############################################################################
# Создание файла базы данных функций
db_path = functions_db_path()
open(db_path, 'w').close()

###############################################################################
# Подготовка файла конфигурации

# Путь к файлу настройки GigaChat
config_path = os.path.join(script_path, 'gigakeys.ini')

# Чтение настройки
config = configparser.ConfigParser()
config.read(config_path)

# Удаление флага первого запуска
if config.has_section('MAIN') and config.has_option('MAIN', 'first_run'):
    config.remove_option('MAIN', 'first_run')
    
# Запись настройки в  файл
with open(config_path, 'w', encoding='utf-8') as config_file:
        config.write(config_file)

###############################################################################
# Создание файла настройки GigaChat

# Путь к файлу настройки GigaChat
config_path = os.path.join(script_path, 'gigakeys.ini')

# Проверка наличия файла настройки
if not os.path.exists(config_path):
    # Создание настройки
    config = configparser.ConfigParser()

    # Создание секции GIGACHAT
    config.add_section('GIGACHAT')
    config.set('GIGACHAT', 'authorization_key', '')
    config.set('GIGACHAT', 'session_id', str(uuid.uuid4()))

    # Запись настройки в  файл
    with open(config_path, 'w', encoding='utf-8') as config_file:
            config.write(config_file)

###############################################################################
print('''\nПрограмма успешно установлена.

Укажите ключ авторизации GigaChat в файле gigakeys.ini.'''
    )