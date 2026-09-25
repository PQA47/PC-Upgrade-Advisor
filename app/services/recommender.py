from typing import Dict, Any


def _price_info(price, budget: float = 0.0):
    """Return a consistent price payload for Jinja templates."""
    try:
        value = float(price or 0)
    except (TypeError, ValueError):
        value = 0.0

    available = value > 0
    return {
        "price": value,
        "price_available": available,
        "price_label": f"{value:,.0f} VND" if available else "Price unavailable",
        "within_budget": bool(available and budget > 0 and value <= budget),
    }


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

    # 1. Storage recommendations
    if storage_type == "HDD":
        recommendations["storage_recommendation"] = {
            "title": "Upgrade to an NVMe M.2 SSD",
            "reason": "Moving the OS from HDD to NVMe SSD can improve boot times and overall system responsiveness by 5-10x.",
            "price_label": "Price not stored in database",
        }
    elif storage_type == "SATA SSD" and usage in ["editing", "ai"]:
        recommendations["storage_recommendation"] = {
            "title": "Add an NVMe Gen 4 drive",
            "reason": "Video editing and AI model loading involve heavy sustained I/O, and NVMe Gen 4 minimizes file access wait time.",
            "price_label": "Price not stored in database",
        }

    # 2. RAM recommendations
    target_ram = 16
    if usage in ["editing", "programming", "ai"]:
        target_ram = 32

    if ram_gb < target_ram:
        recommendations["ram_recommendation"] = {
            "title": f"Upgrade to {target_ram}GB RAM ({current_mb.get('ram_type', 'DDR4')})",
            "reason": f"The current {ram_gb}GB capacity is not enough for smooth {usage.upper()} workloads. The current motherboard supports {current_mb.get('ram_type', 'DDR4')} memory.",
            "price_label": "Price not stored in database",
        }

    # 3. CPU recommendations (same socket to keep the motherboard)
    current_cpu_score = current_cpu.get("score", 0) or 0
    current_gpu_tdp = current_gpu.get("tdp", 0) or 0
    current_cpu_tdp = current_cpu.get("tdp", 0) or 0

    candidate_cpus = db.query(cpu_model).filter(
        cpu_model.socket == current_mb["socket"],
        cpu_model.score > current_cpu_score * 1.15,
    ).order_by(cpu_model.score.asc()).all()

    for cand in candidate_cpus[:3]:
        gain_pct = round(((cand.score - current_cpu_score) / current_cpu_score) * 100) if current_cpu_score else 0
        needed_psu = (cand.tdp or 0) + current_gpu_tdp + 150
        psu_ok = psu_watt >= needed_psu
        price = _price_info(getattr(cand, "price", 0), budget)

        recommendations["cpu_upgrades"].append({
            "name": cand.name,
            "socket": cand.socket,
            "cores": cand.cores,
            "score": cand.score,
            "gain_pct": gain_pct,
            "keep_mainboard": True,
            "psu_ok": psu_ok,
            "needed_psu": needed_psu,
            "note": "Same socket; compatible with the current motherboard" if psu_ok else f"Requires at least {needed_psu}W PSU",
            **price,
        })

    # 4. GPU recommendations
    candidate_gpus = db.query(gpu_model).filter(
        gpu_model.score > (current_gpu.get("score", 0) or 0) * 1.2
    ).order_by(gpu_model.score.asc()).all()

    gpu_candidates = []
    for cand in candidate_gpus:
        current_gpu_score = current_gpu.get("score", 0) or 0
        gain_pct = round(((cand.score - current_gpu_score) / current_gpu_score) * 100) if current_gpu_score else 0
        needed_psu = current_cpu_tdp + (cand.tdp or 0) + 150
        psu_ok = psu_watt >= needed_psu

        res_suitable = True
        if resolution == "1440p" and (cand.vram or 0) < 8:
            res_suitable = False
        elif resolution == "4k" and (cand.vram or 0) < 12:
            res_suitable = False

        price = _price_info(getattr(cand, "price", 0), budget)

        gpu_candidates.append({
            "name": cand.name,
            "vram": cand.vram,
            "tdp": cand.tdp,
            "score": cand.score,
            "gain_pct": gain_pct,
            "psu_ok": psu_ok,
            "needed_psu": needed_psu,
            "res_suitable": res_suitable,
            "note": f"Compatible with the current {psu_watt}W PSU" if psu_ok else f"Requires at least {needed_psu}W PSU",
            **price,
        })

    # Prefer resolution-suitable and priced options when possible, while still
    # returning recommendations if the database has no prices.
    suitable = [g for g in gpu_candidates if g["res_suitable"]]
    priced_suitable = [g for g in suitable if g["price_available"]]
    if priced_suitable:
        recommendations["gpu_upgrades"] = priced_suitable[:3]
    else:
        recommendations["gpu_upgrades"] = suitable[:3]

    # The displayed CPU/GPU cards are alternatives, not parts that should all
    # be purchased together. Therefore don't sum all recommendation cards.
    known_prices = [
        item["price"]
        for item in recommendations["cpu_upgrades"] + recommendations["gpu_upgrades"]
        if item["price_available"]
    ]
    recommendations["total_known_price"] = sum(known_prices)
    total_candidates = recommendations["cpu_upgrades"] + recommendations["gpu_upgrades"]
    recommendations["total_price_complete"] = bool(total_candidates) and all(
        item["price_available"] for item in total_candidates
    )

    return recommendations
