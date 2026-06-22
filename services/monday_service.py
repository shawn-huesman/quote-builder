import logging
import requests

logger = logging.getLogger(__name__)


def get_market(monday_board_id: str, monday_api_key: str) -> str:
    logger.info(f"Querying Monday.com workspace for board ID: {monday_board_id}")
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": monday_api_key,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }

    query = """
        query ($ids: [ID!]) {
          boards(ids: $ids) {
            workspace { name }
          }
        }
    """

    try:
        response = requests.post(url, json={'query': query, 'variables': {'ids': [monday_board_id]}}, headers=headers)
        response.raise_for_status()
        res_json = response.json()

        if "errors" in res_json:
            logger.error(f"Monday API returned GraphQL errors: {res_json['errors']}")
            return "default_market"

        boards = res_json.get('data', {}).get('boards', [])
        if not boards:
            logger.warning(f"No board matches found on Monday.com for ID: {monday_board_id}")
            return "default_market"

        workspace = boards[0].get('workspace')
        workspace_name = workspace.get('name') if workspace else "Main Workspace"
        market = "".join(char for char in workspace_name.lower() if char.isalpha())

        logger.info(f"Successfully resolved market name: '{market}' from workspace: '{workspace_name}'")
        return market

    except requests.RequestException as e:
        logger.error(f"HTTP request error connection to Monday API: {e}")
        return "default_market"
