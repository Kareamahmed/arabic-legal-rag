import json
import random
from .BaseController import BaseController


class EvalDatasetController(BaseController):
    def __init__(self, generation_client):
        super().__init__()
        self.generation_client = generation_client

    def load_corpus(self):
        with open(self.data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def sample_articles(self, corpus: list[dict], n: int, seed: int = 42):
        rng = random.Random(seed)
        if n >= len(corpus):
            return corpus
        return rng.sample(corpus, n)

    def build_ground_truth(self, article: dict) -> str:
        # mirrors ProcessController.get_chunks formatting so ground_truth
        # matches what's actually indexed/retrievable in the vector DB
        return f"المادة {article.get('article_number')} : {article.get('text_ar', '').strip()}"

    async def generate_question(self, article: dict) -> str | None:
        article_text = self.build_ground_truth(article)

        system_prompt = (
            "أنت خبير قانوني تقوم بصياغة سؤال واحد واضح باللغة العربية "
            "يمكن الإجابة عليه حصراً بالاعتماد على نص المادة القانونية المقدمة. "
            "لا تكتب أي مقدمات أو شروحات، اكتب السؤال فقط."
        )
        prompt = (
            f"نص المادة القانونية:\n{article_text}\n\n"
            "صغ سؤالاً واحداً قصيراً يمكن الإجابة عليه من هذه المادة فقط."
        )

        question = await self.generation_client.generate_text(
            prompt=prompt, system_prompt=system_prompt, temperature=0.3
        )
        if not question:
            return None
        return question.strip()

    async def build_eval_dataset(self, n: int = 20, seed: int = 42):
        corpus = self.load_corpus()
        sampled = self.sample_articles(corpus, n=n, seed=seed)

        dataset = []
        for article in sampled:
            question = await self.generate_question(article)
            if not question:
                continue
            dataset.append(
                {
                    "question": question,
                    "ground_truth": self.build_ground_truth(article),
                    "article_number": article.get("article_number"),
                }
            )
        return dataset