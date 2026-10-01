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
    priced = [c for c in candidates if c["price_available"] and c.get("psu_ok", True)]
    affordable = [c for c in priced if budget > 0 and c["price"] <= budget]

    summary = {
        "primary_component": primary_type,
        "upgrade_needed": bool(upgrade_needed),
        "budget": float(budget or 0),
        "status": "no_limit" if budget <= 0 and upgrade_needed else "not_needed" if not upgrade_needed else "price_unavailable",
        "title": "",
        "message": "",
        "selected": None,
        "cheapest_price": min((c["price"] for c in priced), default=None),
        "additional_budget": None,
        "remaining_budget": None,
    }

    if not upgrade_needed:
        summary["title"] = "NO UPGRADE REQUIRED"
        summary["message"] = "The current configuration meets the selected requirements."
        return summary

    if primary_type not in {"CPU", "GPU"}:
        summary["status"] = "price_unavailable"
        summary["title"] = "UPGRADE NEEDED, PRICE UNAVAILABLE"
        summary["message"] = f"The primary {primary_type} upgrade does not have a retail price in the current database, so the budget cannot be evaluated for it yet."
        return summary

    if budget <= 0:
        summary["status"] = "no_limit"
        summary["title"] = "UPGRADE RECOMMENDED"
        if priced:
            chosen = priced[0]
            summary["selected"] = chosen
            summary["message"] = f"A suitable {primary_type.upper()} upgrade is available. No budget limit was specified."
        else:
            summary["message"] = "An upgrade is technically recommended, but no current retail price is available for a suitable option."
        return summary

    if affordable:
        chosen = min(affordable, key=lambda c: (-c.get("score", 0), c["price"]))
        summary["status"] = "within_budget"
        summary["title"] = "UPGRADE FITS YOUR BUDGET"
        summary["selected"] = chosen
        summary["remaining_budget"] = budget - chosen["price"]
        summary["message"] = f"A suitable {primary_type.upper()} upgrade is available within your budget."
        return summary

    if priced:
        cheapest = min(priced, key=lambda c: c["price"])
        summary["status"] = "over_budget"
        summary["title"] = "UPGRADE NEEDED, BUT OVER BUDGET"
        summary["selected"] = cheapest
        summary["additional_budget"] = max(0, cheapest["price"] - budget)
        summary["message"] = f"The cheapest suitable {primary_type.upper()} upgrade is over your budget."
        return summary

    summary["status"] = "price_unavailable"
    summary["title"] = "UPGRADE NEEDED, PRICE UNAVAILABLE"
    summary["message"] = "A technical upgrade is recommended, but current retail pricing is unavailable for suitable parts."
    return summary


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
        "budget_decision": None,
        "total_known_price": 0.0,
        "total_price_complete": False,
    }

    # RAM/storage are still technical recommendations only because their prices
    # are not stored in the current component database.
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

    # CPU candidates: same socket and at least 15% benchmark improvement.
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

    # GPU candidates: at least 20% improvement and suitable VRAM for resolution.
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

    # The alternatives displayed on the page are NOT a shopping cart. Never sum
    # all CPU and GPU recommendation cards.
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

    # Show the selected upgrade price as the headline cost. It is one option,
    # not the sum of all alternatives.
    selected = recommendations["budget_decision"].get("selected")
    recommendations["total_known_price"] = selected["price"] if selected and selected["price_available"] else 0.0
    recommendations["total_price_complete"] = bool(selected and selected["price_available"])

    return recommendations
