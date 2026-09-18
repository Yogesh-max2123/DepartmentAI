from backend.llm.gemini_client import generate_answer


question = "What is the minimum SPI/CPI requirement for continuing in the programme?"

context = """
Section 8 — Academic Performance Requirement

The minimum SPI/CPI requirement for continuing in the programme is
equal to 6.5. A student who secures SPI less than 6.5 in the first
semester shall be called ACD.
"""


answer = generate_answer(question, context)

print("\nQUESTION:")
print(question)

print("\nANSWER:")
print(answer)
