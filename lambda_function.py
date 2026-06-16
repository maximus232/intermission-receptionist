"""AWS Lambda entry point behind API Gateway."""

import logging

from openai import RateLimitError

from questionnaire import QuestionnaireManager
from errors import ResponseError

logger = logging.getLogger(__name__)

ALLOWED_DOMAINS = [
    "https://intermission.rsvp",
    "https://www.intermission.rsvp",
    "http://localhost:5500",
]


def json_response(status: str, message, status_code: int, headers):
    return {
        "statusCode": status_code,
        "status": status,
        "message": message,
        "headers": headers,
    }


def lambda_handler(event, context):
    headers = {
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    if event.get("httpMethod"):
        origin = event["headers"].get("origin", "")
        headers["Access-Control-Allow-Origin"] = (
            origin if origin in ALLOWED_DOMAINS else "https://intermission.rsvp"
        )

        # Pre-flight: return only the headers.
        if event["httpMethod"] == "OPTIONS":
            return {"statusCode": 200, "headers": headers}

    if "message" not in event or "user_id" not in event:
        return json_response("Bad request", None, 501, headers)

    try:
        questionnaire = QuestionnaireManager(event["user_id"], event["message"])
        amys_response, prompt, q_idx = questionnaire.next()
        return {
            "statusCode": 200,
            "message": amys_response,
            "headers": headers,
            "q_idx": q_idx,
        }
    except ValueError as e:
        if str(e) == "User not found":
            return json_response("not_found", "", 401, headers)
        raise
    except RateLimitError as e:
        return json_response("rate_limit_error", e.message, 503, headers)
    except ResponseError as e:
        return json_response("response_error", str(e), 500, headers)


if __name__ == "__main__":
    # Local smoke test against the real handler.
    logging.basicConfig(level=logging.DEBUG)
    print(lambda_handler({"message": "Max Tester", "user_id": "test_631"}, None))
