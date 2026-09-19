from pathlib import Path
from controller.RagasEvalController import RagasEvalController


def main():
    ragas_controller = RagasEvalController()

    results_path = Path(__file__).parent / "assets" / "eval" / "rag_results.json"
    dataset = ragas_controller.load_rag_results(results_path)

    result = ragas_controller.run_evaluation_in_batches(dataset)

    output_path = Path(__file__).parent / "assets" / "eval" / "ragas_report.csv"
    result.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(result)
    print(f"\nSaved detailed report to {output_path}")


if __name__ == "__main__":
    main()

# from pathlib import Path
# import pandas as pd

# output_path = Path(__file__).parent / "assets" / "eval" / "ragas_report.csv"

# df =  pd.read_csv(output_path, encoding="utf-8-sig")
# avg_faithfulness = (df["faithfulness"].sum() / len(df)).round(4)
# print(f"Average Faithfulness: {avg_faithfulness}")