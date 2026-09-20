import asyncio
import json
from pathlib import Path

from helper.config import get_settings
from stores.LLM.LLMProviderFactory import LLMProviderFactory
from controller.EvalDatasetController import EvalDatasetController


async def main():
    settings = get_settings()

    llm_provider_factory = LLMProviderFactory(settings=settings)
    generation_client = llm_provider_factory.create_provider(
        name=settings.GENERATION_BACKEND
    )
    generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    eval_controller = EvalDatasetController(generation_client=generation_client)
    dataset = await eval_controller.build_eval_dataset(n=20)

    output_path = Path(__file__).parent / "assets" / "eval" / "eval_dataset.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(dataset)} Q&A pairs to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())