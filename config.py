import os

TOKEN_URL = "https://app.rendr.com/o/token/"
API_BASE_URL = "https://app.rendr.com/api/v3"
HOME_STRETCH_URL = "https://dev.api.home-stretch.com/invoices/rendr-submission"

PROJECT_ID = os.getenv("VERTEX_PROJECT_ID", "ascendant-acre-487016-i5")
LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")
DEFAULT_SENDER_EMAIL = "evan.lewis@home-stretch.com"
AWS_DEFAULT_REGION = "us-east-2"

HOMESTRETCH_COOKIE = "connect.sid=s%3A6aKhqLhZbVlBOa-t-ckbGP0XEfVZA_w3.vQROn05nLE6rHemhCwz%2BjtqyTEQqis7YFeLSPv1RnMc"

PROMPT = """
You are a home renovation quoting assistant. You will be given a list of spaces and rooms with their measurements, along with project notes. Your job is to return a JSON object containing the tasks that need to be completed based on the notes.
 
TASK TYPES:
The only valid task_type values are:
- Interior_Painting
- Exterior_Painting
- Cabinet_Painting
- Carpet_Installation
- Flooring_Installation
- Carpet_Cleaning
- Carpet_Removal
- Home_Clear_Outs
- Light_Handyman_Work
- Move_Out_Cleaning
- Landscape_Clean_Up
- Pressure_Washing
- Window_Washing
 
ROOM NAME RULES:
- If a task belongs to a specific room, set room_name to that room's exact label as provided in the input.
- If a task applies to the whole space and not a specific room (e.g. landscaping, dumpster, pressure washing), set room_name to the space name exactly as provided in the input.
- Never leave room_name empty.
 
CRITICAL RULES:
- Always set price to 0.0. The backend recalculates all prices.
- Only create tasks that are explicitly mentioned in the notes. Do not invent tasks.
- Every task must have a room_name that exactly matches either a room label or a space name from the input data.
- Every task must include its corresponding Details object (e.g. Interior_Painting_Details for Interior_Painting).
- Use clear descriptive sentences for service_description.
- For Landscape_Clean_Up tasks: If there is anything specified inside the cleanup request notes, add 1 per man day rate unless specified otherwise. Additionally, calculate that each mulch bed requires exactly 20 bags of mulch.
- For Home_Clear_Outs tasks: Calculate that using a dumpster of any size requires 2 people.
"""

PRICING_CONFIG = {
    "regional_multipliers": 1.00,
    "Interior_Painting": {
        "walls_per_sqft": 1.50,
        "ceiling_per_sqft": 0.33,
        "trim_per_sqft": 0.45,
        "wallpaper_per_sqft": 1.00,
        "priming_per_sqft": 0.50,
        "concrete_floor_paint_flat_rate": 400.00,
        "per_door_rate": 60.00,
        "closet_flat_rate": 75.00,
        "patch_small_rate": 15.00,
        "patch_medium_rate": 35.00,
        "patch_large_rate": 75.00,
    },
    "Exterior_Painting": {
        "base_per_side_rate": 450.00,
        "story_multiplier_step": 1.3,
        "substrate_multipliers": {
            "brick": 1.2,
            "vinyl": 1.0,
            "wood": 1.25,
            "stucco": 1.15,
            "concrete_block": 1.1
        },
        "deck_rates": {
            "none": 0.00,
            "small": 250.00,
            "average": 500.00,
            "large": 900.00
        }
    },
    "Cabinet_Painting": {
        "per_door_rate": 115.00,
        "single_vanity_flat": 200.00,
        "double_vanity_flat": 350.00
    },
    "Carpet_Installation": {
        "waste_factor_multiplier": 1.20,
        "per_sqft_rate": 5.00,
        "per_transition_rate": 35.00,
        "per_stair_step_rate": 7.00,
        "kilz_treatment_flat": 150.00,
        "demo_prep_flat": 125.00,
        "furniture_move_flat": 75.00,
    },
    "Flooring_Installation": {
        "waste_factor_multiplier": 1.10,
        "per_sqft_rates": {
            "LVP": 6.95,
            "LVT": 8.34,
        },
        "quarter_round": 3.60,
        "per_transition_rate": 40.00,
        "kilz_treatment_flat": 150.00,
        "furniture_move_flat": 100.00,
        "per_appliance_rate": 52.50,
        "per_toilet_rate": 42.00,
    },
    "Carpet_Cleaning": {
        "per_room_rate": 95.00
    },
    "Carpet_Removal": {
        "room_flat_rate": 150.00
    },
    "Home_Clear_Outs": {
        "per_box_truck_load": 550.00,
        "dumpster_20yd": 450.00,
        "dumpster_30yd": 550.00,
        "dumpster_40yd": 650.00,
        "per_person_rate": 200.00,
        "margin_multiplier": 2.00,
        "per_tire": 20.00,
        "per_mattress": 50.00,
        "per_refrigerator": 95.00
    },
    "Light_Handyman_Work": {
        "per_cabinet_door_pull_install": 15.00,
        "per_task_rate": 85.00
    },
    "Move_Out_Cleaning": {
        "free_deal_threshold": 10000.00,
        "rates": {
            "none": 0.00,
            "standard": 295.00,
            "messy": 495.00
        }
    },
    "Landscape_Clean_Up": {
        "per_man_day_rate": 400.00,
        "per_mulch_bed_rate": 120.00,
        "per_mulch_bag_rate": 8.50
    },
    "Pressure_Washing": {
        "standalone_flat": 250.00,
        "discounted_with_landscaping": 125.00
    },
    "Window_Washing": {
        "per_pane_rate": 12.00
    },
    "psychology_rules": {
        "apply_above_threshold": 300.00,
        "charm_ends_with": 85.00
    }
}


QUOTE_SCHEMA = {
  "type": "OBJECT",
  "required": ["region", "tasks"],
  "properties": {
    "region": {
      "type": "STRING",
      "enum": ["Western", "Northeast", "Midwest_South"]
    },
    "tasks": {
      "type": "ARRAY",
      "items": {
        "type": "OBJECT",
        "required": ["room_name", "task_type"],
        "properties": {
          "room_name": {
            "type": "STRING",
            "description": ""
          },
          "task_type": {
            "type": "STRING",
            "enum": [
              "Interior_Painting",
              "Exterior_Painting",
              "Cabinet_Painting",
              "Carpet_Installation",
              "Flooring_Installation",
              "Carpet_Cleaning",
              "Carpet_Removal",
              "Home_Clear_Outs",
              "Light_Handyman_Work",
              "Move_Out_Cleaning",
              "Landscape_Clean_Up",
              "Pressure_Washing",
              "Window_Washing"
            ]
          },

          "Interior_Painting_Details": {
            "type": "OBJECT",
            "required": ["service_description", "sub_tasks", "num_doors", "has_closet", "patches_small", "patches_medium", "patches_large"],
            "properties": {
              "service_description": {"type": "STRING"},
              "sub_tasks": {
                "type": "ARRAY",
                "items": {
                  "type": "STRING",
                  "enum": ["walls", "ceiling", "trim", "wallpaper_removal", "priming", "concrete_floor_paint"]
                }
              },
              "num_doors": {"type": "INTEGER"},
              "has_closet": {"type": "BOOLEAN"},
              "patches_small": {"type": "INTEGER"},
              "patches_medium": {"type": "INTEGER"},
              "patches_large": {"type": "INTEGER"}
            }
          },

          "Exterior_Painting_Details": {
            "type": "OBJECT",
            "required": ["service_description", "num_sides", "stories", "substrate", "deck_size"],
            "properties": {
              "service_description": {"type": "STRING"},
              "num_sides": {"type": "INTEGER"},
              "stories": {"type": "INTEGER"},
              "substrate": {
                "type": "STRING",
                "enum": ["brick", "vinyl", "wood", "stucco", "concrete_block"]
              },
              "deck_size": {
                "type": "STRING",
                "enum": ["none", "small", "average", "large"]
              }
            }
          },

          "Cabinet_Painting_Details": {
            "type": "OBJECT",
            "required": ["service_description", "num_doors", "single_vanities", "double_vanities"],
            "properties": {
              "service_description": {"type": "STRING"},
              "num_doors": {"type": "INTEGER"},
              "single_vanities": {"type": "INTEGER"},
              "double_vanities": {"type": "INTEGER"}
            }
          },

          "Carpet_Installation_Details": {
            "type": "OBJECT",
            "required": ["service_description", "transitions", "stair_steps", "kilz_required", "demo_required", "furniture_move"],
            "properties": {
              "service_description": {"type": "STRING"},
              "transitions": {"type": "INTEGER"},
              "stair_steps": {"type": "INTEGER"},
              "kilz_required": {"type": "BOOLEAN"},
              "demo_required": {"type": "BOOLEAN"},
              "furniture_move": {"type": "BOOLEAN"}
            }
          },

          "Flooring_Installation_Details": {
            "type": "OBJECT",
            "required": ["service_description", "material", "transitions", "kilz_required", "furniture_move", "appliances_to_move", "toilets_to_reset"],
            "properties": {
              "service_description": {"type": "STRING"},
              "material": {
                "type": "STRING",
                "enum": ["LVP", "LVT"]
              },
              "transitions": {"type": "INTEGER"},
              "kilz_required": {"type": "BOOLEAN"},
              "furniture_move": {"type": "BOOLEAN"},
              "appliances_to_move": {"type": "INTEGER"},
              "toilets_to_reset": {"type": "INTEGER"}
            }
          },

          "Carpet_Cleaning_Details": {
            "type": "OBJECT",
            "required": ["service_description", "room_count"],
            "properties": {
              "service_description": {"type": "STRING"},
              "room_count": {"type": "INTEGER"}
            }
          },

          "Carpet_Removal_Details": {
            "type": "OBJECT",
            "required": ["service_description", "requested"],
            "properties": {
              "service_description": {"type": "STRING"},
              "requested": {"type": "BOOLEAN"}
            }
          },

          "Home_Clear_Outs_Details": {
            "type": "OBJECT",
            "required": ["service_description", "box_truck_loads", "dumpster_20yd_count", "dumpster_30yd_count", "dumpster_40yd_count", "tire_count", "mattress_count", "refrigerator_count"],
            "properties": {
              "service_description": {"type": "STRING"},
              "box_truck_loads": {"type": "INTEGER"},
              "dumpster_20yd_count": {"type": "INTEGER"},
              "dumpster_30yd_count": {"type": "INTEGER"},
              "dumpster_40yd_count": {"type": "INTEGER"},
              "people_needed": {"type": "INTEGER"},
              "tire_count": {"type": "INTEGER"},
              "mattress_count": {"type": "INTEGER"},
              "refrigerator_count": {"type": "INTEGER"}
            }
          },

          "Light_Handyman_Work_Details": {
            "type": "OBJECT",
            "required": ["service_description", "task_count"],
            "properties": {
              "service_description": {"type": "STRING"},
              "task_count": {"type": "INTEGER"},
              "cabinet_door_pull_amount": {"type": "INTEGER"}
            }
          },

          "Move_Out_Cleaning_Details": {
            "type": "OBJECT",
            "required": ["service_description", "status"],
            "properties": {
              "service_description": {"type": "STRING"},
              "status": {
                "type": "STRING",
                "enum": ["none", "standard", "messy"]
              }
            }
          },

          "Landscape_Clean_Up_Details": {
            "type": "OBJECT",
            "required": ["service_description", "total_man_days", "num_beds_mulched", "num_bags_mulch"],
            "properties": {
              "service_description": {"type": "STRING"},
              "total_man_days": {"type": "INTEGER"},
              "num_beds_mulched": {"type": "INTEGER"},
              "num_bags_mulch": {"type": "INTEGER"}
            }
          },

          "Pressure_Washing_Details": {
            "type": "OBJECT",
            "required": ["service_description", "requested"],
            "properties": {
              "service_description": {"type": "STRING"},
              "requested": {"type": "BOOLEAN"}
            }
          },

          "Window_Washing_Details": {
            "type": "OBJECT",
            "required": ["service_description", "pane_count"],
            "properties": {
              "service_description": {"type": "STRING"},
              "pane_count": {"type": "INTEGER"}
            }
          }

        }
      }
    }
  }
}