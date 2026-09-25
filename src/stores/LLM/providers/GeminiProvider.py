from ..LLMInterface import LLMInterface
from ..LLMEnums import GeminiEnums
from google import genai
from google.genai import types
import logging
from collections.abc import AsyncGenerator
from google.genai.errors import ServerError


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

    async def generate_text_stream(
        self,
        prompt: str,
        system_prompt: str = None,
        chat_history: list = None,
        max_output_tokens: int = None,
        temperature: float = None,
    ) -> AsyncGenerator[str, None]:
        
        if not self.generation_model_id:
            self.logger.error("Generation model ID is not set.")
            return

        max_output_tokens = max_output_tokens or self.default_max_output_tokens
        temperature = temperature or self.default_temperature

        if chat_history:
            contents = list(chat_history)
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
            )
        else:
            contents = prompt

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            top_p=0.95,
        )

        response_stream = await self.client.aio.models.generate_content_stream(
            model=self.generation_model_id, contents=contents, config=config
        )

        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str = None,
        chat_history: list = None,
        max_output_tokens: int = None,
        temperature: float = None,
    ) -> str | None:

        chunks = []
        async for chunk in self.generate_text_stream(
            prompt=prompt,
            system_prompt=system_prompt,
            chat_history=chat_history,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        ):
            chunks.append(chunk)

        if not chunks:
            return None

        return "".join(chunks)

    async def embedding_text(self, text, document_type=None):
        if not self.embedding_model_id or not self.embedding_size:
            self.logger.error("Embedding model ID or size is not set.")
            return None

        if isinstance(text, str):
            text = [text]

        result = await self.client.aio.models.embed_content(
            model=self.embedding_model_id,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=self.embedding_size),
        )
        if not result or not result.embeddings:
            self.logger.error("Error while generating embeddings with Gemini")
            return None

        embeddings = [embedding.values for embedding in result.embeddings]
        return embeddings

    def construct_prompt(self, prompt, role):
        return {"type": role, "content": [{"type": "text", "text": prompt}]}
