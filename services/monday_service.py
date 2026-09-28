import logging
import requests

logger = logging.getLogger(__name__)


def get_workspace_id_from_board(board_id: str, monday_api_key: str) -> str:
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": monday_api_key,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }

    query = """
        query ($ids: [ID!]) {
          boards(ids: $ids) {
            workspace {
              id
            }
          }
        }
    """

    try:
        response = requests.post(
            url,
            json={'query': query, 'variables': {'ids': [board_id]}},
            headers=headers
        )
        response.raise_for_status()
        res_json = response.json()

        if "errors" in res_json:
            logger.error(f"Monday API returned GraphQL errors: {res_json['errors']}")
            return ""

        boards = res_json.get('data', {}).get('boards', [])
        if not boards:
            logger.warning(f"No board matches found on Monday.com for ID: {board_id}")
            return ""

        workspace = boards[0].get('workspace')
        return workspace.get('id', '') if workspace else "main"

    except requests.RequestException as e:
        logger.error(f"HTTP request error connecting to Monday API: {e}")
        return ""


def get_pipeline_workspaces(monday_api_key: str) -> dict:
    logger.info("Querying Monday.com for boards named 'pipeline'...")
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": monday_api_key,
        "Content-Type": "application/json",
        "API-Version": "2023-10"
    }

    query = """
            query {
              boards(limit: 150000) {
                id
                name
                workspace {
                  id
                  name
                }
              }
            }
        """

    try:
        response = requests.post(url, json={'query': query}, headers=headers)
        response.raise_for_status()
        res_json = response.json()

        if "errors" in res_json:
            logger.error(f"Monday API returned GraphQL errors: {res_json['errors']}")
            return {}

        boards = res_json.get('data', {}).get('boards', [])
        if not boards:
            logger.warning("No boards found on Monday.com.")
            return {}

        pipeline_workspaces = {}
        for board in boards:
            board_id = board.get('id', '')
            board_name = board.get('name', '')
            if "pipeline" in board_name.lower():
                workspace = board.get('workspace')
                ws_id = workspace.get('id', 'main') if workspace else "main"
                ws_name = workspace.get('name') if workspace else "Main Workspace"

                if ws_id not in pipeline_workspaces:
                    pipeline_workspaces[ws_id] = {
                        "name": ws_name,
                        "board_ids": []
                    }

                pipeline_workspaces[ws_id]["board_ids"].append(board_id)

        return pipeline_workspaces

    except requests.RequestException as e:
        logger.error(f"HTTP request error connecting to Monday API: {e}")
        return {}


def format_market_name(workspace_name: str) -> str:
    return "".join(char for char in workspace_name.lower() if char.isalpha())


def get_workspace_id(monday_board_id: str, monday_api_key: str) -> str:
    url = "https://api.monday.com/v2"
    headers = {"Authorization": monday_api_key}
    query = f"query {{ boards (ids: {monday_board_id}) {{ workspace_id }} }}"
    response = requests.post(url, json={'query': query}, headers=headers)
    data = response.json()
    return data['data']['boards'][0]['workspace_id']


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
        market = format_market_name(workspace_name)

        logger.info(f"Successfully resolved market name: '{market}' from workspace: '{workspace_name}'")
        return market

    except requests.RequestException as e:
        logger.error(f"HTTP request error connection to Monday API: {e}")
        return "default_market"
