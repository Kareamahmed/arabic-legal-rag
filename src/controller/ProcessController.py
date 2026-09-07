import json
from langchain_core.documents import Document


class ProcessController:

    def get_file_content(self, file_path: str):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data

    def get_chunks(self, file_content: list[dict]):

        documents = [
            Document(
                page_content=f"المادة {article.get('article_number')} : {article.get('text_ar', '').strip()}",
                metadata={
                    k: v for k, v in article.items() if k not in ("text_ar", "text_en")
                },
            )
            for article in file_content
        ]
        return documents
