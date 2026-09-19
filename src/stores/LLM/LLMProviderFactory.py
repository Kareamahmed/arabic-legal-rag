from .providers import GeminiProvider, CohereProvider
from helper.config import Settings
from .LLMEnums import LLMEnums


class LLMProviderFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create_provider(self, name: str):
        if name == LLMEnums.GEMINI.value:
            return GeminiProvider(
                api_key=self.settings.GEMINI_API_KEY,
                max_input_tokens=self.settings.MAX_INPUT_TOKENS,
                max_output_tokens=self.settings.MAX_OUTPUT_TOKENS,
                temperature=self.settings.TEMPERATURE,
            )
        if name == LLMEnums.COHERE.value:
            return CohereProvider(
                api_key=self.settings.COHERE_API_KEY,
                max_input_tokens=self.settings.MAX_INPUT_TOKENS,
                max_output_tokens=self.settings.MAX_OUTPUT_TOKENS,
                temperature=self.settings.TEMPERATURE,
            )

        return None
