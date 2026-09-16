from backend.llm.gemini_client import generate_answer


def resolve_follow_up(question, conversation_history):
    """
    Convert a follow-up question into a standalone question
    using only the recent relevant conversation.
    """

    if not conversation_history:
        return question

    # Only consider the most recent 6 messages.
    recent_history = conversation_history[-6:]

    history_parts = []

    for message in recent_history:
        role = message.get("role", "")
        content = message.get("content", "")

        if role in ["user", "assistant"] and content:
            history_parts.append(
                f"{role.upper()}: {content}"
            )

    if not history_parts:
        return question

    history_text = "\n".join(history_parts)

    prompt = f"""
You are a conversation-context resolver for an academic ordinance chatbot.

Your ONLY task is to rewrite the current user question into a
standalone question when it depends on the recent conversation.

Recent conversation:
{history_text}

Current question:
{question}

Rules:

1. If the current question is already standalone, return it unchanged.

2. If the current question is a follow-up, identify the MOST RECENT
   relevant topic from the conversation and make the question standalone.

3. Do NOT combine multiple academic programmes or topics.

4. If the recent conversation is about the M.Tech. degree requirements and
   the user asks "What about the CPI requirement?", the output MUST refer
   specifically to the M.Tech. degree requirements.

5. Do NOT switch from one programme to another merely because they share
   words such as CPI, credits, eligibility, registration, or thesis.

6. Use ONLY information contained in the recent conversation to resolve
   the reference.

7. Do NOT answer the question.

8. Return ONLY the final standalone question.
Do not provide explanations, numbering, or additional text.

Example:

Recent conversation:
USER: What are the requirements for the M.Tech. degree?
ASSISTANT: A student must earn at least 80 credits, defend the final thesis and attain the minimum required SPI/CPI.

Current question:
What about the CPI requirement?

Correct output:
What is the CPI requirement for the M.Tech. degree?
"""

    resolved_question = generate_answer(
        question,
        prompt
    ).strip()

    # Safety fallback if the resolver returns nothing.
    if not resolved_question:
        return question

    return resolved_question
