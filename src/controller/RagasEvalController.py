import json
from pathlib import Path
import time
import pandas as pd
from datasets import Dataset

from langchain_groq import ChatGroq
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from ragas import evaluate
from ragas.metrics import faithfulness
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig

from .BaseController import BaseController


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
            request_timeout=180,
            max_retries=5,
            max_tokens=2048,
            temperature=0.0,
        )

        return LangchainLLMWrapper(chat_model)

    def _build_judge_embeddings(self):
        settings = self.app_setting

        embed_model = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL_ID,
            google_api_key=settings.GEMINI_API_KEY,
            output_dimensionality=settings.EMBEDDING_SIZE,
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
        custom_run_config = RunConfig(
            max_workers=1,
            timeout=180,
            max_retries=10,
            max_wait=120,
        )

        result = evaluate(
            dataset=dataset,
            metrics=[faithfulness],
            llm=self.judge_llm,
            embeddings=self.judge_embeddings,
            run_config=custom_run_config,
        )

        return result

    def run_evaluation_in_batches(
        self, full_dataset: Dataset, batch_size: int = 5
    ) -> pd.DataFrame:
        all_results = []
        total_len = len(full_dataset)

        for i in range(0, total_len, batch_size):
            batch_num = (i // batch_size) + 1
            total_batches = (total_len + batch_size - 1) // batch_size
            print(f"Evaluating batch {batch_num} / {total_batches}...")

            batch = full_dataset.select(range(i, min(i + batch_size, total_len)))
            res = self.run_evaluation(batch)
            all_results.append(res.to_pandas())

            if i + batch_size < total_len:
                print("Cooling down for 60 seconds to reset Groq OTPM limit...")
                time.sleep(60)

        final_df = pd.concat(all_results, ignore_index=True)
        return final_df
