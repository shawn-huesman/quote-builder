import logging

logger = logging.getLogger(__name__)

import ast
import inspect
import sys
import textwrap
from typing import Tuple, Any, Dict


class ExpressionFormatter(ast.NodeVisitor):
    def __init__(self, local_scope: Dict[str, Any], global_scope: Dict[str, Any]):
        self.local_scope = local_scope
        self.global_scope = global_scope

    def _eval(self, node: ast.AST) -> Any:
        try:
            code = compile(ast.Expression(body=node), filename="<ast>", mode="eval")
            return eval(code, self.global_scope, self.local_scope)
        except Exception:
            return None

    def format(self, node: ast.AST) -> Tuple[str, str]:
        if isinstance(node, ast.BinOp):
            left_sym, left_num = self.format(node.left)
            right_sym, right_num = self.format(node.right)
            op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}.get(type(node.op), "?")
            return f"{left_sym} {op} {right_sym}", f"{left_num} {op} {right_num}"

        elif isinstance(node, ast.Name):
            val = self._eval(node)
            num_str = str(round(val, 4)) if isinstance(val, (int, float)) else str(val)
            return node.id, num_str

        elif isinstance(node, ast.Constant):
            return str(node.value), str(node.value)

        elif isinstance(node, ast.Subscript):
            val = self._eval(node)
            key = node.slice.value if isinstance(node.slice, ast.Constant) else "key"
            num_str = str(round(val, 4)) if isinstance(val, (int, float)) else str(val)
            return str(key), num_str

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "max":
                formatted_args_sym = []
                formatted_args_num = []

                for arg in node.args:
                    arg_sym, arg_num = self.format(arg)
                    formatted_args_sym.append(arg_sym)
                    formatted_args_num.append(arg_num)

                sym_str = f"max({', '.join(formatted_args_sym)})"
                num_str = f"max({', '.join(formatted_args_num)})"
                return sym_str, num_str

            if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                val = self._eval(node)
                num_str = str(round(val, 4)) if isinstance(val, (int, float)) else str(val)
                key_name = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else "key"
                return str(key_name), num_str

            val = self._eval(node)
            num_str = str(round(val, 4)) if isinstance(val, (int, float)) else str(val)
            return "val", num_str

        val = self._eval(node)
        num_str = str(round(val, 4)) if isinstance(val, (int, float)) else str(val)
        return "expr", num_str


def explain_method(method, *args, **kwargs) -> Tuple[str, str, float]:
    recorded_steps = []

    def trace_calls(frame, event, arg):
        if event == "line":
            local_scope = frame.f_locals.copy()
            global_scope = frame.f_globals.copy()

            line_code = inspect.getframeinfo(frame).code_context
            if line_code:
                code_str = line_code[0].strip()
                if "+=" in code_str or ("total =" in code_str and "max(" not in code_str):
                    recorded_steps.append((code_str, local_scope, global_scope))
        return trace_calls

    sys.settrace(trace_calls)
    try:
        result = method(*args, **kwargs)
    finally:
        sys.settrace(None)

    terms_symbolic = []
    terms_numeric = []

    for code_str, local_scope, global_scope in recorded_steps:
        if "=" in code_str:
            rhs_str = code_str.split("=", 1)[1].strip()
            try:
                tree = ast.parse(rhs_str, mode="eval")
                formatter = ExpressionFormatter(local_scope, global_scope)
                sym, num = formatter.format(tree.body)

                val = eval(rhs_str, global_scope, local_scope)
                if isinstance(val, (int, float)) and val > 0:
                    terms_symbolic.append(f"({sym})")
                    terms_numeric.append(f"({num})")
            except Exception:
                continue

    symbolic_formula = " + ".join(terms_symbolic) if terms_symbolic else "0"
    numeric_formula = " + ".join(terms_numeric) if terms_numeric else "0"

    return symbolic_formula, numeric_formula, result


class PricingEngine:
    def __init__(self, config: dict):
        self.config = config

    def price_task(self, task_type: str, details: dict, container) -> float:
        method = getattr(self, f"_price_{task_type.lower()}", None)
        if not method:
            logger.warning(f"No pricing rule for task type: {task_type}")
            return 0.0

        price = method(details, container)

        royalty_multiplier = self.config.get("royalty_multiplier", 1.0)
        price *= royalty_multiplier

        task_lower = task_type.lower()
        if "carpet" not in task_lower and "flooring" not in task_lower:
            price = round(price / 5) * 5

        if task_lower == "carpet_cleaning" or task_lower == "carpet_removal":
            price = round(price / 25) * 25

        return float(price)

    def explain_task(self, task_type: str, details: dict, container) -> dict:
        method_name = f"_price_{task_type.lower()}"
        method = getattr(self, method_name, None)
        if not method:
            return {"symbolic": "", "numeric": "", "value": 0.0}

        symbolic, numeric, base_price = explain_method(method, details, container)

        final_price = base_price * self.config.get("royalty_multiplier", 1.0)

        task_lower = task_type.lower()
        if "carpet" not in task_lower and "flooring" not in task_lower:
            final_price = round(final_price / 5) * 5

        if task_lower == "carpet_cleaning" or task_lower == "carpet_removal":
            final_price = round(final_price / 25) * 25

        return {
            "value": float(final_price),
            "symbolic_formula": symbolic,
            "numeric_formula": numeric
        }

    def _price_interior_painting(self, d: dict, container) -> float:
        cfg = self.config["Interior_Painting"]
        sqft = container.paintable_sqft
        perimeter = container.perimeter
        ceiling_sqft = container.ceiling_area
        wall_sqft = container.wall_area

        total = 0.0
        sub = d.get("sub_tasks", [])
        if "walls" in sub:                total += max(wall_sqft * cfg["walls_per_sqft"], cfg["minimum_wall_price"])
        if "ceiling" in sub:              total += max(ceiling_sqft * cfg["ceiling_per_sqft"], cfg["minimum_ceiling_price"])
        if "trim" in sub:                 total += max(perimeter * cfg["trim_per_lnft"], cfg["minimum_trim_price"])
        if "wallpaper_removal" in sub:    total += sqft * cfg["wallpaper_per_sqft"]
        if "priming" in sub:              total += sqft * cfg["priming_per_sqft"]
        if "concrete_floor_paint" in sub: total += sqft * cfg["concrete_floor_paint_per_sqft"]
        if d.get("has_closet"):           total += cfg["closet_flat_rate"]
        total += d.get("num_doors", 0)      * cfg["per_door_rate"]
        total += d.get("patches_small", 0)  * cfg["patch_small_rate"]
        total += d.get("patches_medium", 0) * cfg["patch_medium_rate"]
        total += d.get("patches_large", 0)  * cfg["patch_large_rate"]

        total = max(total, cfg["minimum_painting_price"])
        return total

    def _price_exterior_painting(self, d: dict, container) -> float:
        sqft = container.paintable_sqft
        return sqft * 3.5

    def _price_cabinet_painting(self, d: dict, container) -> float:
        cfg = self.config["Cabinet_Painting"]
        return (
            d.get("num_doors", 0)       * cfg["per_door_rate"] +
            d.get("single_vanities", 0) * cfg["single_vanity_flat"] +
            d.get("double_vanities", 0) * cfg["double_vanity_flat"]
        )

    def _price_carpet_installation(self, d: dict, container) -> float:
        cfg = self.config["Carpet_Installation"]
        ceiling_sqft = container.ceiling_area
        tier = d.get("carpet_tier")
        price_tier_key = f"{tier}_carpet_per_sqft_rate"
        per_sqft_rate = cfg.get(price_tier_key, cfg["tier1_carpet_per_sqft_rate"])

        total = ceiling_sqft * per_sqft_rate * cfg["waste_factor_multiplier"]
        total += (ceiling_sqft / cfg["sqft_per_transition"]) * cfg["per_transition_rate"]
        total += d.get("stair_steps", 0) * cfg["per_stair_step_rate"]
        if d.get("kilz_required"):  total += cfg["kilz_treatment_per_sqft"] * ceiling_sqft
        if d.get("demo_required"):  total += cfg["demo_prep_per_sqft"] * ceiling_sqft
        if d.get("ceramic_demo_required"):  total += cfg["ceramic_demo_prep_per_sqft"] * ceiling_sqft
        if d.get("furniture_move"): total += cfg["furniture_move_per_sqft"] * ceiling_sqft
        total = max(total, cfg["minimum_installation_price"])
        return total

    def _price_flooring_installation(self, d: dict, container) -> float:
        cfg = self.config["Flooring_Installation"]
        sqft = container.ceiling_area
        perimeter = container.perimeter
        material = d.get("material", "LVP")
        rate = cfg["per_sqft_rates"].get(material, cfg["per_sqft_rates"]["LVP"])
        if material == "LVP":
            minimum = cfg["minimum_lvp_installation_price"]
        else:
            minimum = cfg["minimum_lvt_installation_price"]
        total = (sqft * rate * cfg["waste_factor_multiplier"]) + (perimeter * cfg["quarter_round"])
        total += d.get("transitions", 0)        * cfg["per_transition_rate"]
        total += d.get("appliances_to_move", 0) * cfg["per_appliance_rate"]
        total += d.get("toilets_to_reset", 0)   * cfg["per_toilet_rate"]
        if d.get("kilz_required"):  total += cfg["kilz_treatment_per_sqft"] * sqft
        if d.get("demo_required"):  total += cfg["demo_prep_per_sqft"] * sqft
        if d.get("ceramic_demo_required"):  total += cfg["ceramic_demo_prep_per_sqft"] * sqft
        if d.get("furniture_move"): total += cfg["furniture_move_per_sqft"] * sqft
        total = max(total, minimum)
        return total

    def _price_carpet_cleaning(self, d: dict, container) -> float:
        cfg = self.config["Carpet_Cleaning"]

        total = d.get("room_count", 0) * cfg["per_room_rate"]
        if d.get("pet_treatment_required"): total += d.get("room_count", 0) * cfg["pet_treatment_rate"]

        if total > 0:
            total = max(total, cfg["minimum_service_price"])
        return total

    def _price_carpet_removal(self, d: dict, container) -> float:
        return self.config["Carpet_Removal"]["room_flat_rate"] if d.get("requested") else 0.0

    def _price_home_clear_outs(self, d: dict, container) -> float:
        cfg = self.config["Home_Clear_Outs"]
        people_needed = (d.get("dumpster_20yd_count", 0) * cfg["people_needed_per_dumpster_20yd"] +
        d.get("dumpster_30yd_count", 0) * cfg["people_needed_per_dumpster_30yd"] +
        d.get("dumpster_40yd_count", 0) * cfg["people_needed_per_dumpster_40yd"])

        return (
            d.get("box_truck_loads", 0)     * cfg["per_box_truck_load"] +
            d.get("dumpster_20yd_count", 0) * cfg["dumpster_20yd"] +
            d.get("dumpster_30yd_count", 0) * cfg["dumpster_30yd"] +
            d.get("dumpster_40yd_count", 0) * cfg["dumpster_40yd"] +
            d.get("tire_count", 0)          * cfg["per_tire"] +
            d.get("mattress_count", 0)      * cfg["per_mattress"] +
            d.get("refrigerator_count", 0)  * cfg["per_refrigerator"] +
            people_needed * cfg["per_person_rate"]
        ) * cfg["margin_multiplier"]

    def _price_light_handyman_work(self, d: dict, container) -> float:
        cfg = self.config["Light_Handyman_Work"]

        return (
            d.get("task_count", 0) * cfg["per_task_rate"] +
            d.get("cabinet_door_pull_amount", 0) * cfg["per_cabinet_door_pull_install"] +
            d.get("light_fixture_amount", 0) * cfg["per_light_fixture_install"] +
            d.get("ceiling_fan_amount", 0) * cfg["per_ceiling_fan_install"] +
            d.get("mirror_amount", 0) * cfg["per_mirror_install"]
        )

    def _price_move_out_cleaning(self, d: dict, container) -> float:
        cfg = self.config["Move_Out_Cleaning"]
        sqft = container.paintable_sqft

        return (
            max(cfg["base_price"], cfg["per_sqft_price"] * sqft)
        )

    def _price_landscape_clean_up(self, d: dict, container) -> float:
        cfg = self.config["Landscape_Clean_Up"]
        return (
            d.get("total_man_days", 0)   * cfg["per_man_day_rate"] +
            d.get("num_beds_mulched", 0) * cfg["per_mulch_bed_rate"] +
            d.get("num_bags_mulch", 0)   * cfg["per_mulch_bag_rate"]
        )

    def _price_pressure_washing(self, d: dict, container) -> float:
        cfg = self.config["Pressure_Washing"]
        sqft = container.paintable_sqft

        total = 0.00
        if d.get("driveway_requested"): total += cfg["driveway_flat"]
        if d.get("porch_requested"): total += cfg["porch_flat"]
        if d.get("sidewalk_requested"): total += cfg["sidewalk_flat"]
        if d.get("deck_requested"): total += cfg["deck_flat"]
        if d.get("exterior_siding_requested"): total += cfg["exterior_siding_rate"] * sqft

        total = max(total, cfg["minimum_service_price"])
        return total

    def _price_window_washing(self, d: dict, container) -> float:
        return d.get("pane_count", 0) * self.config["Window_Washing"]["per_pane_rate"]


class MaterialPricingEngine:
    def __init__(self, config: dict):
        self.config = config

    def price_task(self, task_type: str, details: dict, container):
        method = getattr(self, f"_price_{task_type.lower()}", None)
        if not method:
            logger.warning(f"No material pricing rule for task type: {task_type}")
            return 0
        return method(details, container)

    def _price_interior_painting(self, d: dict, container) -> float:
        cfg = self.config["Interior_Painting"]
        price = cfg["paint_price_per_gallon"]
        cov = cfg["coverage_sqft_per_gallon"]

        wall_sqft = container.wall_area
        ceiling_sqft = container.ceiling_area
        sqft = container.paintable_sqft
        perimeter = container.perimeter
        sub = d.get("sub_tasks", [])

        total = 0.0

        if "walls" in sub:
            gallons = _round_gallons(wall_sqft / cov["walls"])
            total += gallons * price["walls"]

        if "ceiling" in sub:
            gallons = _round_gallons(ceiling_sqft / cov["ceilings"])
            total += gallons * price["ceilings"]

        if "trim" in sub:
            trim_sqft = perimeter * cfg["trim_sqft_per_lnft"]  # ASSUMPTION #1
            gallons = _round_gallons(trim_sqft / cov["trim_doors"])
            total += gallons * price["trim_doors"]

        if "priming" in sub:
            gallons = _round_gallons(sqft / cov["primer"])
            total += gallons * price["primer"]

        num_doors = d.get("num_doors", 0)
        if num_doors:
            gallons = _round_gallons(num_doors * cfg["cabinet_doors_gallons_per_door"])
            total += gallons * price["trim_doors"]

        # --- sundries ---
        total += cfg["project_setup_fee"]

        if "walls" in sub or "ceiling" in sub:
            total += (wall_sqft + ceiling_sqft) * cfg["surface_area_scaling_fee_per_sqft"]

        if "trim" in sub or num_doors:
            total += cfg["trim_door_caulk_per_room"]

        if "wallpaper_removal" in sub:
            total += cfg["wallpaper_removal_kit_flat"]

        return total

    def _price_exterior_painting(self, d: dict, container) -> float:
        cfg = self.config["Exterior_Painting"]
        sqft = container.paintable_sqft
        stories = d.get("stories", 2)
        story_mult = cfg["story_surface_multiplier"].get(stories, 1.5)
        exterior_sqft = sqft * story_mult

        substrate = d.get("substrate", "vinyl")
        coverage = cfg["coverage_sqft_per_gallon"].get(substrate, 350.0)

        gallons = _round_gallons(exterior_sqft / coverage)
        total = gallons * cfg["paint_price_per_gallon"]
        total += cfg["project_setup_fee"]
        return total

    def _price_cabinet_painting(self, d: dict, container) -> float:
        cfg = self.config["Cabinet_Painting"]
        total_gallons = d.get("num_doors", 0) * cfg["door_gallons_per_door"]
        total_gallons += d.get("single_vanities", 0) * cfg["single_vanity_gallons"]
        total_gallons += d.get("double_vanities", 0) * cfg["double_vanity_gallons"]
        gallons = _round_gallons(total_gallons)
        return gallons * cfg["paint_price_per_gallon"]

    def _price_carpet_installation(self, d: dict, container) -> float:
        cfg = self.config["Carpet_Installation"]
        sqft = container.ceiling_area
        tier = d.get("carpet_tier", "tier1")
        material_rate = cfg["material_per_sqft"].get(tier, cfg["material_per_sqft"]["tier1"])

        total = sqft * material_rate
        total += sqft * cfg["pad_per_sqft"]
        total += sqft * cfg["tack_strips_per_sqft"]
        total += (sqft / 1000.0) * cfg["transition_strips_per_1000_sqft"]
        total += d.get("stair_steps", 0) * cfg["per_step_material_rate"]

        if d.get("kilz_required"):
            total += sqft * cfg["kilz_treatment_per_sqft"]
        if d.get("demo_required"):
            total += sqft * cfg["demo_vinyl_per_sqft"]
        if d.get("ceramic_demo_required"):
            total += sqft * cfg["demo_tile_per_sqft"]
        if d.get("furniture_move"):
            total += sqft * cfg["furniture_move_per_sqft"]

        total = total * (1 + cfg["sales_tax"])

        return total

    def _price_flooring_installation(self, d: dict, container) -> float:
        cfg = self.config["Flooring_Installation"]
        sqft = container.ceiling_area
        material = d.get("material", "LVP")
        material_rate = cfg["material_per_sqft"].get(material, cfg["material_per_sqft"]["LVP"])

        total = sqft * material_rate
        total += sqft * cfg["floor_prep_per_sqft"]
        total += (sqft / 1000.0) * cfg["transition_strips_per_1000_sqft"]
        total += d.get("appliances_to_move", 0) * cfg["per_appliance_rate"]
        total += d.get("toilets_to_reset", 0) * cfg["per_toilet_rate"]

        if d.get("kilz_required"):
            total += sqft * cfg["kilz_treatment_per_sqft"]
        if d.get("demo_required"):
            total += sqft * cfg["demo_vinyl_per_sqft"]
        if d.get("ceramic_demo_required"):
            total += sqft * cfg["demo_tile_per_sqft"]
        if d.get("furniture_move"):
            total += sqft * cfg["furniture_move_per_sqft"]

        total = total * (1 + cfg["sales_tax"])

        return total

    def _price_home_clear_outs(self, d: dict, container) -> float:
        cfg = self.config["Home_Clear_Outs"]
        return (
                d.get("box_truck_loads", 0) * cfg["per_box_truck_load"]
                + d.get("dumpster_20yd_count", 0) * cfg["dumpster_20yd"]
                + d.get("dumpster_30yd_count", 0) * cfg["dumpster_30yd"]
                + d.get("dumpster_40yd_count", 0) * cfg["dumpster_40yd"]
                + d.get("tire_count", 0) * cfg["per_tire"]
                + d.get("mattress_count", 0) * cfg["per_mattress"]
                + d.get("refrigerator_count", 0) * cfg["per_refrigerator"]
        )

    def _price_landscape_clean_up(self, d: dict, container) -> float:
        cfg = self.config["Landscape_Clean_Up"]
        return (
                d.get("num_beds_mulched", 0) * cfg["per_mulch_bed_rate"]
                + d.get("num_bags_mulch", 0) * cfg["per_mulch_bag_rate"]
        )

    def _price_light_handyman_work(self, d: dict, container) -> float:
        cfg = self.config["Light_Handyman_Work"]
        return (
                d.get("cabinet_door_pull_amount", 0) * cfg["per_cabinet_door_pull_material"]
                + d.get("light_fixture_amount", 0) * cfg["per_light_fixture_material"]
                + d.get("ceiling_fan_amount", 0) * cfg["per_ceiling_fan_material"]
                + d.get("mirror_amount", 0) * cfg["per_mirror_material"]
        )


def _round_gallons(gallons: float) -> float:
    if gallons <= 0:
        return 0.0
    whole = int(gallons)
    frac = gallons - whole
    return float(whole + 1) if frac >= 0.2 else float(whole)


class PayoutPricingEngine:
    def __init__(self, config: dict):
        self.config = config

    def price_task(self, task_type: str, details: dict, container):
        method = getattr(self, f"_price_{task_type.lower()}", None)
        if not method:
            logger.warning(f"No material pricing rule for task type: {task_type}")
            return 0
        return method(details, container)

    def _calculate_paint_price(self, task_name: str, container) -> float:
        task = next((t for t in container.tasks if t.task_type == task_name), None)
        if not task:
            return 0.0

        cfg = self.config[task_name]
        royalty_mult = self.config["royalty_multiplier"]
        target_margin = cfg["target_margin"]

        return task.price - (task.price * royalty_mult) - task.material_price - (task.price * target_margin)

    def _calculate_flooring_price(self, task_name: str, container) -> float:
        task = next((t for t in container.tasks if t.task_type == task_name), None)
        if not task:
            return 0.0

        cfg = self.config[task_name]
        royalty_mult = self.config["royalty_multiplier"]
        target_margin = cfg["target_margin"]

        return task.price - (task.price * royalty_mult) - task.material_price - (task.price * target_margin)

    def _price_interior_painting(self, d: dict, container) -> float:
        return self._calculate_paint_price("Interior_Painting", container)

    def _price_exterior_painting(self, d: dict, container) -> float:
        return self._calculate_paint_price("Exterior_Painting", container)

    def _price_cabinet_painting(self, d: dict, container) -> float:
        return self._calculate_paint_price("Cabinet_Painting", container)

    def _price_carpet_installation(self, d: dict, container) -> float:
        return self._calculate_flooring_price("Carpet_Installation", container)

    def _price_flooring_installation(self, d: dict, container) -> float:
        return self._calculate_flooring_price("Flooring_Installation", container)

    def _price_home_clear_outs(self, d: dict, container) -> float:
        cfg = self.config["Home_Clear_Outs"]

        total = (d.get("box_truck_loads", 0) * cfg["per_box_truck_load_people_needed"] * cfg["per_person_rate"]
                + d.get("dumpster_20yd_count", 0) * cfg["dumpster_20yd_people_needed"] + cfg["per_person_rate"]
                + d.get("dumpster_30yd_count", 0) * cfg["dumpster_30yd_people_needed"] + cfg["per_person_rate"]
                + d.get("dumpster_40yd_count", 0) * cfg["dumpster_40yd_people_needed"] + cfg["per_person_rate"])

        return total

    def _price_move_out_cleaning(self, d: dict, container) -> float:
        cfg = self.config["Move_Out_Cleaning"]
        sqft = container.paintable_sqft

        return (
            max(cfg["minimum_price"], cfg["per_sqft_price"] * sqft)
        )

    def _price_carpet_cleaning(self, d: dict, container) -> float:
        cfg = self.config["Carpet_Cleaning"]

        total = d.get("room_count", 0) * cfg["per_room_rate"]

        return total

    def _price_pressure_washing(self, d: dict, container) -> float:
        cfg = self.config["Pressure_Washing"]

        total = cfg["flat_cost"]

        return total

    def _price_landscape_clean_up(self, d: dict, container) -> float:
        cfg = self.config["Landscape_Clean_Up"]

        return max(cfg["minimum_price"], (d.get("total_man_days", 0) * cfg["per_man_day_rate"]))

    def _price_light_handyman_work(self, d: dict, container) -> float:
        cfg = self.config["Light_Handyman_Work"]
        return (
                d.get("cabinet_door_pull_amount", 0) * cfg["per_cabinet_door_pull_material"]
                + d.get("light_fixture_amount", 0) * cfg["per_light_fixture_material"]
                + d.get("ceiling_fan_amount", 0) * cfg["per_ceiling_fan_material"]
                + d.get("mirror_amount", 0) * cfg["per_mirror_material"]
        )
