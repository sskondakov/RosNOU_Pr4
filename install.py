import os

import uuid

from tqdm import tqdm

import configparser
from zipfile import ZipFile

# Пути к папке скрипта
script_path = os.path.dirname(os.path.abspath(__file__))

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
    for member in tqdm(members, desc='Распаковка'):
        zip_file.extract(member, extract_path)

# Удаление архива
os.remove(zip_path)

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