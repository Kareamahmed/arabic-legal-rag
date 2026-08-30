from enum import Enum


class LLMEnums(Enum):
    GEMINI = "gemini"
    COHERE = "cohere"


class GeminiEnums(Enum):
    USER = "user_input"
    MODEL = "model"
