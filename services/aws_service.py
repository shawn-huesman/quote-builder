import json
import logging
import boto3
from botocore.exceptions import ClientError
from config import AWS_DEFAULT_REGION

logger = logging.getLogger(__name__)


def get_secret(secret_id: str, region_id: str = AWS_DEFAULT_REGION):
    logger.info(f"Fetching secret: '{secret_id}' from region: '{region_id}'")
    client = boto3.client("secretsmanager", region_name=region_id)
    try:
        response = client.get_secret_value(SecretId=secret_id)
        secret_data = response['SecretString']

        try:
            return json.loads(secret_data)
        except json.JSONDecodeError:
            return secret_data

    except ClientError as e:
        logger.error(f"AWS SecretsManager ClientError for secret '{secret_id}': {e}")
        return {}