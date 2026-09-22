from typing import Dict, Any


# These are only used for RAM / storage because those two recommendations
# are not stored as hardware rows in the current database.
# CPU/GPU prices always come from the database when available.
RAM_PRICE_ESTIMATES = {
    16: 800_000,
    32: 1_500_000,
    64: 3_000_000,
}

STORAGE_PRICE_ESTIMATES = {
    "NVMe M.2 SSD": 1_200_000,
    "NVMe Gen 4": 1_500_000,
}


def money(value):
    try:
        value = float(value or 0)
        return round(value, 0) if value > 0 else None
    except (TypeError, ValueError):
        return None


def get_recommendations(
    db,
    cpu_model,
    gpu_model,
    current_cpu: dict,
    current_gpu: dict,
    current_mb: dict,
    psu_watt: int,
    ram_gb: int,
    storage_type: str,
    resolution: str,
    usage: str,
    decision: dict,
    budget: float = 0.0,
) -> Dict[str, Any]:
    recommendations = {
        "cpu_upgrades": [],
        "gpu_upgrades": [],
        "ram_recommendation": None,
        "storage_recommendation": None,
        "total_known_price": 0.0,
        "total_price_complete": True,
    }

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------
    if storage_type == "HDD":
        storage_price = STORAGE_PRICE_ESTIMATES["NVMe M.2 SSD"]
        recommendations["storage_recommendation"] = {
            "title": "Upgrade to an NVMe M.2 SSD",
            "reason": "Replacing the HDD with an NVMe SSD can significantly improve boot, application and file-loading times.",
            "price": storage_price,
            "price_estimated": True,
            "price_label": f"~{storage_price:,.0f} VND",
        }
    elif storage_type == "SATA SSD" and usage in ["editing", "ai"]:
        storage_price = STORAGE_PRICE_ESTIMATES["NVMe Gen 4"]
        recommendations["storage_recommendation"] = {
            "title": "Add an NVMe Gen 4 drive",
            "reason": "Heavy editing and AI workloads can benefit from faster NVMe storage.",
            "price": storage_price,
            "price_estimated": True,
            "price_label": f"~{storage_price:,.0f} VND",
        }

    # --------------------------------------------------------
    # RAM
    # --------------------------------------------------------
    target_ram = 16
    if usage in ["editing", "programming", "ai"]:
        target_ram = 32

    if ram_gb < target_ram:
        price = RAM_PRICE_ESTIMATES.get(target_ram)
        recommendations["ram_recommendation"] = {
            "title": f"Upgrade to {target_ram}GB RAM ({current_mb.get('ram_type', 'DDR4')})",
            "reason": (
                f"The current {ram_gb}GB capacity may be limiting for {usage.upper()} workloads. "
                f"The motherboard uses {current_mb.get('ram_type', 'DDR4')} memory."
            ),
            "price": price,
            "price_estimated": True,
            "price_label": f"~{price:,.0f} VND" if price else "Price unavailable",
        }

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------
    current_score = current_cpu.get("score") or 0
    if current_score > 0:
        candidate_cpus = db.query(cpu_model).filter(
            cpu_model.socket == current_mb.get("socket"),
            cpu_model.score > current_score * 1.15,
        ).order_by(cpu_model.score.asc()).all()
    else:
        candidate_cpus = []

    for cand in candidate_cpus[:3]:
        gain_pct = round(((cand.score - current_score) / current_score) * 100)
        needed_psu = (cand.tdp or 0) + (current_gpu.get("tdp") or 0) + 150
        psu_ok = psu_watt >= needed_psu
        price = money(getattr(cand, "price", 0))
        within_budget = budget <= 0 or price is None or price <= budget

        recommendations["cpu_upgrades"].append({
            "name": cand.name,
            "socket": cand.socket,
            "cores": cand.cores,
            "score": cand.score,
            "gain_pct": gain_pct,
            "price": price,
            "price_label": f"{price:,.0f} VND" if price is not None else "Price unavailable",
            "price_available": price is not None,
            "within_budget": within_budget,
            "keep_mainboard": True,
            "psu_ok": psu_ok,
            "needed_psu": needed_psu,
            "note": (
                "Same socket; compatible with the current motherboard"
                if psu_ok else f"Requires at least {needed_psu}W PSU"
            ),
        })

    # --------------------------------------------------------
    # GPU
    # --------------------------------------------------------
    current_gpu_score = current_gpu.get("score") or 0
    if current_gpu_score > 0:
        candidate_gpus = db.query(gpu_model).filter(
            gpu_model.score > current_gpu_score * 1.2
        ).order_by(gpu_model.score.asc()).all()
    else:
        candidate_gpus = []

    gpu_candidates = []
    for cand in candidate_gpus:
        gain_pct = round(((cand.score - current_gpu_score) / current_gpu_score) * 100)
        needed_psu = (current_cpu.get("tdp") or 0) + (cand.tdp or 0) + 150
        psu_ok = psu_watt >= needed_psu

        res_suitable = True
        if resolution == "1440p" and (cand.vram or 0) < 8:
            res_suitable = False
        elif resolution == "4k" and (cand.vram or 0) < 12:
            res_suitable = False

        price = money(getattr(cand, "price", 0))
        within_budget = budget <= 0 or price is None or price <= budget

        gpu_candidates.append({
            "name": cand.name,
            "vram": cand.vram,
            "tdp": cand.tdp,
            "score": cand.score,
            "gain_pct": gain_pct,
            "price": price,
            "price_label": f"{price:,.0f} VND" if price is not None else "Price unavailable",
            "price_available": price is not None,
            "within_budget": within_budget,
            "psu_ok": psu_ok,
            "needed_psu": needed_psu,
            "res_suitable": res_suitable,
            "note": (
                f"Compatible with the current {psu_watt}W PSU"
                if psu_ok else f"Requires at least {needed_psu}W PSU"
            ),
        })

    # Prefer resolution-suitable candidates within budget when prices exist.
    budget_and_resolution = [
        g for g in gpu_candidates if g["within_budget"] and g["res_suitable"]
    ]
    resolution_matches = [g for g in gpu_candidates if g["res_suitable"]]

    selected_gpus = budget_and_resolution or resolution_matches or gpu_candidates
    recommendations["gpu_upgrades"] = selected_gpus[:3]

    # --------------------------------------------------------
    # Total price of the displayed recommendations.
    # Only add prices that are actually known. The UI also tells the
    # user when the total is incomplete.
    # --------------------------------------------------------
    price_items = []
    for item in recommendations["cpu_upgrades"]:
        if item["price"] is not None:
            price_items.append(item["price"])
    for item in recommendations["gpu_upgrades"]:
        if item["price"] is not None:
            price_items.append(item["price"])

    if recommendations["ram_recommendation"]:
        price_items.append(recommendations["ram_recommendation"]["price"])
    if recommendations["storage_recommendation"]:
        price_items.append(recommendations["storage_recommendation"]["price"])

    recommendations["total_known_price"] = sum(price_items)
    recommendations["total_price_complete"] = all(
        item.get("price_available", True)
        for item in recommendations["cpu_upgrades"] + recommendations["gpu_upgrades"]
    )

    return recommendations
