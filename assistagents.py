from enum import Enum
import json

import os
import subprocess

from gigachat.models import Function
from gigachat.models.function_parameters import FunctionParameters

from agents import AIAgentMessage, BaseAIFunctions, BaseAIAgent
from funcdb import function_details
from gigagents import BaseGigaChatAIAgent, default_model_name
from semsearch import RubertTiny2SemanticSearch
from utilities import main_folder, config_value, main_logger

# Перечисление дополнительных типов функций
class AIFunctions(Enum):
    search_app = 'search_app' # функция поиска программы
    launch_app = 'launch_app' # функция запуска программы
 
# Описание функций для API GigaChat
GIGACHAT_FUNCTIONS: dict = {
    AIFunctions.launch_app: Function(
        name=AIFunctions.launch_app.value,
        description='Запускает программу по идентификатору',
        parameters=FunctionParameters(
            properties={
                'app_id': {
                    'type': 'string',
                    'description': 'Идентификатор программы'
                }
            },
            required=['app_id']
        ),
        return_parameters={
            'type': 'object',
            'properties': {
                'result': {
                    'type': 'string',
                    'description': 'Результат запуска программы'
                }
            }
        }
    )
}

# Агент-асситент
class AssistantAgent(BaseGigaChatAIAgent):
    # Описание функций для API GigaChat
    _gigachat_functions = GIGACHAT_FUNCTIONS

    def __init__(self):
        # Получение логгера
        self._logger = main_logger()

        # Получение имени модели LLM
        model = default_model_name()

        # Системный prompt
        system_prompt = '''Ты специалист по поиску компьютерных программ.

### Задача
Найди программу для решения задачи пользователя.

### Требования
- В предложенном списке найди одну программу подходящую для решения задачи.
- Если программа не найдена, сообщи об этом.
- Если программа найдена, вызови функцию запуска программ по идентификатору.'''

        # Получение описания функций для API GigaChat
        function_launch_app = self._gigachat_functions[AIFunctions.launch_app]

        # Инициализация как у базового класса
        super().__init__(system_prompt, model, [function_launch_app])

    # Возможность дать ответ
    def can_handle(self, question: AIAgentMessage) -> float:
        # Если это ответ на запрос функции - можем обработать
        if question.is_answer:
            if question.reply_to == self.__class__.__name__:
                return 1.0

        # Если это запрос на поиск программы - можем обработать
        elif question.function == AIFunctions.search_app:
            return 1.0
        return -1.0

    # Ответ на вопрос
    def answer(self, question: AIAgentMessage) -> AIAgentMessage:
        # Проверка возможности дать ответ
        if self.can_handle(question) == -1:
            raise Exception("Невозможно обработать запрос")

        # Логгирование на уровне отладки
        self._logger.debug(f"Объект: {self.__class__.__name__}\n Запрос: {question}")

        # Если это запрос от пользователя - отвечаем
        if question.function == AIFunctions.search_app:
            app_list = [
                {
                    k: v for k, v in d.items() if k in ['id', 'name', 'description']
                } for d in question.content['app_list']
            ]

            content = f'''### Список программ:
{json.dumps(app_list, indent=1, ensure_ascii=False)}

### Задача пользователя:
{question.content['prompt']}'''

            answer = self._answer(content, BaseAIFunctions.content.value)

        # Если это ответ от функции 'запуск приложения'
        elif question.function == AIFunctions.launch_app:
            # Просим исправить ошибку несколько раз
            if self._trial_count < 3:
                answer = self._answer(question.content, question.function.value, question.is_answer)

            # Не получилось - честно признаемся и завершаем работу
            else:
                answer = AIAgentMessage()
                answer.content = 'Не удалось найти приложение'
                answer.done = True

        else:
            raise Exception("Невозможно обработать запрос")

        # Получаем функцию AI-агента по имени функции GigaChat
        if answer.function != BaseAIFunctions.content:
            answer.function = AIFunctions[answer.function]

        # Если не завершаем работу
        if not answer.done:
            # Если это запрос функции 'запуск приложения' - помещаем идентификатор в контент
            if answer.function == AIFunctions.launch_app:
                answer.content = answer.content['app_id']
                self._trial_count += 1

            elif answer.function == BaseAIFunctions.content:
                answer = AIAgentMessage()
                answer.content = 'Не удалось найти приложение'
                answer.done = True

            else:
                raise Exception(f'Неизвестная функция: {answer.function}')

        # Мы либо отвечаем пользователю, либо вызываем функцию - фиксируем обратный адрес
        answer.reply_to = self.__class__.__name__

        # Логгирование на уровне отладки
        self._logger.debug(f"Объект: {self.__class__.__name__}\n Ответ: {answer}")

        return answer

    # Очистка контекста
    def clear_context(self):
        super().clear_context()
        self._trial_count = 0

# Агент по составлению списка программ
class AppListAgent(BaseAIAgent):
    def __init__(self):
        # Получение логгер
        self._logger = main_logger()

        # Создаем объект для семантического поиска
        self._searcher = RubertTiny2SemanticSearch()

    # Возможность дать ответ
    def can_handle(self, question: AIAgentMessage) -> float:
        # Если это контент - отвечаем
        if question.function == BaseAIFunctions.content and not question.is_answer:
            return 1.0
        return -1.0

    # Ответ на вопрос
    def answer(self, question: AIAgentMessage) -> AIAgentMessage:
        # Проверка возможности дать ответ
        if self.can_handle(question) == -1:
            raise Exception("Невозможно обработать запрос")
        
        # Логгирование на уровне отладки
        self._logger.debug(f"Объект: {self.__class__.__name__}\n Запрос: {question}")

        # Получение списка программ и формирования сообщения
        answer_data = {
            'app_list': self._searcher.functions(question.content),
            'prompt': question.content
        }

        answer = AIAgentMessage()
        answer.function = AIFunctions.search_app
        answer.content = answer_data

        # Логгирование на уровне отладки
        self._logger.debug(f"Объект: {self.__class__.__name__}\n Ответ: {answer}")

        return answer

    # Очистка контекста
    def clear_context(self):
        pass

# Агент по запуску программ
class LaunchAppAgent(BaseAIAgent):
    def __init__(self):
        self._logger = main_logger()
        self.clear_context()

    # Возможность дать ответ
    def can_handle(self, question: AIAgentMessage) -> float:
        # Если это запрос нашей функции - отвечаем
        if question.function == AIFunctions.launch_app and not question.is_answer:
            return 1.0
        return -1.0

    # Ответ на вопрос
    def answer(self, question: AIAgentMessage) -> AIAgentMessage:
        # Проверка возможности дать ответ
        if self.can_handle(question) == -1:
            raise Exception("Невозможно обработать запрос")

        # Логгирование на уровне отладки
        self._logger.debug(f"Объект: {self.__class__.__name__}\n Запрос: {question}")

        # Получение информации о приложении
        row = function_details(int(question.content))
        if row:
            columns = ['id', 'name', 'description', 'command']
            app_info = dict(zip(columns, row[0]))

            # Запускаем приложение
            try:
                subprocess.Popen([app_info['command']], shell=True)

                answer = AIAgentMessage()
                answer.content = f'Запускаю приложение {app_info['name']}\nid: {app_info['id']}'
                answer.done = True

            except Exception as e:
                answer = AIAgentMessage()
                answer.content = f'Ошибка запуска приложения {app_info['name']}: {e}\nid: {app_info['id']}'
                answer.done = True

        else:
            # Прочим вернуть верный идентификатор
            answer = AIAgentMessage()
            answer.function = question.function
            answer.content = json.dumps({'result': 'Ошибка: неверный идентификатор. Попробуй ещё раз'}, indent=1, ensure_ascii=False)
            answer.is_answer = True
            answer.reply_to = question.reply_to

        # Логгирование на уровне отладки
        self._logger.debug(f"Объект: {self.__class__.__name__}\n Ответ: {answer}")

        return answer

    # Очистка контекста
    def clear_context(self):
        pass