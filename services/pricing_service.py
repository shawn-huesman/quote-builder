import logging

logger = logging.getLogger(__name__)


class PricingEngine:
    def __init__(self, config: dict):
        self.config = config

    def price_task(self, task_type: str, details: dict, container) -> float:
        method = getattr(self, f"_price_{task_type.lower()}", None)
        if not method:
            logger.warning(f"No pricing rule for task type: {task_type}")
            return 0.0
        return method(details, container)

    def _price_interior_painting(self, d: dict, container) -> float:
        cfg = self.config["Interior_Painting"]
        sqft = container.paintable_sqft
        total = 0.0
        sub = d.get("sub_tasks", [])
        if "walls" in sub:                total += sqft * cfg["walls_per_sqft"]
        if "ceiling" in sub:              total += sqft * cfg["ceiling_per_sqft"]
        if "trim" in sub:                 total += sqft * cfg["trim_per_sqft"]
        if "wallpaper_removal" in sub:    total += sqft * cfg["wallpaper_per_sqft"]
        if "priming" in sub:              total += sqft * cfg["priming_per_sqft"]
        if "concrete_floor_paint" in sub: total += sqft * cfg["concrete_floor_paint_per_sqft"]
        if d.get("has_closet"):           total += cfg["closet_flat_rate"]
        total += d.get("num_doors", 0)      * cfg["per_door_rate"]
        total += d.get("patches_small", 0)  * cfg["patch_small_rate"]
        total += d.get("patches_medium", 0) * cfg["patch_medium_rate"]
        total += d.get("patches_large", 0)  * cfg["patch_large_rate"]
        return total

    def _price_exterior_painting(self, d: dict, container) -> float:
        # Use interior sqft for exterior painting
        sqft = container.paintable_sqft

        cfg = self.config["Exterior_Painting"]
        sub = cfg["substrate_multipliers"].get(d.get("substrate", "vinyl"), 1.0)
        story = cfg["story_multiplier_step"] ** max(0, d.get("stories", 1) - 1)
        base = sqft * cfg["per_interior_sqft_rate"] * sub * story
        deck = cfg["deck_rates"].get(d.get("deck_size", "none"), 0.0)
        return base + deck

    def _price_cabinet_painting(self, d: dict, container) -> float:
        cfg = self.config["Cabinet_Painting"]
        return (
            d.get("num_doors", 0)       * cfg["per_door_rate"] +
            d.get("single_vanities", 0) * cfg["single_vanity_flat"] +
            d.get("double_vanities", 0) * cfg["double_vanity_flat"]
        )

    def _price_carpet_installation(self, d: dict, container) -> float:
        cfg = self.config["Carpet_Installation"]
        total = container.ceiling_area * cfg["per_sqft_rate"] * cfg["waste_factor_multiplier"]
        total += d.get("transitions", 0) * cfg["per_transition_rate"]
        total += d.get("stair_steps", 0) * cfg["per_stair_step_rate"]
        if d.get("kilz_required"):  total += cfg["kilz_treatment_flat"]
        if d.get("demo_required"):  total += cfg["demo_prep_flat"]
        if d.get("furniture_move"): total += cfg["furniture_move_flat"]
        return total

    def _price_flooring_installation(self, d: dict, container) -> float:
        cfg = self.config["Flooring_Installation"]
        sqft = container.ceiling_area
        perimeter = container.perimeter
        rate = cfg["per_sqft_rates"].get(d.get("material", "LVP"), cfg["per_sqft_rates"]["LVP"])
        total = (sqft * rate * cfg["waste_factor_multiplier"]) + (perimeter * cfg["quarter_round"])
        total += d.get("transitions", 0)        * cfg["per_transition_rate"]
        total += d.get("appliances_to_move", 0) * cfg["per_appliance_rate"]
        total += d.get("toilets_to_reset", 0)   * cfg["per_toilet_rate"]
        if d.get("kilz_required"):  total += cfg["kilz_treatment_flat"]
        if d.get("furniture_move"): total += cfg["furniture_move_flat"]
        return total

    def _price_carpet_cleaning(self, d: dict, container) -> float:
        return d.get("room_count", 0) * self.config["Carpet_Cleaning"]["per_room_rate"]

    def _price_carpet_removal(self, d: dict, container) -> float:
        return self.config["Carpet_Removal"]["room_flat_rate"] if d.get("requested") else 0.0

    def _price_home_clear_outs(self, d: dict, container) -> float:
        cfg = self.config["Home_Clear_Outs"]
        return (
            d.get("box_truck_loads", 0)     * cfg["per_box_truck_load"] +
            d.get("dumpster_20yd_count", 0) * cfg["dumpster_20yd"] +
            d.get("dumpster_30yd_count", 0) * cfg["dumpster_30yd"] +
            d.get("dumpster_40yd_count", 0) * cfg["dumpster_40yd"] +
            d.get("tire_count", 0)          * cfg["per_tire"] +
            d.get("mattress_count", 0)      * cfg["per_mattress"] +
            d.get("refrigerator_count", 0)  * cfg["per_refrigerator"] +
            d.get("people_needed", 0) * cfg["per_person_rate"]
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
        return self.config["Move_Out_Cleaning"]["rates"].get(d.get("status", "none"), 0.0)

    def _price_landscape_clean_up(self, d: dict, container) -> float:
        cfg = self.config["Landscape_Clean_Up"]
        return (
            d.get("total_man_days", 0)   * cfg["per_man_day_rate"] +
            d.get("num_beds_mulched", 0) * cfg["per_mulch_bed_rate"] +
            d.get("num_bags_mulch", 0)   * cfg["per_mulch_bag_rate"]
        )

    def _price_pressure_washing(self, d: dict, container) -> float:
        return self.config["Pressure_Washing"]["standalone_flat"] if d.get("requested") else 0.0

    def _price_window_washing(self, d: dict, container) -> float:
        return d.get("pane_count", 0) * self.config["Window_Washing"]["per_pane_rate"]

    def _apply_psychology(self, price: float) -> float:
        rules = self.config["psychology_rules"]
        if price > rules["apply_above_threshold"]:
            return int(price // 100) * 100 + rules["charm_ends_with"]
        return price