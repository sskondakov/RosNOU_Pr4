import os
import sys
import threading

from datetime import datetime
import json
from tqdm import tqdm

import logging

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import pystray
from PIL import Image, ImageDraw, ImageFont

from agents import BaseAIAgentManager, AIAgentMessage
from assistagents import AppListAgent, AssistantAgent, LaunchAppAgent
from gigagents import new_app_description
from osinfo import os_app_list
from semsearch import RubertTiny2SemanticSearch
from funcdb import function_id_by_command, function_type_id, save_function, save_prompt
from funceditor import FunctionEditorWindow
from utilities import set_main_folder, main_folder, config_value, set_config_value, set_logging_level, main_logger

# Путь к папкам скрипта
script_path = os.path.dirname(os.path.abspath(__file__))

# Устанавливаем основную папку проекта
set_main_folder(script_path)

# Определение режима запуска
DEBUG_MODE = False
for arg in reversed(sys.argv):
    if arg == 'debug':
        DEBUG_MODE = True

# Установка уровня логгирования
if DEBUG_MODE:
    set_logging_level(logging.DEBUG)

# Менеджер AI-агентов
class AIAgentManager(BaseAIAgentManager):
    def __init__(self):
        # Инициализация AI-агентов
        super().__init__(
            [
                AppListAgent(),
                AssistantAgent(),
                LaunchAppAgent()
            ]
        )
# Экземпляр менеджера AI-агентов
AGENT_MANAGER = AIAgentManager()

# История диалогов
class DialogHistory:
    def __init__(self):
        # Получение логгера
        self._logger = main_logger()

        # Установка имени файла истории
        history_file_name = config_value(None, 'DIALOG_HISTORY', 'file_name')
        if history_file_name is None:
            raise Exception('Не указан файл истории диалогов')
        self.history_file_path = os.path.join(main_folder(), history_file_name)

        # Загрузка истории
        self._dialogs = self._load_history()
    
    #Загрузка истории
    def _load_history(self):
        try:
            if os.path.exists(self.history_file_path):
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
                    
        except Exception as e:
            # Логгирование на уровне отладки
            self._logger.debug(f"Ошибка загрузки истории: {e}")

        return []

    # Сохранение истории    
    def _save_history(self):
        try:
            with open(self.history_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._dialogs, f, ensure_ascii=False, indent=2)

        except Exception as e:
            raise Exception(f"Ошибка сохранения истории: {e}")

    # Добавление нового диалога    
    def add_dialog(self, user_query, ai_response, solved=None):
        dialog = {
            'id': len(self._dialogs) + 1,
            'timestamp': datetime.now().isoformat(),
            'user_query': user_query,
            'ai_response': ai_response,
            'solved': solved  # None, True, False
        }
        self._dialogs.append(dialog)

        # Сохранение истории
        self._save_history()

        return dialog
    
    # Установка статуса диалога
    def set_dialog_solved(self, dialog_id, solved):
        if 0 <= dialog_id - 1 < len(self._dialogs):
            self._dialogs[dialog_id - 1]['solved'] = solved
            self._save_history()
            return True
        return False

    # Список последних диалогов
    def recent_dialogs(self, count=10):
        return self._dialogs[-count:] if self._dialogs else []

# Главное окно приложения
class MainWindow:
    def __init__(self):
        # Получение логгера
        self._logger = main_logger()
        
        # Создание окна и интерфейса
        self._create_window()
        self._create_ui()

        # Получение истории диалога
        self._max_dialog_length = 10
        self._dialog_history = DialogHistory()
        self._load_recent_dialogs()
    
    # Создание главного окна
    def _create_window(self):
        self.root = tk.Tk()

        # Настройка окна
        self.root.title("OS Assistant")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Обработчик закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # Создание интерфейса
    def _create_ui(self):
        # Основной фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Веса растягивания первого столбца и колонки
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Фрейм истории диалогов
        history_frame = ttk.LabelFrame(main_frame, text="История диалогов", padding="5")
        history_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)
        
        # Текстовое поле истории
        self.history_text = scrolledtext.ScrolledText(
            history_frame, 
            height=20, 
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.history_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Фрейм поля ввода
        input_frame = ttk.LabelFrame(main_frame, text="Запрос", padding="5")
        input_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        input_frame.columnconfigure(0, weight=1)
        
        # Поле ввода
        self.input_text = tk.Text(input_frame, height=4, wrap=tk.WORD)
        self.input_text.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        # Фрейм кнопок
        buttons_frame = ttk.Frame(input_frame)
        buttons_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Кнопка отправить
        ttk.Button(
            buttons_frame, 
            text="Отправить (Enter)", 
            command=self._send_query
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        # Кнопка очистить
        ttk.Button(
            buttons_frame, 
            text="Очистить", 
            command=self._clear_input
        ).pack(side=tk.LEFT)
        
        # Привязка клавиши Enter
        self.input_text.bind('<Control-Return>', lambda e: self._send_query())
        self.input_text.bind('<Return>', lambda e: self._send_query())
        
        # Строка  статуса
        self.status_var = tk.StringVar()
        self.status_var.set("Готов к работе")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, sticky=(tk.W, tk.E))
    
    # Загрузка последних диалогов
    def _load_recent_dialogs(self):
        # Включаем и очищаем поле истории
        self.history_text.config(state=tk.NORMAL)
        self.history_text.delete(1.0, tk.END)
        
        # Загружаем последние диалоги
        recent_dialogs = self._dialog_history.recent_dialogs(self._max_dialog_length)
        for dialog in recent_dialogs:
            if dialog['solved'] is None:
                # Для диалогов без статуса создаём интерактивную версию с кнопками
                self._add_dialog_to_history(dialog, True)

            else:
                # Для диалогов со статусом - статическую версию
                self._add_dialog_to_history(dialog, False)
        
        # Устанавливаем оформление элементов текста
        self.history_text.tag_configure('user_time', foreground='blue', font=('TkDefaultFont', 9, 'bold'))
        self.history_text.tag_configure('ai_time', foreground='green', font=('TkDefaultFont', 9, 'bold'))
        self.history_text.tag_configure('status_solved', foreground='green', font=('TkDefaultFont', 9, 'italic'))
        self.history_text.tag_configure('status_not_solved', foreground='red', font=('TkDefaultFont', 9, 'italic'))
        self.history_text.tag_configure('separator', foreground='gray')
        
        # Выключаем поле истории и перематываем в конец
        self.history_text.config(state=tk.DISABLED)
        self._scroll_to_bottom()

    # Отправка запроса
    def _send_query(self):
        # Получаем запрос пользователя
        query = self.input_text.get(1.0, tk.END).strip()
        if not query:
            return
        
        # Устанавливаем строку статуса
        self.status_var.set("Обработка запроса...")

        # Обновляем форму
        self.root.update()
        
        try:
            # Создаем сообщение AI-агентам
            question = AIAgentMessage()
            question.content = query
            
            # Получаем ответ от AI-агентов
            AGENT_MANAGER.clear_context()
            answer = AGENT_MANAGER.answer(question)
            
            # Добавляем диалог в историю
            dialog = self._dialog_history.add_dialog(query, answer.content, None)
            
            # Добавляем диалог в текстовое поле
            self.history_text.config(state=tk.NORMAL)
            self._add_dialog_to_history(dialog, interactive=True)
            self.history_text.config(state=tk.DISABLED)
            self._scroll_to_bottom()

            # Очищаем поле ввода запроса
            self.input_text.delete(1.0, tk.END)

            # Устанавливаем строку статуса
            self.status_var.set("Готов к работе")
            
        except Exception as e:
            # Логгирование на уровне ошибок
            self._logger.error(f"Ошибка при обработке запроса: {str(e)}")
            
            # Устанавливаем строку статуса
            self.status_var.set(f"Ошибка: {str(e)}")

        # Обновляем форму
        self.root.update()

    # Добавление диалога в историю
    def _add_dialog_to_history(self, dialog, interactive=None):
        # Определяем режим отображения
        if interactive is None:
            interactive = (dialog['solved'] is None)
        
        # Форматирование времени
        timestamp = datetime.fromisoformat(dialog['timestamp']).strftime('%H:%M:%S')
        
        # Добавление текста диалога
        self.history_text.insert(tk.END, f"[{timestamp}] Вы:\n", 'user_time')
        self.history_text.insert(tk.END, f"{dialog['user_query']}\n\n", 'user_text')
        self.history_text.insert(tk.END, f"AI Assistant:\n", 'ai_time')
        self.history_text.insert(tk.END, f"{dialog['ai_response']}\n\n", 'ai_text')
        
        if interactive:
            # Интерактивная версия с кнопками
            self._add_interaction_buttons(dialog['id'])
        else:
            # Статичная версия со статусом
            if dialog['solved'] is not None:
                status = "✓ Решено" if dialog['solved'] else "✗ Не решено"
                status_tag = 'status_solved' if dialog['solved'] else 'status_not_solved'
                self.history_text.insert(tk.END, f"Статус: {status}\n", status_tag)
        
        # Разделитель
        separator = "\n\n" if interactive else ""
        self.history_text.insert(tk.END, f"{separator}{'-' * 50}\n\n", 'separator')

    # Диалог по индентификатору
    def _dialog_by_id(self, dialog_id: int):
        all_dialogs = self._dialog_history.recent_dialogs(self._max_dialog_length)
        for dialog in all_dialogs:
            if dialog['id'] == dialog_id:
                return dialog
        return None

    # Вытаскиваем _function_id из ответа AI-асистента
    def _function_id_by_ai_response(self, ai_response: str):
        if not ai_response:
            return None
        
        lines = ai_response.strip().split('\n')
        if lines:
            # Ищем "id" и число в последней строке
            last_line = lines[-1].strip().lower()
            match = re.search(r'\bid[:\s]*(\d+)', last_line)
            if match:
                return int(match.group(1))
        
        return None

    # Добавляеv интерактивные кнопки для диалога
    def _add_interaction_buttons(self, dialog_id):
        # Фрейм кнопок
        button_frame = ttk.Frame(self.history_text)
        
        # Кнопка Решено
        solved_btn = ttk.Button(
            button_frame, 
            text="✓ Решено", 
            command=lambda: self._mark_solved_and_disable(dialog_id, True, [solved_btn, not_solved_btn])
        )
        solved_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Кнопка Не решено
        not_solved_btn = ttk.Button(
            button_frame, 
            text="✗ Не решено", 
            command=lambda: self._mark_solved_and_disable(dialog_id, False, [solved_btn, not_solved_btn])
        )
        not_solved_btn.pack(side=tk.LEFT)
        
        # Добавление фрейма кнопок в текстовое поле
        buttons_pos = self.history_text.index(tk.END)
        self.history_text.window_create(buttons_pos, window=button_frame, padx=10, pady=5)

    # Установка отметки "решенный"
    def _mark_solved_and_disable(self, dialog_id, solved, buttons):
        # Если удачно установили статус, то вносим изменения в интерфейс
        if self._dialog_history.set_dialog_solved(dialog_id, solved):
            # Информируем в строке статуса
            self.status_var.set(f"Диалог {dialog_id} отмечен как {'решенный' if solved else 'нерешенный'}")
            
            # Деактивируем и скрываем кнопки
            for btn in buttons:
                try:
                    btn.pack_forget()  # Удаляем кнопки из видимости
                except:
                    pass
            
            # Находим родительский фрейм кнопок и добавляем текст статуса
            try:
                button_frame = buttons[0].master  # Получаем родительский фрейм
                
                # Добавляем текст статуса
                status_text = "✓ Решено" if solved else "✗ Не решено"
                status_label = ttk.Label(
                    button_frame, 
                    text=f"Статус: {status_text}",
                    foreground='green' if solved else 'red',
                    font=('TkDefaultFont', 9, 'italic')
                )
                status_label.pack(side=tk.LEFT)

                if solved:
                    # Пишем промпт для "обучения"
                    self._add_ai_response_to_prompt(dialog_id)

            except Exception as e:
                self._logger.error(f"Ошибка добавления статуса: {e}")

        else:
            self.status_var.set("Ошибка обновления статуса")

    # Добавляем ответ AI-асистента в промпт
    def _add_ai_response_to_prompt(self, dialog_id):
        try:
            # Получаем диалог по ID
            dialog = self._dialog_by_id(dialog_id)
            if dialog:
                # Извлекаем function_id из ответа AI
                function_id = self._function_id_by_ai_response(dialog['ai_response'])
                if function_id:
                    # Сохраняем запрос пользователя как промпт
                    prompt_id = save_prompt(
                        prompt_id=None,
                        function_id=function_id,
                        text=dialog['user_query']
                    )
                    self._logger.debug(f"Промпт {prompt_id} сохранен для функции {function_id}")

                else:
                    self._logger.warning(f"Не удалось извлечь function_id из ответа диалога {dialog_id}")
                    
        except Exception as e:
            self._logger.error(f"Ошибка при сохранении промпта: {e}")    

    # Прокуртка в самый низ
    def _scroll_to_bottom(self):
        self.history_text.see(tk.END)
        
        # Обработка событий перерисовки
        self.root.update_idletasks()

    # Очистка поля ввода
    def _clear_input(self):
        self.input_text.delete(1.0, tk.END)
    
    # Обработчик закрытия окна
    def _on_closing(self):
        self.root.withdraw()  # Скрываем окно вместо закрытия
    
    # Отображение окна
    def show_window(self):
        # разворачивам, поднимаем, устанавливаем фокус
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    # Запуск цикла обработки сообщений
    def run(self):
        self.root.mainloop()

# Иконка в системном трее
class SystemTray:
    def __init__(self, main_window):
        self.main_window = main_window
        self._create_tray()

    # Создание иконки в ситемном трее
    def _create_tray(self):
        # Создаем простую картинку
        image = Image.new('RGB', (64, 64), color='white')
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=48)
        draw.text((32, 32), "OS", fill='blue', anchor="mm", font=font)
        font = ImageFont.load_default(size=32)
        draw.text((32, 32), "AI", fill='red', anchor="mm", font=font)
        
        # Создаем иконку с меню
        self.icon = pystray.Icon(
            "os_assistant",
            image,
            "OS Assistant",
            menu=pystray.Menu(
                pystray.MenuItem("Открыть диалог", self._show_window),
                pystray.MenuItem("Редактор функций", self._open_function_editor),
                pystray.MenuItem("Выход", self._exit_app)
            )
        )

    # Уведомление о запуске
    def _show_startup_notification(self):
        if self.icon.HAS_NOTIFICATION:
            self.icon.notify(message='Ваш ассистент Windows находится здесь', title='OS Assistant')

        else:
            print('Ваш ассистент Windows находится в системном трее')

    # Отображение окна диалога
    def _show_window(self, icon=None, item=None):
        self.main_window.show_window()

    def _open_function_editor(self, icon=None, item=None):
        try:
            editor = FunctionEditorWindow()
            editor.show()
            
        except Exception as e:
            logger.error(f'Ошибка запуска редактора функций: {e}')

    # Выход из приложения   
    def _exit_app(self, icon=None, item=None):
        icon.stop()

        self.main_window.root.quit()
        self.main_window.root.destroy()

        sys.exit(0)
    
    # Запуск иконки в трее
    def run(self):
        self.icon.run_detached()
        threading.Timer(3.0, self._show_startup_notification).start()

# Первоначальная инициализация приложения
def first_init_application():
    if config_value(None, 'MAIN', 'first_run', 'True'):
        set_config_value(None, 'MAIN', 'first_run', 'False')

    else:
        return

    logger = main_logger()
    
    app_list = os_app_list()
    launch_app_id = function_type_id('Launch application')
    
    for app_info in tqdm(app_list, desc='Заполнение базы функций операционной системы'):
        try:
            result = json.loads(new_app_description(app_info))
            if result['description']:
                save_function(
                    function_id_by_command(app_info['command']),
                    app_info['name'],
                    launch_app_id,
                    result['description'],
                    app_info['command']
                )

        except Exception as e:
            logger.error(f'Ошибка заполнения базы функций: {e}')

# Главная функция
def main():
    try:
        # Первоначальная инициализация
        first_init_application()

        # Пересчет эмбеддингов
        # TODO Не оптимально
        searcher = RubertTiny2SemanticSearch()
        searcher.rebuild_embeddings()

        # Создаем и скрываем главное окно
        main_window = MainWindow()
        main_window.root.withdraw()
        
        # Иконка в трее - отдельный поток
        tray = SystemTray(main_window)
        tray_thread = threading.Thread(target=tray.run, daemon=True)
        tray_thread.start()
        
        # Главный цикл - основной поток
        main_window.run()
        
    except Exception as e:
        print(f'Ошибка запуска приложения: {e}')

        return 1

    return 0

# Код главного скрипта
if __name__ == '__main__':
    # Запуск приложения
    exit_code = main()
    sys.exit(exit_code)