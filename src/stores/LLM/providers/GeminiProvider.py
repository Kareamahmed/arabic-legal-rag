from ..LLMInterface import LLMInterface
from ..LLMEnums import GeminiEnums
from google import genai
from google.genai import types
import logging


class GeminiProvider(LLMInterface):

    def __init__(
        self,
        api_key: str,
        max_input_tokens: int = 1000,
        max_output_tokens: int = 1000,
        temperature: float = 0.2,
    ):
        self.api_key = api_key
        self.default_max_input_tokens = max_input_tokens
        self.default_max_output_tokens = max_output_tokens
        self.default_temperature = temperature

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None

        self.client = genai.Client(api_key=self.api_key)
        self.logger = logging.getLogger("uvicorn")

    def set_generation_model(self, model_id):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id, embedding_size):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def generate_text(
        self,
        prompt: str,
        system_prompt: str = None,
        chat_history: list = None,
        max_output_tokens: int = None,
        temperature: float = None,
    ):
        if not chat_history:
            chat_history = []

        if not self.generation_model_id:
            self.logger.error("Generation model ID is not set.")
            return None

        max_output_tokens = max_output_tokens or self.default_max_output_tokens
        temperature = temperature or self.default_temperature

        chat_history.append(self.construct_prompt(prompt, role=GeminiEnums.USER.value))

        interaction = self.client.interactions.create(
            model=self.generation_model_id,
            system_instruction=system_prompt,
            generation_config=types.GenerationConfig(
                max_output_tokens=max_output_tokens,
                temperature=temperature,
            ),
        )

        if not interaction or not interaction.output_text:
            self.logger.error("Error while generating text with Gemini")
            return None

        for step in interaction.steps:
            chat_history.append(step.model_dump())

        return interaction.output_text

    def embedding_text(self, text, document_type=None):
        if not self.embedding_model_id or not self.embedding_size:
            self.logger.error("Embedding model ID or size is not set.")
            return None

        if isinstance(text, str):
            text = [text]

        result = self.client.models.embed_content(
            model=self.embedding_model_id,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=self.embedding_size),
        )
        if not result or not result.embeddings:
            self.logger.error("Error while generating embeddings with Gemini")
            return None

        embeddings = [embedding.vector for embedding in result.embeddings]
        return embeddings

    def construct_prompt(self, prompt, role):
        return {"role": role, "content": [{"type": "text", "text": prompt}]}
