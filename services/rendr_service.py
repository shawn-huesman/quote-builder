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
    rooms = []
    SQUARE_METERS_TO_SQUARE_FEET = 10.76398
    METERS_TO_FEET = 3.28084

    if isinstance(data, dict):
        if "rooms" in data and isinstance(data["rooms"], list) and data["rooms"]:
            for room in data["rooms"]:
                rooms.extend(_extract_rooms_for_space(room))
            return rooms

        if "label" in data:
            label = data.get("label") or ""
            normalized_label = _normalize_key(label)

            if label and normalized_label != "allrooms":
                takeoff = data.get("roomTakeoff") or {}

                paintable_sqft = (
                    data.get("totalPaintableSurfaceAreaInSqMeters")
                    if data.get("totalPaintableSurfaceAreaInSqMeters") is not None
                    else takeoff.get("totalPaintableSurfaceAreaInSqMeters", 0)
                )
                ceiling_area = (
                    data.get("ceilingAreaInSqMeters")
                    if data.get("ceilingAreaInSqMeters") is not None
                    else takeoff.get("ceilingAreaInSqMeters", 0)
                )
                perimeter = (
                    data.get("perimeterInMeters")
                    if data.get("perimeterInMeters") is not None
                    else takeoff.get("perimeterInMeters", 0)
                )
                wall_area = (
                    data.get("wallsAreaInSqMeters")
                    if data.get("wallsAreaInSqMeters") is not None
                    else takeoff.get("wallsAreaInSqMeters", 0)
                )
                doors = (
                    data.get("numberOfDoors")
                    if data.get("numberOfDoors") is not None
                    else takeoff.get("numberOfDoors", 0)
                )
                windows = (
                    data.get("numberOfWindows")
                    if data.get("numberOfWindows") is not None
                    else takeoff.get("numberOfWindows", 0)
                )

                rooms.append({
                    "label": label,
                    "paintable_sqft": float(paintable_sqft or 0) * SQUARE_METERS_TO_SQUARE_FEET,
                    "ceiling_area": float(ceiling_area or 0) * SQUARE_METERS_TO_SQUARE_FEET,
                    "perimeter": float(perimeter or 0) * METERS_TO_FEET,
                    "wall_area": float(wall_area or 0) * SQUARE_METERS_TO_SQUARE_FEET,
                    "doors": int(doors or 0),
                    "windows": int(windows or 0),
                    "notes": data.get("notes") or takeoff.get("notes") or ""
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
    SQUARE_METERS_TO_SQUARE_FEET = 10.76398
    METERS_TO_FEET = 3.28084

    while stack:
        current = stack.pop()

        if isinstance(current, dict):
            if ("title" in current or "label" in current) and (
                    "squareFootage" in current or "wallSurfaceArea" in current or "totalPaintableSurfaceAreaInSqMeters" in current or "spaceTakeoff" in current):

                nested_rooms = _extract_rooms_for_space(current)
                takeoff = current.get("spaceTakeoff") or {}

                paintable_sqft = (
                        current.get("totalPaintableSurfaceAreaInSqMeters") or
                        takeoff.get("totalPaintableSurfaceAreaInSqMeters") or
                        0
                )

                ceiling_area = (
                        current.get("ceilingAreaInSqMeters") or
                        takeoff.get("ceilingAreaInSqMeters") or
                        0
                )

                perimeter = (
                        current.get("perimeterInMeters") or
                        takeoff.get("perimeterInMeters") or
                        0
                )

                wall_area = (
                        current.get("wallsAreaInSqMeters") or
                        takeoff.get("wallsAreaInSqMeters") or
                        0
                )

                doors = current.get("numberOfDoors") or takeoff.get("numberOfDoors") or 0
                windows = current.get("numberOfWindows") or takeoff.get("numberOfWindows") or 0

                results.append({
                    "space_name": current.get("title") or current.get("label"),
                    "paintable_sqft": float(paintable_sqft) * SQUARE_METERS_TO_SQUARE_FEET,
                    "ceiling_area": float(ceiling_area) * SQUARE_METERS_TO_SQUARE_FEET,
                    "perimeter": float(perimeter) * METERS_TO_FEET,
                    "wall_area": float(wall_area) * SQUARE_METERS_TO_SQUARE_FEET,
                    "doors": int(doors),
                    "windows": int(windows),
                    "notes": current.get("notes") or takeoff.get("notes") or "",
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

    unique_results.append({
        "space_name": "Home",
        "paintable_sqft": sum(d.get("paintable_sqft", 0) for d in unique_results),
        "ceiling_area": sum(d.get("ceiling_area", 0) for d in unique_results),
        "perimeter": sum(d.get("perimeter", 0) for d in unique_results),
        "wall_area": sum(d.get("wall_area", 0) for d in unique_results),
        "doors": sum(d.get("doors", 0) for d in unique_results),
        "windows": sum(d.get("windows", 0) for d in unique_results),
        "notes": "",
        "rooms": []
    })

    logger.info(f"--- FINAL HIERARCHICAL SUMMARY ---: {json.dumps(unique_results)}")
    return unique_results


def _process_space_data(data: dict, space: dict, space_details: list):
    if not data.get("notes") or not str(data["notes"]).strip():
        data["notes"] = space.get("notes")

    space_details.append(data)


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
                    space_json_res = requests.get(f"{API_BASE_URL}/spaces/json/{s_id}", headers=headers)

                    space_res = requests.get(f"{API_BASE_URL}/spaces/{s_id}", headers=headers)
                    space_uuid = space_res.json().get("uuid")
                    flex = requests.get(f"{API_BASE_URL}/spaces/flex/file-versions/{space_uuid}/latest", headers=headers)
                    flex_uuid = flex.json().get("uuid")
                    flex_takeoff_res = requests.get(f"{API_BASE_URL}/spaces/flex/export/takeoff/{flex_uuid}", headers=headers)

                    if flex_takeoff_res.ok:
                        flex_takeoff = flex_takeoff_res.json()
                        _process_space_data(flex_takeoff, space, space_details)
                    elif space_json_res.ok:
                        space_json = space_json_res.json().get("spaces")[0]
                        _process_space_data(space_json, space, space_details)
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