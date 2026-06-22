from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Task:
    task_type: str
    details: dict
    service_description: str = ""
    price: float = 0.0


@dataclass
class Room:
    label: str
    wall_area: float = 0.0
    ceiling_area: float = 0.0
    perimeter: float = 0.0
    paintable_sqft: float = 0.0
    doors: int = 0
    windows: int = 0
    tasks: list[Task] = field(default_factory=list)


@dataclass
class Space:
    name: str
    rooms: list[Room] = field(default_factory=list)
    notes: str = ""
    paintable_sqft: float = 0.0
    wall_area: float = 0.0
    ceiling_area: float = 0.0
    perimeter: float = 0.0
    doors: int = 0
    windows: int = 0
    tasks: list[Task] = field(default_factory=list)


@dataclass
class QuoteJob:
    address: str
    monday_item_id: str
    monday_board_id: str
    project_id: Optional[str] = None
    space_ids: list = field(default_factory=list)
    spaces: list[Space] = field(default_factory=list)
    owner_email: Optional[str] = None
    project_notes: Optional[str] = None