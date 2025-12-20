import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from funcdb import functions_list, function_types, function_details, delete_function, delete_prompt, save_function, save_prompt, prompt
from utilities import main_logger, main_folder

# Редактор функций
class FunctionEditorWindow:
    _instance = None  # Синглтон

    def __new__(cls):
        # Новыqе экземпляр только один раз = Синглтон
        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(self):
        # Инициализация только один раз - Синглтон
        if not hasattr(self, '_initialized'):
            self._logger = main_logger()
            self._parent_root = None
            self._create_window()
            self._create_ui()
            self._load_functions()

            self._initialized = True # Защита от повторной инициализации

    # Создание окна
    def _create_window(self):
        try:
            self.root = tk.Toplevel() # Дополнительное окно

        except tk.TclError:
            self.root = tk.Tk()  # Основное окно
        
        self.root.title("Редактор функций")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Скрываем окно
        self.root.withdraw()

    # Создание интерфейса
    def _create_ui(self):
        # Фрэйм с отступами
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Настройка пропорций растягивания окна и фрейма
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Кнопки управления (row 0)
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        buttons_frame.columnconfigure(1, weight=1)
        
        ttk.Button(buttons_frame, text="Добавить функцию", command=self._add_function).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        ttk.Button(buttons_frame, text="Удалить функцию", command=self._delete_function).grid(row=0, column=1, sticky=tk.W)
        
        # Таблица функций с правильными скроллбарами (row 1-2)
        table_frame = ttk.Frame(main_frame)
        table_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Колонки таблицы
        columns = ('id', 'name', 'description', 'type', 'command')
        self.functions_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)
        
        self.functions_tree.heading('id', text='Код')
        self.functions_tree.heading('name', text='Наименование')
        self.functions_tree.heading('description', text='Описание')
        self.functions_tree.heading('type', text='Тип функции')
        self.functions_tree.heading('command', text='Команда')
        
        # Ширина колонок (сумма = 900px, адаптивно)
        self.functions_tree.column('id', width=60, minwidth=60)
        self.functions_tree.column('name', width=150, minwidth=100)
        self.functions_tree.column('description', width=250, minwidth=150)
        self.functions_tree.column('type', width=120, minwidth=100)
        self.functions_tree.column('command', width=320, minwidth=200)
        
        self.functions_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Скроллбары в углах
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.functions_tree.yview)
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.functions_tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.functions_tree.xview)
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E), columnspan=2)
        self.functions_tree.configure(xscrollcommand=h_scrollbar.set)
        
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        
        # Строка статуса (row 2)
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Двойной клик
        self.functions_tree.bind('<Double-1>', self._edit_function)
    
    # Загрузка функций
    def _load_functions(self):
        try:
            # Очищаем таблицу
            for item in self.functions_tree.get_children():
                self.functions_tree.delete(item)
            
            # Получаем функции через функцию из funcdb.py
            functions = functions_list()
            
            for func in functions:
                # func содержит: (id, name, description, type_name, command)
                self.functions_tree.insert('', tk.END, values=func)
            
            self.status_var.set(f"Загружено функций: {len(functions)}")
            
        except Exception as e:
            self._logger.error(f"Ошибка загрузки функций: {e}")
            self.status_var.set(f"Ошибка: {e}")

    # Добавление функции
    def _add_function(self):
        # Открываем диалог
        dialog = FunctionCard(self.root, None)
        if dialog.result:
            self._load_functions()
    
    # Изменение функции
    def _edit_function(self, event):
        # Берем выбранную строку
        selection = self.functions_tree.selection()
        if not selection:
            return
        
        # Получаем поле id
        item = self.functions_tree.item(selection[0])
        func_id = item['values'][0]
        
        # Открываем диалог
        dialog = FunctionCard(self.root, func_id)
        if dialog.result:
            self._load_functions()
    
    # Удаление функции
    def _delete_function(self):
        # Берем выбранную строку
        selection = self.functions_tree.selection()
        if not selection:
            return

        # Получаем поле id
        item = self.functions_tree.item(selection[0])
        func_id = item['values'][0]
        
        # Спрашиваем подтверждение
        if tk.messagebox.askyesno("Подтверждение", f"Удалить функцию ID {func_id}?"):
            try:
                # Удаляем функцию
                delete_function(func_id)
                self._load_functions()

                self.status_var.set("Функция удалена")
                
            except Exception as e:
                self._logger.error(f"Ошибка удаления функции: {e}")
                self.status_var.set(f"Ошибка: {e}")

    # Обработчик закрытия
    def _on_closing(self):
        # Просто скрываем
        self.root.withdraw()
    
    # Отображение окна
    def show(self):
        self.root.deiconify()  # Показываем окно
        self.root.lift()       # Поднимаем на передний план
        self.root.focus_force() # Устанавливаем фокус
        
# Карточка редактирования функции
class FunctionCard:
    def __init__(self, parent, function_id=None):
        self.function_id = function_id
        self.result = False
        
        # Создаем диалоговое окно
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Редактирование функции" if function_id else "Новая функция")
        self.dialog.geometry("600x500")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрируем окно
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        self._create_ui()
        
        if function_id:
            self._load_function()
        
        # Блокируем родительское окно
        self.dialog.wait_window()
    
    def _create_ui(self):
        # главный фрейм
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ID функции (только для чтения при редактировании)
        ttk.Label(main_frame, text="ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.id_var = tk.StringVar()
        id_entry = ttk.Entry(main_frame, textvariable=self.id_var, state=tk.DISABLED)
        id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        # Название функции
        ttk.Label(main_frame, text="Название:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(main_frame, textvariable=self.name_var)
        name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        # Тип функции
        ttk.Label(main_frame, text="Тип функции:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar()
        self.type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, state="readonly")
        self.type_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        self._load_function_types()
        
        # Описание
        ttk.Label(main_frame, text="Описание:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.description_text = tk.Text(main_frame, height=3, wrap=tk.WORD)
        self.description_text.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        # Команда
        ttk.Label(main_frame, text="Команда:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.command_var = tk.StringVar()
        command_entry = ttk.Entry(main_frame, textvariable=self.command_var)
        command_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 0))
        
        # Промпты
        prompts_frame = ttk.LabelFrame(main_frame, text="Промпты", padding="5")
        prompts_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        prompts_frame.columnconfigure(0, weight=1)
        prompts_frame.rowconfigure(0, weight=1)
        
        self.prompts_tree = ttk.Treeview(prompts_frame, columns=('id', 'text'), show='headings', height=5)
        self.prompts_tree.heading('id', text='ID')
        self.prompts_tree.heading('text', text='Текст промпта')
        self.prompts_tree.column('id', width=50)
        self.prompts_tree.column('text', width=400)
        self.prompts_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        prompts_scrollbar = ttk.Scrollbar(prompts_frame, orient=tk.VERTICAL, command=self.prompts_tree.yview)
        self.prompts_tree.configure(yscrollcommand=prompts_scrollbar.set)
        prompts_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Кнопки управления промптами
        prompts_buttons = ttk.Frame(prompts_frame)
        prompts_buttons.grid(row=1, column=0, columnspan=2, pady=(5, 0))
        
        ttk.Button(prompts_buttons, text="Добавить", command=self._add_prompt).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(prompts_buttons, text="Редактировать", command=self._edit_prompt).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(prompts_buttons, text="Удалить", command=self._delete_prompt).pack(side=tk.LEFT)
        
        # Кнопки диалога
        dialog_buttons = ttk.Frame(main_frame)
        dialog_buttons.grid(row=6, column=0, columnspan=2, pady=20)
        
        ttk.Button(dialog_buttons, text="Сохранить", command=self._save).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(dialog_buttons, text="Отмена", command=self._cancel).pack(side=tk.LEFT)
        
        # Настройка растягивания
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)

    # Загрузка типов функций
    def _load_function_types(self):
        try:
            # Получаем типы функций
            types = function_types()
            
            # Преобразуем в формат для Combobox
            self.type_combo['values'] = [f"{name} (ID: {id_})" for id_, name in types]
            
            # Создаем словарь для обратного преобразования
            self._function_types = {f"{name} (ID: {id_})": id_ for id_, name in types}
            
        except Exception as e:
            main_logger().error(f"Ошибка загрузки типов функций: {e}")
    
    # Загрузка данных функции
    def _load_function(self):
        try:
            # Получаем детали функции через функцию из funcdb.py
            function_details_data, prompts = function_details(self.function_id)
            
            if function_details_data:
                # Заполняем поля
                self.id_var.set(str(function_details_data[0]))
                self.name_var.set(function_details_data[1] or '')
                self.description_text.insert('1.0', function_details_data[2] or '')
                self.command_var.set(function_details_data[3] or '')
                
                # Значение в выпадающем списке тип функции
                type_name = f"{function_details_data[4]} (ID: {function_details_data[5]})"
                if type_name in self._function_types:
                    self.type_combo.set(type_name)
            
            # Загружаем промпты
            for prompt in prompts:
                self.prompts_tree.insert('', tk.END, values=prompt)
                
        except Exception as e:
            main_logger().error(f"Ошибка загрузки функции: {e}")

    # Добавить промпт
    def _add_prompt(self):
        # Диалог промпта
        dialog = PromptCard(self.dialog, None, self.function_id)
        if dialog.result:
            self._load_prompts()
    
    # Меняем промпт
    def _edit_prompt(self):
        # Выбранная строка
        selection = self.prompts_tree.selection()
        if not selection:
            return
        
        # id из строки
        item = self.prompts_tree.item(selection[0])
        prompt_id = item['values'][0]
        
        # Диалог промпта
        dialog = PromptCard(self.dialog, prompt_id, self.function_id)
        if dialog.result:
            self._load_prompts()
    
    # Удаление промпта
    def _delete_prompt(self):
        # Выбранная строка        
        selection = self.prompts_tree.selection()
        if not selection:
            return
        
        # id из строки
        item = self.prompts_tree.item(selection[0])
        prompt_id = item['values'][0]
        
        # Подтверждаем удаление
        if tk.messagebox.askyesno("Подтверждение", f"Удалить промпт ID {prompt_id}?"):
            try:
                # Удаляем
                delete_prompt(prompt_id)

                self._load_prompts()
                
            except Exception as e:
                main_logger().error(f"Ошибка удаления промпта: {e}")

    # Загрузка промптов
    def _load_prompts(self):
        try:
            if self.function_id is None:
                return

            # Очищаем таблицу
            for item in self.prompts_tree.get_children():
                self.prompts_tree.delete(item)
            
            # Получаем промпты через function_details
            _, prompts = function_details(self.function_id)
            
            # Добавляем в список
            for prompt in prompts:
                self.prompts_tree.insert('', tk.END, values=prompt)
                
        except Exception as e:
            main_logger().error(f"Ошибка загрузки промптов: {e}")

    # Обработчик записи функции
    def _save(self):
        try:
            # Валидация
            if not self.type_combo.get():
                tk.messagebox.showerror("Ошибка", "Выберите тип функции")
                return
            
            if not self.command_var.get().strip():
                tk.messagebox.showerror("Ошибка", "Введите команду")
                return
            
            # Читаем из элементов
            type_id = self._function_types[self.type_combo.get()]
            if hasattr(self, 'name_var') and self.name_var.get().strip():
                name = self.name_var.get().strip()

            else:
                name = self.command_var.get().strip()

            description = self.description_text.get('1.0', tk.END).strip()
            command = self.command_var.get().strip()
            
            if self.function_id:  # Обновление - есть id
                save_function(
                    function_id=self.function_id,
                    name=name,
                    type_id=type_id,
                    description=description,
                    command=command
                )
            else:  # Создание новой - нет id
                self.function_id = save_function(
                    name=name,
                    type_id=type_id,
                    description=description,
                    command=command
                )
            
            self.result = True

            self.dialog.destroy()
            
        except Exception as e:
            main_logger().error(f"Ошибка сохранения функции: {e}")
            tk.messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")

    # Обработчик отмены
    def _cancel(self):
        self.dialog.destroy()

# Карточка редактирования промпта
class PromptCard:
    def __init__(self, parent, prompt_id=None, function_id=None):
        self.prompt_id = prompt_id
        self.function_id = function_id
        self.result = False
        
        # Дополнительное окно диалога
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Редактирование промпта" if prompt_id else "Новый промпт")
        self.dialog.geometry("500x300")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрируем
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 100, parent.winfo_rooty() + 100))
        
        # Создаем интерфейс
        self._create_ui()
        
        # Загружаем промпты
        if prompt_id:
            self._load_prompt()
        
        # Блокирующее окно диалога
        self.dialog.wait_window()
    
    # Создание интерфейса
    def _create_ui(self):
        # Главный фрейм
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Текст промпта
        ttk.Label(main_frame, text="Текст промпта:").pack(anchor=tk.W)
        
        # Растягивающееся во все строны поле промпта
        self.prompt_text = tk.Text(main_frame, height=10, wrap=tk.WORD)
        self.prompt_text.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        # Кнопки в отдельном фрейме
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)
        
        ttk.Button(buttons_frame, text="Сохранить", command=self._save).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(buttons_frame, text="Отмена", command=self._cancel).pack(side=tk.LEFT)
    
    # Загрузка промпта
    def _load_prompt(self):
        try:
            text = prompt(self.prompt_id)
            
            if text:
                self.prompt_text.insert('1.0', text)
            
        except Exception as e:
            main_logger().error(f"Ошибка загрузки промпта: {e}")
    
    # Обработчик созранения
    def _save(self):
        try:
            # Получаем промпт из элемента
            text = self.prompt_text.get('1.0', tk.END).strip()
            if not text:
                tk.messagebox.showerror("Ошибка", "Введите текст промпта")
                return
            
            if self.prompt_id:  # Обновление - есть id
                save_prompt(prompt_id=self.prompt_id, text=text)

            else:  # Создание нового - нет id
                self.prompt_id = save_prompt(function_id=self.function_id, text=text)
            
            self.result = True

            self.dialog.destroy()
            
        except Exception as e:
            main_logger().error(f"Ошибка сохранения промпта: {e}")
            tk.messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")
    
    # Обработчик отмены
    def _cancel(self):
        self.dialog.destroy()