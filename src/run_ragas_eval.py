from pathlib import Path
from controller.RagasEvalController import RagasEvalController


def main():
    ragas_controller = RagasEvalController()

    results_path = Path(__file__).parent / "assets" / "eval" / "rag_results.json"
    dataset = ragas_controller.load_rag_results(results_path)

    result = ragas_controller.run_evaluation(dataset)

    df = result.to_pandas()
    output_path = Path(__file__).parent / "assets" / "eval" / "ragas_report.csv"
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(result)
    print(f"\nSaved detailed report to {output_path}")


if __name__ == "__main__":
    main()
