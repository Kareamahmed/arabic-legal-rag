from ..LLMInterface import LLMInterface
from ..LLMEnums import CoHereEnums, DocumentTypeEnums
import cohere
import logging


class CohereProvider(LLMInterface):

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

        self.client = cohere.Client(api_key=self.api_key)
        self.logger = logging.getLogger("uvicorn")

    def set_generation_model(self, model_id):
        self.generation_model_id = model_id

    def set_embedding_model(self, model_id, embedding_size):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    def generate_text(
        self,
        prompt,
        system_prompt=None,
        chat_history=None,
        max_output_tokens=None,
        temperature=None,
    ):
        if not chat_history:
            chat_history = []

        if not self.generation_model_id:
            self.logger.error("Generation model ID is not set.")
            return None

        max_output_tokens = max_output_tokens or self.default_max_output_tokens
        temperature = temperature or self.default_temperature

        chat_history.append(self.construct_prompt(prompt, role=CoHereEnums.USER.value))

        response = self.client.chat(
            model=self.generation_model_id,
            messages=chat_history,
            max_tokens=max_output_tokens,
            temperature=temperature,
        )
        if (
            not response
            or not response.message
            or not response.message.content
            or len(response.message.content) == 0
        ):
            self.logger.error("Error while generating text with CoHere")
            return None

        generated_text = response.message.content[0].text

        return generated_text

    def embedding_text(self, text, document_type=None):
        if not self.embedding_model_id or not self.embedding_size:
            self.logger.error("Embedding model ID or size is not set.")
            return None

        input_type = CoHereEnums.DOCUMENT.value
        if document_type == DocumentTypeEnums.QUERY.value:
            input_type = CoHereEnums.QUERY.value

        if isinstance(text, str):
            text = [text]

        response = self.client.embed(
            model=self.embedding_model_id,
            texts=text,
            input_type=input_type,
            output_dimension=self.embedding_size,
        )

        if not response or not response.embeddings or not response.embeddings.float:
            self.logger.error("Error while embedding text with CoHere")
            return None

        return [f for f in response.embeddings.float]

    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": prompt,
        }
