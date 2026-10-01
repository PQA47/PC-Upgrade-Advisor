from typing import Dict, Any


def _price_info(price, budget: float = 0.0, source=None, updated_at=None):
    """Return a consistent price payload. Missing price is never treated as free."""
    try:
        value = float(price or 0)
    except (TypeError, ValueError):
        value = 0.0

    available = value > 0
    within_budget = bool(available and budget > 0 and value <= budget)
    over_budget = bool(available and budget > 0 and value > budget)

    return {
        "price": value,
        "price_available": available,
        "price_label": f"{value:,.0f} VND" if available else "Price unavailable",
        "price_source": source or "",
        "price_updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else (str(updated_at) if updated_at else ""),
        "within_budget": within_budget,
        "over_budget": over_budget,
        "budget_delta": (budget - value) if budget > 0 and available else None,
    }


def _candidate_sort(item):
    """Put affordable priced options first, then priced over-budget options, then unknown prices."""
    return (
        0 if item["within_budget"] else 1 if item["price_available"] else 2,
        item["price"] if item["price_available"] else float("inf"),
        -item.get("score", 0),
    )


def _select_candidates(candidates, limit=3):
    candidates = sorted(candidates, key=_candidate_sort)
    return candidates[:limit]


def _budget_summary(primary_type, candidates, budget, upgrade_needed):
    if not upgrade_needed:
        return {
            "status": "not_needed",
            "title": "SYSTEM IS WELL-BALANCED",
            "message": "No major upgrades are strictly required for your workload at this resolution.",
            "selected": None,
            "budget": budget,
            "primary_component": primary_type,
            "upgrade_needed": False,
            "cheapest_price": None,
            "additional_budget": None,
            "remaining_budget": None,
        }

    priced = [c for c in candidates if c["price_available"]]
    if not priced:
        return {
            "status": "no_pricing",
            "title": "PRICING DATA UNAVAILABLE",
            "message": f"We found matching {primary_type} upgrades, but pricing data is not currently stored in the database.",
            "selected": candidates[0] if candidates else None,
            "budget": budget,
            "primary_component": primary_type,
            "upgrade_needed": True,
            "cheapest_price": None,
            "additional_budget": None,
            "remaining_budget": None,
        }

    cheapest = min(priced, key=lambda x: x["price"])
    selected = None

    if budget > 0:
        affordable = [c for c in priced if c["within_budget"]]
        if affordable:
            selected = max(affordable, key=lambda x: x["score"])
        else:
            selected = cheapest
    else:
        selected = cheapest

    additional_budget = None
    remaining_budget = None
    status = "ok"

    if budget > 0 and selected and selected["price_available"]:
        if selected["price"] <= budget:
            status = "within_budget"
            remaining_budget = budget - selected["price"]
        else:
            status = "over_budget"
            additional_budget = selected["price"] - budget

    return {
        "status": status,
        "title": f"RECOMMENDED {primary_type.upper()} UPGRADE",
        "message": f"Best matching upgrade for your budget and {primary_type} bottleneck.",
        "selected": selected,
        "budget": budget,
        "primary_component": primary_type,
        "upgrade_needed": True,
        "cheapest_price": cheapest["price"],
        "additional_budget": additional_budget,
        "remaining_budget": remaining_budget,
    }


def get_recommendations(
    db: Any,
    cpu_model: Any,
    gpu_model: Any,
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
        "budget_decision": None,
        "total_known_price": 0.0,
        "total_price_complete": False,
    }

    if storage_type == "HDD":
        recommendations["storage_recommendation"] = {
            "title": "Upgrade to an NVMe M.2 SSD",
            "reason": "Moving the OS from HDD to NVMe SSD can improve boot times and overall system responsiveness.",
            "price_label": "Price unavailable",
            "price_available": False,
        }
    elif storage_type == "SATA SSD" and usage in ["editing", "ai"]:
        recommendations["storage_recommendation"] = {
            "title": "Add an NVMe Gen 4 drive",
            "reason": "Video editing and AI model loading involve heavy sustained I/O.",
            "price_label": "Price unavailable",
            "price_available": False,
        }

    target_ram = 32 if usage in ["editing", "programming", "ai"] else 16
    if ram_gb < target_ram:
        recommendations["ram_recommendation"] = {
            "title": f"Upgrade to {target_ram}GB RAM ({current_mb.get('ram_type', 'DDR4')})",
            "reason": f"The current {ram_gb}GB capacity is not enough for smooth {usage.upper()} workloads.",
            "price_label": "Price unavailable",
            "price_available": False,
        }

    current_cpu_score = current_cpu.get("score", 0) or 0
    current_gpu_score = current_gpu.get("score", 0) or 0
    current_gpu_tdp = current_gpu.get("tdp", 0) or 0
    current_cpu_tdp = current_cpu.get("tdp", 0) or 0

    candidate_cpus = db.query(cpu_model).filter(
        cpu_model.socket == current_mb["socket"],
        cpu_model.score > current_cpu_score * 1.15,
    ).order_by(cpu_model.score.asc()).all()

    cpu_candidates = []
    for cand in candidate_cpus:
        gain_pct = round(((cand.score - current_cpu_score) / current_cpu_score) * 100) if current_cpu_score else 0
        needed_psu = (cand.tdp or 0) + current_gpu_tdp + 150
        psu_ok = psu_watt >= needed_psu
        price = _price_info(
            getattr(cand, "price", 0),
            budget,
            getattr(cand, "price_source", None),
            getattr(cand, "price_updated_at", None),
        )
        cpu_candidates.append({
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

    recommendations["cpu_upgrades"] = _select_candidates(cpu_candidates)

    candidate_gpus = db.query(gpu_model).filter(
        gpu_model.score > current_gpu_score * 1.2
    ).order_by(gpu_model.score.asc()).all()

    gpu_candidates = []
    for cand in candidate_gpus:
        gain_pct = round(((cand.score - current_gpu_score) / current_gpu_score) * 100) if current_gpu_score else 0
        needed_psu = current_cpu_tdp + (cand.tdp or 0) + 150
        psu_ok = psu_watt >= needed_psu

        res_suitable = True
        if resolution == "1440p" and (cand.vram or 0) < 8:
            res_suitable = False
        elif resolution == "4k" and (cand.vram or 0) < 12:
            res_suitable = False

        if not res_suitable:
            continue

        price = _price_info(
            getattr(cand, "price", 0),
            budget,
            getattr(cand, "price_source", None),
            getattr(cand, "price_updated_at", None),
        )
        gpu_candidates.append({
            "name": cand.name,
            "vram": cand.vram,
            "tdp": cand.tdp,
            "score": cand.score,
            "gain_pct": gain_pct,
            "psu_ok": psu_ok,
            "needed_psu": needed_psu,
            "res_suitable": True,
            "note": f"Compatible with the current {psu_watt}W PSU" if psu_ok else f"Requires at least {needed_psu}W PSU",
            **price,
        })

    recommendations["gpu_upgrades"] = _select_candidates(gpu_candidates)

    primary_type = decision.get("primary_component") or decision.get("bottleneck_component") or "GPU"
    if primary_type == "CPU":
        budget_candidates = cpu_candidates
    elif primary_type == "GPU":
        budget_candidates = gpu_candidates
    else:
        budget_candidates = []

    recommendations["budget_decision"] = _budget_summary(
        primary_type,
        budget_candidates,
        budget,
        decision.get("verdict_needed", False),
    )

    selected = recommendations["budget_decision"].get("selected")
    recommendations["total_known_price"] = selected["price"] if selected and selected["price_available"] else 0.0
    recommendations["total_price_complete"] = bool(selected and selected["price_available"])

    return recommendations
