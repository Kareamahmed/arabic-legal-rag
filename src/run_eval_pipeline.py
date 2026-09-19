import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from helper.config import get_settings
from stores.LLM.LLMProviderFactory import LLMProviderFactory
from stores.LLM.templates.template_parser import TemplateParser
from stores.rerank.RerankerProviderFactory import RerankerProviderFactory
from stores.vectordb.VectorDBFactory import VectorDBFactory
from controller.NLPController import NLPController


async def main():
    settings = get_settings()

    postgres_conn = (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DB}"
    )
    postgres_engine = create_async_engine(postgres_conn)
    db_client = sessionmaker(
        postgres_engine, class_=AsyncSession, expire_on_commit=False
    )

    vector_db_factory = VectorDBFactory(db_client=db_client, settings=settings)
    vector_db_client = vector_db_factory.create_provider(
        name=settings.VECTOR_DB_BACKEND
    )
    await vector_db_client.connect()

    llm_provider_factory = LLMProviderFactory(settings=settings)

    generation_client = llm_provider_factory.create_provider(
        name=settings.GENERATION_BACKEND
    )
    generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    embedding_client = llm_provider_factory.create_provider(
        name=settings.EMBEDDING_BACKEND
    )
    embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_SIZE
    )

    template_parser = TemplateParser(
        language=settings.PRIMARY_LANG, default_language=settings.DEFAULT_LANG
    )

    reranker_factory = RerankerProviderFactory(settings=settings)
    reranker_client = reranker_factory.create_provider(name=settings.RERANKER_BACKEND)

    nlp_controller = NLPController(
        vector_db_client=vector_db_client,
        generation_client=generation_client,
        embedding_client=embedding_client,
        template_parser=template_parser,
        reranker_client=reranker_client,
    )

    # --- load eval questions ---
    eval_path = Path(__file__).parent / "assets" / "eval" / "eval_dataset.json"
    with open(eval_path, "r", encoding="utf-8") as f:
        eval_dataset = json.load(f)

    results = []
    for item in eval_dataset:
        question = item["question"]

        pipeline_result = await nlp_controller.answer_rag_question(query=question)
        await asyncio.sleep(7)

        if not pipeline_result:
            print(f"[SKIP] No answer for: {question}")
            continue

        answer, full_prompt, contexts = pipeline_result

        results.append(
            {
                "question": question,
                "answer": answer,
                "contexts": contexts,
                "ground_truth": item["ground_truth"],
                "article_number": item.get("article_number"),
            }
        )
        print(f"[OK] {question[:60]}...")

    output_path = Path(__file__).parent / "assets" / "eval" / "rag_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(results)} pipeline results to {output_path}")

    await postgres_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
