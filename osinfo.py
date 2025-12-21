import os
from pathlib import Path

import winshell
from winshell import shortcut

from utilities import main_logger

# Базовый список приложений
def _default_app_list():
    app_list = []

    app_info = {
        'name': 'Блокнот',
        'command': 'notepad.exe',
        'description': 'Простой редактор текста'
    }
    app_list.append(app_info)

    app_info = {
        'name': 'Paint',
        'command': 'mspaint.exe',
        'description': 'Простой редактор изображения'
    }
    app_list.append(app_info)

    app_info = {
        'name': 'Калькулятор',
        'command': 'calc.exe',
        'description': 'Для математических вычислений'
    }
    app_list.append(app_info)

    return app_list

# Список приложений в меню кнопки "Пуск"
def _start_menu_app_list():
    app_list = []

    logger = main_logger()

    # Пути к меню "Пуск"
    start_menu_paths = [
        Path(winshell.folder('CSIDL_COMMON_PROGRAMS')),  # Общее для всех пользователей
        Path(winshell.folder('CSIDL_PROGRAMS')),         # Для текущего пользователя
    ]

    for start_path in start_menu_paths:
        if not start_path.exists():
            continue

        # Ищем все ярлыки
        for lnk_path in start_path.rglob('*.lnk'):
            try:
                lnk = shortcut(str(lnk_path))
                app_info = {
                    'name': lnk_path.stem, # Имя файла
                    'command': lnk.path if lnk.path else '',  # Путь к исполняемому файлу
                    'description': lnk.description if lnk.description else ''  # Описание
                }
                app_list.append(app_info)

            except Exception as e:
                logger.error(f'Не удалось прочитать ярлык {lnk_path}: {e}')

    return app_list

# Список приложений для запуска
def os_app_list():
    return _default_app_list() + _start_menu_app_list()