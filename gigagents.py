from collections import deque
import json

import os

from gigachat import GigaChat
import gigachat.context
from gigachat.exceptions import AuthenticationError, ResponseError
from gigachat.models import Chat, Messages, MessagesRole

from agents import AIAgentMessage, BaseAIFunctions, BaseAIAgent
from utilities import config_value, main_folder

# Ключевые настройки GigaChat
def _gigachat_key_settings():
    # Личные данные храним в отдельном файле
    config_path = os.path.join(main_folder(), 'gigakeys.ini')

    # Ключ авторизации GigaChat
    authorization_key = config_value(config_path, 'GIGACHAT', 'authorization_key', None)
    if authorization_key is None:
        raise Exception('Ключ авторизации GigaChat не установлен')
    
    # Заголовки соединения с GigaChat: идентификатор сессия, ...
    session_id = config_value(config_path,'GIGACHAT', 'session_id', None)
    if session_id is None:
        raise Exception('Идентификатор сессия GigaChat не установлен')
    headers = {"X-Session-ID": session_id}

    return authorization_key, headers

# Имя модели по умолчанию
def default_model_name() -> str:
    model_name = config_value(None, 'GIGACHAT', 'model', None)
    if model_name is None:
        raise Exception('Не указан модель GigaChat')

    return model_name

# Ответ на запрос
def response_to_prompt(authorization_key: str, headers: dict, model_name: str, message_list: list, function_list: list | None = None):
    # Экземпляр GigaChat
    with GigaChat(
        credentials=authorization_key,
        scope='GIGACHAT_API_PERS',
        verify_ssl_certs=False
    ) as giga:
        gigachat.context.session_id_cvar.set(headers.get("X-Session-ID"))

        # Новое сообщение в чат
        chat = Chat(
            messages=message_list,
            model=model_name,
            functions=function_list
        )

        # Получение ответа от чата
        try:
            response = giga.chat(chat)

        except AuthenticationError as e:
            raise Exception(f'Ошибка авторизации в GigaChat: {e}')

        except ResponseError as e:
            raise Exception(f'Ошибка получения ответа GigaChat: {e}')

        return response

def new_app_description(app_info: dict) -> str:
    system_prompt = Messages(
        role=MessagesRole.SYSTEM,
        content="""Ты — специалист по компьютерным программам.

### Твоя задача:
Создавать описание известных тебе программ.

### Требования:
- Достоверность — создавай описание только извесных тебе программ.
- Краткость — описание должно быть коротким.
- Точность — описание должно быть точным.
- Формат ответа для известных программ: {"description": "Текст описания"}
- Формат ответа для неизвестных программ: {"description": null}
        
### Примеры корректного запроса и ответа:
- Пример 1:
    User: {"name": "Блокнот", "command": "notepad.exe", "description": null}
    Assistant: {"description": "Простой редактор текста"}
- Пример 2:
    User: {"name": "Калькулятор", "command": "calc.exe", "description": null}
    Assistant: {"description": "Для математических вычислений"}
- Пример 3:
    User: {"name": "Хероборатор", "command": "C:\\Heroborator.exe", "description": "Конструктор херобор"}
    Assistant: {"description": null}"""
    )

    user_prompt = Messages(
        role=MessagesRole.USER,
        content=json.dumps(app_info, indent=1, ensure_ascii=False)
    )

    authorization_key, headers = _gigachat_key_settings()
    response = response_to_prompt(authorization_key, headers, default_model_name(), [system_prompt, user_prompt])
    return response.choices[0].message.content.strip()

# История сообщений GigaChat
class GigaChatHistory():
    def __init__(self, system_prompt: str):
        # Ограничение максимального размера контекста
        max_context_length = config_value(None, 'GIGACHAT', 'max_context_length', None)
        if max_context_length is None:
            raise Exception('Максимальная длина контекста GigaChat не установлена')
        self._max_context_length = max_context_length

        # Первое сообщение всегда системный промпт
        message = Messages(
            role=MessagesRole.SYSTEM,
            content=system_prompt
        )
        self._messages = deque([message])

    # Количество сообщений в истории для функции len()
    def __len__(self) -> int:
        return len(self._messages)

    # Размер контекста как сумма длины всех сообщений
    def _context_length(self) -> int:
        return sum(len(message.content) for message in self._messages)

    # Ограничение максимального размера контекста
    def _enforce_context_limit(self):
        # Удаление самого старого сообщение (кроме системного промта)
        while len(self) > 2 and self._context_length() > self._max_context_length:
            del self._messages[1]

        # Контроль: втрое сообщение должно быть от пользователя
        if len(self) > 2 and self._messages[1].role != MessagesRole.USER:
            del self._messages[1]

    # Добавление любого сообщения GigaChat
    def add_message(self, message: Messages):
        # Добавление сообщения
        self._messages.append(message)
        # Контроль размера контекста
        self._enforce_context_limit()

    # Добавление сообщения пользователя
    def add_user_content(self, content: str) -> Messages:
        # Новое сообщения GigaChat
        message = Messages(
            role=MessagesRole.USER,
            content=content
        )
        self.add_message(message)

        return message

    # Добавление системного промта
    def add_assistant_content(self, content: str) -> Messages:
        # Новое сообщения GigaChat
        message = Messages(
            role=MessagesRole.ASSISTANT,
            content=content
        )
        self.add_message(message)

        return message

    # Добавление сообщения функции
    def add_function_content(self, content: str, function: str) -> Messages:
        # Новое сообщения GigaChat
        message = Messages(
            role=MessagesRole.FUNCTION,
            content=content,
            name=function
        )
        self.add_message(message)

        return message

    # Список сообщений
    def messages(self) -> list[Messages]:
        return list(self._messages)

# Базовый класс GigaChat AI-агента
class BaseGigaChatAIAgent(BaseAIAgent):
    def __init__(self, system_prompt: str, model: str, functions: list):
        # Ключевые настройки
        self._authorization_key, self._headers = _gigachat_key_settings()

        # Параметры GigaChat
        self._model = model
        self._system_prompt = system_prompt
        self._functions = functions

        # Очистка контекста
        self.clear_context()

    # Ответ на вопрос
    def _answer(self, content: str, function: str, is_answer: bool = False) -> AIAgentMessage:
        # Добавление резултата функции в чат
        if is_answer:
            self._chat_history.add_function_content(content, function)

        # Добавление сообщения пользователя в чат
        else:
            self._chat_history.add_user_content(content)
        
        # Получение ответа от чата
        response = response_to_prompt(
            self._authorization_key,
            self._headers,
            self._model,
            self._chat_history.messages(),
            self._functions
        )

        # Добавление ответа ассистента в чат
        chat_message = response.choices[0].message
        self._chat_history.add_message(chat_message)

        answer = AIAgentMessage()
        # Помещение ответа в сообщение
        if chat_message.function_call is None:
            answer.content = chat_message.content.strip()

        # Помещение параметров и имени функции в сообщение
        else:
            answer.function = chat_message.function_call.name
            answer.content = chat_message.function_call.arguments

        return answer

    # Возможность дать ответ
    def can_handle(self, question: AIAgentMessage) -> float:
        if question.function == BaseAIFunctions.content:
            return 1.0
        return 0.0

    # Ответ на вопрос
    def answer(self, question: AIAgentMessage) -> AIAgentMessage:
        # Получение ответа на вопрос
        answer = self._answer(question.content, question.function, question.is_answer)
        # По умолчанию обычный контент (не вызов функции) провоцирует завершение работы
        if answer.function == BaseAIFunctions.content:
            answer.done = True
        return answer

    # Очистка контекста
    def clear_context(self):
        # Новая история чата с GigaChat
        self._chat_history = GigaChatHistory(self._system_prompt)
