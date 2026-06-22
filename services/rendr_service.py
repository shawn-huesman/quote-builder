import base64
import logging
import unicodedata
import requests
import json
from typing import Optional, Dict, Any, List
from config import TOKEN_URL, API_BASE_URL, HOME_STRETCH_URL

logger = logging.getLogger(__name__)


def get_access_token(client_id: str, secret: str) -> Optional[str]:
    logger.info("Requesting access token from Rendr auth server.")
    auth_b64 = base64.b64encode(f"{client_id}:{secret}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        res = requests.post(TOKEN_URL, headers=headers, data={"grant_type": "client_credentials"})
        res.raise_for_status()
        token = res.json().get("access_token")
        if token:
            logger.info("Rendr access token successfully rotated.")
        return token
    except requests.RequestException as e:
        logger.error(f"Failed to generate Rendr access token: {e}")
        return None


def _normalize_key(s: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", s).lower() if char.isalnum())


def _extract_rooms_for_space(data: Any) -> List[Dict[str, Any]]:
    """
    Recursively scans deep down into a specific Space's sub-tree
    to harvest its underlying nested Rooms.
    """
    rooms = []
    SQUARE_METERS_TO_SQUARE_FEET = 10.76398

    if isinstance(data, dict):
        # Identify a Room leaf node
        if "label" in data and ("area" in data or "perimeter" in data or "roomTakeoff" in data):
            label = data.get("label") or ""
            normalized_label = _normalize_key(label)

            if label and normalized_label != "allrooms":
                takeoff = data.get("roomTakeoff") or {}

                paintable_sqft, ceiling_area, perimeter, wall_area, doors, windows = [
                    data.get(k) or takeoff.get(k)
                    for k in ["totalPaintableSurfaceAreaInSqMeters", "ceilingAreaInSqMeters", "perimeterInMeters",
                              "wallsAreaInSqMeters", "numberOfDoors", "numberOfWindows"]
                ]

                rooms.append({
                    "label": label,
                    "paintable_sqft": float(paintable_sqft or 0) * SQUARE_METERS_TO_SQUARE_FEET,
                    "ceiling_area": float(ceiling_area or 0) * SQUARE_METERS_TO_SQUARE_FEET,
                    "perimeter": float(perimeter or 0) * SQUARE_METERS_TO_SQUARE_FEET,
                    "wall_area": float(wall_area or 0) * SQUARE_METERS_TO_SQUARE_FEET,
                    "doors": int(doors or 0),
                    "windows": int(windows or 0),
                    # "notes": data.get("notes") or ""
                })
            return rooms

        for value in data.values():
            rooms.extend(_extract_rooms_for_space(value))

    elif isinstance(data, list):
        for item in data:
            rooms.extend(_extract_rooms_for_space(item))

    return rooms


def summarize_spaces_with_rooms(data: Any) -> List[Dict[str, Any]]:
    logger.info("--- PROCESSING NESTED SPACES AND ROOMS STRUCT ---")
    results = []
    stack = [data]

    while stack:
        current = stack.pop()

        if isinstance(current, dict):
            if "title" in current and ("squareFootage" in current or "wallSurfaceArea" in current):

                nested_rooms = _extract_rooms_for_space(current)

                results.append({
                    "space_name": current.get("title"),
                    "paintable_sqft": current.get("paintableSurfaceArea", 0),
                    "ceiling_area": current.get("ceilingSurfaceArea", 0),
                    "perimeter": current.get("perimeterInFeet", 0),
                    "wall_area": current.get("wallSurfaceArea", 0),
                    "doors": current.get("numberOfDoors", 0),
                    "windows": current.get("numberOfWindows", 0),
                    "notes": current.get("notes") or "",
                    "rooms": nested_rooms
                })
            else:
                stack.extend(current.values())

        elif isinstance(current, list):
            stack.extend(current)

    seen = set()
    unique_results = []
    for r in results:
        uid = (r['space_name'], r['paintable_sqft'])
        if uid not in seen:
            unique_results.append(r)
            seen.add(uid)

    logger.info(f"--- FINAL HIERARCHICAL SUMMARY ---: {json.dumps(unique_results)}")
    return unique_results


def find_spaces(access_token: str, space_name: str, page_size: int) -> Optional[Dict[str, Any]]:
    logger.info(f"Scanning Rendr projects to locate space matching target: '{space_name}'")
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    try:
        res = requests.get(f"{API_BASE_URL}/projects/", headers=headers, params={"page_size": page_size})
        res.raise_for_status()

        target_name = _normalize_key(space_name or "")
        for project in res.json().get("items", []):
            current_project_name = project.get("name") or ""
            if _normalize_key(current_project_name) == target_name:
                logger.info(f"Match found! Rendr Project: '{current_project_name}' matches Target: '{space_name}'")

                space_details = []
                space_ids = []

                for space in project.get("spaces", []):
                    s_id = space.get("id")
                    space_ids.append(s_id)
                    s_res = requests.get(f"{API_BASE_URL}/spaces/json/{s_id}", headers=headers)
                    if s_res.ok:
                        space_details.append(s_res.json().get("spaces"))
                    else:
                        logger.warning(f"Could not load JSON schema metrics for space ID: {s_id}")

                return {
                    "project_id": project.get("id"),
                    "space_ids": space_ids,
                    "spaces": space_details,
                    "owner_email": project.get("owner_email"),
                    "project_notes": project.get("description")
                }
    except requests.RequestException as e:
        logger.error(f"Network error discovered while syncing Rendr project details: {e}")

    logger.warning(f"No active Rendr project matches target parameter name '{space_name}' after full scan.")
    return None


def send_submission(payload: Dict[str, Any], cookie: str):
    logger.info(f"Posting invoice submission to Home Stretch endpoint: {HOME_STRETCH_URL}")
    headers = {"Cookie": cookie}
    try:
        res = requests.post(HOME_STRETCH_URL, headers=headers, json=payload)
        res.raise_for_status()
        logger.info(f"Home Stretch invocation success. HTTP Status: {res.status_code}")
    except requests.RequestException as e:
        logger.error(f"Failed to post structured payload to Home Stretch pipeline: {e}")