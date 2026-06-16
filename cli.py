"""Run Amy locally in your terminal — no AWS, no Google Sheets.

Requires only an OpenAI key:

    export OPENAI_API_KEY=sk-...
    python cli.py

Conversation state is held in an in-memory store, so each run starts a fresh
guest. Type 'quit' to exit.
"""

import logging
import uuid

from questionnaire import QuestionnaireManager
from storage import InMemoryStore, COL_COMPLETION_TIME


def main():
    logging.basicConfig(level=logging.WARNING)
    store = InMemoryStore()
    user_id = f"local-{uuid.uuid4().hex[:8]}"

    print("Intermission — you're chatting with Amy. Type 'quit' to exit.\n")

    # Opening greeting is produced with no user input.
    response, _, _ = QuestionnaireManager(user_id, "", store=store).next()
    print(f"Amy: {response}\n")

    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if text.lower() in {"quit", "exit"}:
            break
        if not text:
            continue

        qm = QuestionnaireManager(user_id, text, store=store)
        response, _, _ = qm.next()
        print(f"\nAmy: {response}\n")

        if qm.user.get_current_progress() >= COL_COMPLETION_TIME:
            print("(questionnaire complete)")
            break


if __name__ == "__main__":
    main()
