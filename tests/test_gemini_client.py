from backend.llm.gemini_client import generate_answer


question = "What are the requirements for academic performance?"

context = """
Section 7 — Academic Performance Requirement

A student is required to maintain the prescribed academic performance
during the programme. Students whose academic performance becomes deficient
are subject to the conditions specified in the ordinance.
"""


answer = generate_answer(question, context)

print("\nQUESTION:")
print(question)

print("\nANSWER:")
print(answer)