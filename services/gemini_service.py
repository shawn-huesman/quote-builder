import json
import logging
from typing import Any, Dict
from google.oauth2 import service_account
from google import genai
from config import LOCATION, PROJECT_ID, QUOTE_SCHEMA

logger = logging.getLogger()

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def generate_quote(vertex_key: Dict[str, Any], prompt_text: str) -> Dict[str, Any]:
    credentials = service_account.Credentials.from_service_account_info(
        vertex_key,
        scopes=SCOPES
    )

    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
        credentials=credentials
    )

    logger.info(f"--- CONTENT TO GEMINI ---: {json.dumps(prompt_text)}")

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=prompt_text,
        config={
            "response_mime_type": "application/json",
            "response_schema": QUOTE_SCHEMA,
            "temperature": 0.0,
            "top_p": 0.1,
            "top_k": 1
        }
    )

    return json.loads(response.text)