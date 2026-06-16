"""The LLM boundary: send a prompt to GPT-4 and parse its JSON reply."""

import json
import logging
import os
import re

from openai import OpenAI

from prompt_builder import PromptBuilder
from errors import ResponseError

logger = logging.getLogger(__name__)

# Defaults to OpenAI + GPT-4 (as in production), but both the endpoint and the
# model are overridable via env, so the agent can run against any
# OpenAI-compatible API — including free ones (Groq, a local Ollama server) —
# for local testing without funding an OpenAI account.
client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL") or None,
)
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4")


class Receptionist:
    @staticmethod
    def prompt(prompt: str) -> dict:
        """
        Send a prompt to GPT and parse its response into a dict.

        :param prompt: GPT prompt, including instructions to output JSON.
        :return: the parsed JSON object.
        :raises ResponseError: if the reply is not valid JSON.
        """
        assert prompt is not None
        logger.debug("Sending prompt:\n%s", prompt)

        instructions = PromptBuilder.get_instructions()
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        )

        response = completion.choices[0].message.content
        return Receptionist._parse_reply(response)

    @staticmethod
    def _parse_reply(reply: str, attempt: int = 1) -> dict:
        """Extract and parse the JSON object from a model reply.

        Models occasionally return *almost*-valid JSON (e.g. raw newlines
        inside string values). On the first failure we run a repair pass and
        retry once before giving up.
        """
        match = re.search(r"({[\S\s]+?}$)", reply)
        if not match:
            logger.error("No JSON found in reply: %s", reply)
            raise ResponseError(f"Reply Error: no JSON found in the response string. {reply}")

        json_str = match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            if attempt == 1:
                repaired = Receptionist.escape_newlines_in_json_strings(reply)
                return Receptionist._parse_reply(repaired, attempt + 1)
            logger.error("Extracted string is not valid JSON (%s): %s", e, reply)
            raise ResponseError(f"Reply Error: Extracted string is not valid JSON {reply}")

    @staticmethod
    def escape_newlines_in_json_strings(json_str: str) -> str:
        """Escape raw newlines that appear inside JSON string values."""
        pattern = r'(?:"(?:\\.|[^"\\])*")'

        def replace_newlines(match):
            return match.group(0).replace("\n", "\\n")

        return re.sub(pattern, replace_newlines, json_str)
