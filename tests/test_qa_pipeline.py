from backend.rag.qa_pipeline import answer_question


questions = [
    "What are the requirements for academic performance?",
    "What are the requirements for earning a B.Tech degree?",
    "What are the requirements for a B.Tech Honours degree?",
    "What happens if a student's academic performance becomes deficient?",
    "What degrees can be awarded under the undergraduate programme?",
]


for question in questions:

    answer, results = answer_question(question)

    print("\n" + "=" * 70)
    print("QUESTION")
    print("=" * 70)
    print(question)

    print("\n" + "=" * 70)
    print("ANSWER")
    print("=" * 70)
    print(answer)

    print("\n" + "=" * 70)
    print("RETRIEVED SOURCES")
    print("=" * 70)

    for i, result in enumerate(results, start=1):
        print(
            f"[{i}] "
            f"Section {result['section_number']} - "
            f"{result['section_title']} | "
            f"Clause: {result['clause_number']} | "
            f"Pages: {result['page_start']}-{result['page_end']} | "
            f"Score: {result['combined_score']:.4f}"
        )