import os

from abc import ABC, abstractmethod
import numpy as np

from sentence_transformers import SentenceTransformer

from funcdb import functions_list, rebuild_embeddings, top_N_similar
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

# Cемантический поиск c Rubert-Tiny2
_MODEL_RUBERT_TINY2 = None

class RubertTiny2SemanticSearch(BaseSemanticSearch):
    # Экземпляр модели
    @property
    def _model(self):
        global _MODEL_RUBERT_TINY2

        if _MODEL_RUBERT_TINY2 is None:
            folder_name = config_value(None, 'RUBERT_TINY2', 'folder_name', 'rubert-tiny2')
            model_path = os.path.join(main_folder(), folder_name)
            if not os.path.exists(model_path):
                model_path ='cointegrated/rubert-tiny2'

            # Загрузка модели
            _MODEL_RUBERT_TINY2 = SentenceTransformer(model_path)

        return _MODEL_RUBERT_TINY2

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
        weights = top_N_similar(embedding, 10)
        ids = [f[0] for f in weights]
        rows = functions_list(ids)

        columns = ['id', 'name', 'description', 'type', 'command']
        return [dict(zip(columns, row)) for row in rows]
