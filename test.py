import os
import time

from funcdb import functions_db_path
from utilities import set_main_folder

# Путь к папкам скрипта
script_path = os.path.dirname(os.path.abspath(__file__))

# Устанавливаем основную папку проекта
set_main_folder(script_path)

###############################################################################
# Создание файла базы данных функций
db_path = functions_db_path()
open(db_path, 'w').close()

members = ['1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1','1',]

total = len(members)
for i, member in enumerate(members):
    print(f'\rРаспаковка: {i + 1} из {total} ({100 * (i + 1) / total:.0f}%)', end='')
    time.sleep(1)
