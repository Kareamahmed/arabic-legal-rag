from .providers import CohereProvider
from helper.config import Settings
from .RerankerEnums import RerankerEnums


class RerankerProviderFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_provider(self, name: str):
        if name == RerankerEnums.COHERE.value:
            return CohereProvider(
                api_key=self.settings.COHERE_API_KEY,
                model_name=self.settings.RERANKER_MODEL_NAME,
            )
        return None
