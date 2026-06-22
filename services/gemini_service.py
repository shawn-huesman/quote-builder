import json
import logging
from typing import Any, Dict
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel
from config import LOCATION, PROJECT_ID, QUOTE_SCHEMA

logger = logging.getLogger()


def generate_quote(vertex_key: Dict[str, Any], prompt_text: str) -> Dict[str, Any]:
    credentials = service_account.Credentials.from_service_account_info(vertex_key)
    vertexai.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)

    logger.info(f"--- CONTENT TO GEMINI ---: {json.dumps(prompt_text)}")

    model = GenerativeModel("gemini-2.5-pro")
    response = model.generate_content(
        prompt_text,
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": QUOTE_SCHEMA,
            "temperature": 0.0,
            "top_p": 0.1,
            "top_k": 1
        }
    )

    return json.loads(response.candidates[0].content.parts[0].text)