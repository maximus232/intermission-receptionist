import logging
import os

logger = logging.getLogger(__name__)

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


class PromptBuilder:
    @staticmethod
    def build_prompt(current_goal: str, next_goal: str, conversation: str, history: str):
        parts = [
            f"Current Goal: {current_goal}",
            f"{conversation}",
            f"Upcoming Goal: {next_goal}",
        ]
        if history:
            parts.append(f"Key user info:\n{history}")

        prompt = "\n".join(parts)
        logger.debug("Built prompt:\n%s", prompt)
        return prompt

    @staticmethod
    def get_instructions():
        with open(os.path.join(PROMPTS_DIR, "prompt_v2.txt"), "r") as prompt_file:
            return prompt_file.read()
