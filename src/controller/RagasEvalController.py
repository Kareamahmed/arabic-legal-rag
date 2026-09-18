import json
from pathlib import Path
from datasets import Dataset
from langchain_groq import ChatGroq
from ragas import evaluate

from ragas.metrics import (
    faithfulness,
    context_precision,
    context_recall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from .BaseController import BaseController
from ragas.run_config import RunConfig
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings


class RagasEvalController(BaseController):

    def __init__(self):

        super().__init__()

        self.judge_llm = self._build_judge_llm()

        self.judge_embeddings = self._build_judge_embeddings()

    def _build_judge_llm(self):

        settings = self.app_setting

        chat_model = ChatGroq(
            model=settings.RAGAS_JUDGE_MODEL_ID,
            groq_api_key=settings.GROQ_API_KEY,
            timeout=120,
            max_retries=5,
            max_tokens=4000,
            temperature=0.0,
        )

        return LangchainLLMWrapper(chat_model)

    def _build_judge_embeddings(self):

        settings = self.app_setting

        embed_model = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL_ID,
            google_api_key=settings.GEMINI_API_KEY,
            output_dimensionality=1024,
        )

        return LangchainEmbeddingsWrapper(embed_model)

    def load_rag_results(self, path: Path) -> Dataset:

        with open(path, "r", encoding="utf-8") as f:

            data = json.load(f)

        return Dataset.from_dict(
            {
                "question": [d["question"] for d in data],
                "answer": [d["answer"] for d in data],
                "contexts": [d["contexts"] for d in data],
                "ground_truth": [d["ground_truth"] for d in data],
            }
        )

    def run_evaluation(self, dataset: Dataset):

        result = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                context_precision,
                context_recall,
            ],
            llm=self.judge_llm,
            embeddings=self.judge_embeddings,
            run_config=RunConfig(
                max_workers=1,
                timeout=180,
                max_retries=5,
                max_wait=60,
            ),
        )

        return result
