from enum import Enum


class LLMEnums(Enum):
    GEMINI = "gemini"
    COHERE = "cohere"


class GeminiEnums(Enum):
    USER = "user_input"
    MODEL = "model"


class CoHereEnums(Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"

    DOCUMENT = "search_document"
    QUERY = "search_query"


class DocumentTypeEnums(Enum):
    DOCUMENT = "search_document"
    QUERY = "search_query"
