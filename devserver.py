"""Local dev server: serves the frontend and bridges it to the agent.

Runs the full immersive experience end-to-end on your machine — no AWS, no
Google Sheets. Conversation state lives in an in-memory store.

    pip install flask openai
    export OPENAI_API_KEY=...      # OpenAI, or a free Groq/Ollama endpoint (see .env.example)
    python devserver.py
    # then open http://localhost:5000/?u=guest

The '?u=' query param is the guest id — each booked guest originally had a
unique link. Without it the page stays in "curious visitor" mode (chat
disabled), mirroring the production behaviour.
"""

import logging
import os

from flask import Flask, request, jsonify, send_from_directory
from openai import RateLimitError

from questionnaire import QuestionnaireManager
from storage import InMemoryStore
from errors import ResponseError

logging.basicConfig(level=logging.WARNING)

app = Flask(__name__)
FRONTEND = os.path.join(os.path.dirname(__file__), "frontend")
store = InMemoryStore()  # shared across requests, keyed internally by user_id


@app.route("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.route("/api", methods=["POST"])
def api():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    message = data.get("message", "")
    if not user_id:
        return jsonify({"statusCode": 501, "status": "Bad request", "message": None})

    try:
        amys_response, _, q_idx = QuestionnaireManager(
            user_id, message, store=store
        ).next()
        return jsonify({"statusCode": 200, "message": amys_response, "q_idx": q_idx})
    except RateLimitError:
        return jsonify({"status": "rate_limit_error", "message": "Busy — try again shortly."})
    except ResponseError:
        return jsonify({"status": "response_error", "message": "Lost connection with Amy."})


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND, path)


if __name__ == "__main__":
    app.run(port=5000, debug=True)
