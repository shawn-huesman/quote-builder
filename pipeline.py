import json
import dataclasses
import logging
import os
from typing import Any, Dict

from models import QuoteJob, Space, Room, Task
from config import (DEFAULT_SENDER_EMAIL, EXCEL_FOLDER_ID, EXCEL_DELEGATE_EMAIL,
                    PRICING_CONFIG, MATERIAL_PRICING_CONFIG, PAYOUT_PRICING_CONFIG, PROMPT, HOMESTRETCH_COOKIE)
from services import aws_service, monday_service, rendr_service, gemini_service, excel_email_service
from services.pricing_service import PricingEngine, MaterialPricingEngine, PayoutPricingEngine
from services.excel_service import QuoteExcelBuilder

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def run_quote_pipeline(event_data: Dict[str, Any]):
    job = build_job(event_data)
    board_id = job.monday_board_id
    logger.info(f"Starting pipeline -> Address: '{job.address}'")

    config = _fetch_config(board_id)
    monday_api_key = config["monday_api_key"]
    excel_key = config["excel_key"]
    rendr_token = config["rendr_token"]
    vertex_key = config["vertex_key"]
    prompt_text_base = config["prompt_text_base"]
    if not rendr_token:
        return 500, {"message": "Rendr Access Token collection failed"}

    if not populate_spaces(job, rendr_token):
        return 200, {"message": "No matching Rendr project found", "pulseId": job.monday_item_id}

    try:
        populate_tasks(job, vertex_key, prompt_text_base)
    except Exception as e:
        logger.critical(f"VertexAI processing failure: {e}")
        return 502, {"message": "VertexAI Parsing Error"}

    apply_pricing(job, PRICING_CONFIG, PricingEngine, "price")
    apply_pricing(job, MATERIAL_PRICING_CONFIG, MaterialPricingEngine, "material_price")
    apply_pricing(job, PAYOUT_PRICING_CONFIG, PayoutPricingEngine, "payout_price")
    apply_service_language(job)

    pipeline_workspaces = monday_service.get_pipeline_workspaces(monday_api_key)
    excel_email_service.sync_workspace_folders(excel_key, EXCEL_DELEGATE_EMAIL, EXCEL_FOLDER_ID, pipeline_workspaces)

    workspace_id = monday_service.get_workspace_id_from_board(board_id, monday_api_key)
    folder_id = excel_email_service.get_folder_id_by_workspace_id(excel_key, EXCEL_DELEGATE_EMAIL, EXCEL_FOLDER_ID, workspace_id)

    spreadsheet_title = job.address
    builder = QuoteExcelBuilder()
    excel_buffer = builder.build_to_buffer(job)
    excel_email_service.upload_excel_buffer_to_google_drive(excel_buffer, excel_key, EXCEL_DELEGATE_EMAIL,
                                                            folder_id, spreadsheet_title)

    excel_email_service.share_folder_via_email(
        excel_key=excel_key,
        delegate_user=EXCEL_DELEGATE_EMAIL,
        folder_id=folder_id,
        email_address="shawn.huesman@home-stretch.com",
        role="writer",
        custom_message="You recently created a HOMEstretch quote. Here is access to your excel workspace subfolder."
    )

    payload = build_payload(job)
    logger.info(f"--- PAYLOAD TO HOMESTRETCH ---: {json.dumps(payload, indent=2)}")

    rendr_service.send_submission(payload, HOMESTRETCH_COOKIE)
    return 200, {"challenge": ""}


def apply_pricing(job: QuoteJob, config, pricing_engine, target_attr):
    engine = pricing_engine(config)
    for space in job.spaces:
        for task in space.tasks:
            setattr(task, target_attr, engine.price_task(task.task_type, task.details, space))
        for room in space.rooms:
            for task in room.tasks:
                setattr(task, target_attr, engine.price_task(task.task_type, task.details, room))

    logger.info(f"===Pricing Applied ({pricing_engine})===:")
    _prettyprint(job)


def apply_service_language(job: QuoteJob):
    addon_mappings = {
        "kilz_required": "priming the subfloors",
        "demo_required": "demolition and removal of existing flooring",
        "ceramic_demo_required": "demolition and removal of existing flooring",
        "furniture_move": "moving the furniture",
    }

    def process_task(task: Task):
        details = task.details or {}
        task_display = None
        if task.task_type == "Flooring_Installation":
            task_display = details.get("material")
        elif task.task_type == "Carpet_Installation":
            carpet_tier = str.capitalize(details.get("carpet_tier").replace("tier", " tier"))
            task_display = carpet_tier + " carpet "

        addons = []
        for key, text in addon_mappings.items():
            if details.get(key) and text not in addons:
                addons.append(text)

        if addons and task_display:
            if len(addons) > 2:
                addons_text = f"{', '.join(addons[:-1])}, and {addons[-1]}"
            else:
                addons_text = " and ".join(addons)

            task.service_description += f"\n\nThe {task_display} installation price includes {addons_text}."

    for space in job.spaces:
        for task in space.tasks:
            process_task(task)
        for room in space.rooms:
            for task in room.tasks:
                process_task(task)

    logger.info("===Service Language Applied===")
    _prettyprint(job)


def build_job(event_data: Dict[str, Any]) -> QuoteJob:
    return QuoteJob(
        address=event_data.get("pulseName", ""),
        monday_item_id=event_data.get("pulseId"),
        monday_board_id=event_data.get("boardId"),
    )


def _format_task(task):
    return {
        "service": f"{task.task_type.replace('_', ' ')}: {task.service_description}",
        "task_key": task.task_type,
        "price": task.price,
        "material_price": task.material_price,
        "payout_price": task.payout_price,
    }


def get_task_sort_key(task: dict) -> tuple[int, str]:
    priority_order = {
        "Home_Clear_Outs": 1,
        "Interior_Painting": 2,
        "Flooring_Installation": 3,
        "Light_Handyman_Work": 4,
        "Landscape_Clean_Up": 5,
        "Pressure_Washing": 6,
        "Move_Out_Cleaning": 7,
        "Carpet_Cleaning": 8,
        "Window_Washing": 9,
    }

    task_name = task.get("task_key", "")
    return priority_order.get(task_name, 999), task_name


def build_payload(job: QuoteJob) -> dict:
    rooms_out = []

    for space in job.spaces:
        for room in space.rooms:
            room_tasks = [_format_task(t) for t in room.tasks if t.price > 0]
            if room_tasks:
                room_tasks.sort(key=get_task_sort_key)
                rooms_out.append(_room_entry(room.label, room, room_tasks))

        space_tasks = [_format_task(t) for t in space.tasks if t.price > 0]
        if space_tasks:
            space_tasks.sort(key=get_task_sort_key)
            rooms_out.append(_room_entry(space.name, space, space_tasks))

    return {
        "rooms": rooms_out,
        "sender_email": job.owner_email or DEFAULT_SENDER_EMAIL,
        "monday_item_id": job.monday_item_id,
        "monday_board_id": job.monday_board_id,
        "project_id": job.project_id,
        "space_ids": job.space_ids,
    }


def _room_entry(name: str, container, tasks: list) -> dict:
    return {
        "room_name": name,
        "tasks": tasks,
        "total_wall_area_in_sqft": container.wall_area,
        "total_ceiling_area_in_sqft": container.ceiling_area,
        "total_baseboard_perimeter_in_sqft": container.perimeter,
        "total_door_casing_perimeter_in_sqft": container.doors,
        "total_window_casing_perimeter_in_sqft": container.windows,
    }


def populate_spaces(job: QuoteJob, token: str) -> bool:
    raw = rendr_service.find_spaces(token, job.address, page_size=100)
    if not raw:
        return False

    job.project_id = raw.get("project_id")
    job.space_ids = raw.get("space_ids", [])
    job.owner_email = raw.get("owner_email")
    job.project_notes = raw.get("project_notes")

    for raw_space in rendr_service.summarize_spaces_with_rooms(raw.get("spaces", [])):
        space = Space(
            name=raw_space["space_name"],
            notes=raw_space.get("notes", ""),
            paintable_sqft=raw_space.get("paintable_sqft", 0.0),
            wall_area=raw_space.get("wall_area", 0.0),
            ceiling_area=raw_space.get("ceiling_area", 0.0),
            perimeter=raw_space.get("perimeter", 0.0),
            doors=raw_space.get("doors", 0),
            windows=raw_space.get("windows", 0),
            rooms=[
                Room(
                    label=r["label"],
                    wall_area=r.get("wall_area", 0.0),
                    ceiling_area=r.get("ceiling_area", 0.0),
                    perimeter=r.get("perimeter", 0.0),
                    paintable_sqft=r.get("paintable_sqft", 0.0),
                    doors=r.get("doors", 0),
                    windows=r.get("windows", 0),
                )
                for r in raw_space.get("rooms", [])
            ]
        )
        job.spaces.append(space)

    logger.info(f"===Populated Spaces===:")
    _prettyprint(job)

    return True


def populate_tasks(job: QuoteJob, vertex_key: str, prompt_base: str):
    space_lookup = {_normalize(space.name): space for space in job.spaces}
    room_lookup = {_normalize(room.label): (room, space) for space in job.spaces for room in space.rooms}

    prompt = _build_prompt(prompt_base, job)
    ai_response = gemini_service.generate_quote(vertex_key, prompt)

    for raw_task in ai_response.get("tasks", []):
        name = raw_task.get("room_name", "")
        normalized = _normalize(name)
        task_type = raw_task.get("task_type", "")
        details_key = f"{task_type}_Details"
        details = raw_task.get(details_key, {})

        task = Task(
            task_type=task_type,
            details=details,
            service_description=details.get("service_description", ""),
        )

        room_match = room_lookup.get(normalized)
        if room_match:
            room, parent_space = room_match
            target = parent_space if _should_promote(room.label) else room
            _append_task(target, task)
            continue

        space = space_lookup.get(normalized)
        if space:
            _append_task(space, task)
            continue

        logger.warning(f"No room or space match for '{name}' — skipping")

    logger.info(f"===Populated Tasks===:")
    _prettyprint(job)


def _append_task(target, task):
    if any(t.task_type == task.task_type for t in target.tasks):
        logger.warning(f"Duplicate task_type '{task.task_type}' in '{getattr(target, 'label', getattr(target, 'name', ''))}' — skipping")
        return
    target.tasks.append(task)


def _should_promote(label: str) -> bool:
    normalized = _normalize(label)
    return normalized == "other" or normalized.startswith("room")


def _normalize(s: str) -> str:
    return s.lower().strip().replace(" ", "_")


def _prettyprint(obj):
    # logger.info(json.dumps(dataclasses.asdict(obj), indent=2))
    logger.info(json.dumps(dataclasses.asdict(obj)))


def _build_prompt(base: str, job: QuoteJob) -> str:
    summary = [
        {
            "space": s.name,
            "rooms": [r.__dict__ for r in s.rooms],
            "notes": s.notes
        }
        for s in job.spaces
    ]
    summary.append({"Project Notes": job.project_notes})

    prompt = f"{base}:\n\n\n\n{summary}"

    potential_zip = job.address.split()[-1] if job.address else ""
    if potential_zip.isdigit() and len(potential_zip) == 5:
        prompt += f"\n\n\n\n(Zip code: {potential_zip})"

    return prompt


def _fetch_config(board_id: str) -> dict:
    monday_secrets = aws_service.get_secret("monday_api_key")
    monday_key = monday_secrets.get("monday_api_key") if isinstance(monday_secrets, dict) else monday_secrets
    market = monday_service.get_market(board_id, monday_key)
    aws_creds = aws_service.get_secret(market)

    return {
        "monday_api_key": monday_key,
        "vertex_key": aws_service.get_secret("vertex_key"),
        "excel_key": aws_service.get_secret("excel_key"),
        "prompt_text_base": PROMPT,
        "rendr_token": rendr_service.get_access_token(aws_creds.get("client_id"), aws_creds.get("secret"))
    }
