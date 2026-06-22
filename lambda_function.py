import json
import logging
from typing import Any, Dict

from pipeline import run_quote_pipeline

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    logger.info("Lambda invocation started execution workflow.")

    try:
        body_str = event.get('body', '{}')
        request_body = json.loads(body_str) if isinstance(body_str, str) else body_str
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Malformed JSON request payload parsing failure: {e}")
        return {"statusCode": 400, "body": json.dumps({"message": "Invalid JSON signature"})}

    if 'challenge' in request_body:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"challenge": request_body['challenge']})
        }

    event_body = request_body.get("event")
    if not event_body:
        logger.error("Missing underlying 'event' payload parameter.")
        return {"statusCode": 400, "body": json.dumps({"message": "Missing 'event' payload parameter"})}

    status_code, response_payload = run_quote_pipeline(event_body)

    if status_code == 200 and "challenge" in response_payload:
        response_payload = {'challenge': request_body.get('challenge', '')}

    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_payload)
    }