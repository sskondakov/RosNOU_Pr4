import os

from abc import ABC, abstractmethod
import numpy as np

from sentence_transformers import SentenceTransformer

from funcdb import functions_list, rebuild_embeddings, top_3_similar
from utilities import main_folder, config_value

# Абстактный класс семантического поиска
class BaseSemanticSearch:
    @abstractmethod
    def embeddings(self, sentences: list[str]) -> list[list[float]]:
        pass
    
    @abstractmethod
    def rebuild_embeddings(self):
        pass

    @abstractmethod
    def functions(self, prompt: str) -> list[dict[str, str]]:
        pass

# Cемантического поиск c Rubert-Tiny2
class RubertTiny2SemanticSearch(BaseSemanticSearch):
    def __init__(self):
        # Загрузка модели из папки или с сайта huggingface
        folder_name = config_value(None, 'RUBERT_TINY2', 'folder_name', 'rubert-tiny2')
        model_path = os.path.join(main_folder(), folder_name)
        if not os.path.exists(model_path):
            model_path ='cointegrated/rubert-tiny2'

        self._model = SentenceTransformer(model_path)

        # Обновление эмбеддингов
        # TODO Не оптимально
        self.rebuild_embeddings()

    # Вычисление эмбеддингов
    def embeddings(self, sentences: list[str]) -> list[list[float]]:
        if not sentences:
            return []

        # Нормализованные эмбеддинги
        embeddings = self._model.encode(sentences, normalize_embeddings=True, batch_size=32, show_progress_bar=False)

        return embeddings.tolist()

    # Пересчет эмбеддингов
    def rebuild_embeddings(self):
        rebuild_embeddings(self.embeddings)

    # Поиск функций по тексту промпта
    def functions(self, prompt: str) -> list[dict[str, int | str]]:
        # Эмбеддинг запроса -> ближайшие эмбеддинги с близостью -> id -> функции
        embedding = self.embeddings([prompt])[0]
        weights = top_3_similar(embedding)
        ids = [f[0] for f in weights]
        rows = functions_list(ids)

        columns = ['id', 'name', 'description', 'type', 'command']
        return [dict(zip(columns, row)) for row in rows]
