from typing import Dict, Any


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
    budget: float = 0.0
) -> Dict[str, Any]:
    recommendations = {
        "cpu_upgrades": [],
        "gpu_upgrades": [],
        "ram_recommendation": None,
        "storage_recommendation": None,
    }

    # ---------------------------------------------------------
    # 1. STORAGE
    # ---------------------------------------------------------
    if storage_type == "HDD":
        recommendations["storage_recommendation"] = {
            "title": "Upgrade to an NVMe M.2 SSD",
            "reason": (
                "Moving the operating system from HDD to NVMe SSD can "
                "significantly improve boot time and system responsiveness."
            ),
        }

    elif storage_type == "SATA SSD" and usage in ["editing", "ai"]:
        recommendations["storage_recommendation"] = {
            "title": "Add an NVMe Gen 4 SSD",
            "reason": (
                "Editing and AI workloads can benefit from faster sustained "
                "storage throughput and lower file-access latency."
            ),
        }

    # ---------------------------------------------------------
    # 2. RAM
    # ---------------------------------------------------------
    target_ram = 16

    if usage in ["editing", "programming", "ai"]:
        target_ram = 32

    if ram_gb < target_ram:
        recommendations["ram_recommendation"] = {
            "title": f"Upgrade to {target_ram}GB RAM ({current_mb.get('ram_type', 'DDR4')})",
            "reason": (
                f"The current {ram_gb}GB may be limiting for {usage.upper()} "
                f"workloads. The motherboard uses {current_mb.get('ram_type', 'DDR4')} memory."
            ),
        }

    # ---------------------------------------------------------
    # 3. CPU
    # Same socket + at least 15% performance improvement.
    # ---------------------------------------------------------
    current_cpu_score = current_cpu.get("score") or 0

    if current_cpu_score > 0:
        candidate_cpus = (
            db.query(cpu_model)
            .filter(
                cpu_model.socket == current_mb.get("socket"),
                cpu_model.score > current_cpu_score * 1.15,
            )
            .order_by(cpu_model.score.asc())
            .all()
        )

        for cand in candidate_cpus[:3]:
            gain_pct = round(
                ((cand.score - current_cpu_score) / current_cpu_score) * 100
            )

            needed_psu = (
                (cand.tdp or 0)
                + (current_gpu.get("tdp") or 0)
                + 150
            )
            psu_ok = psu_watt >= needed_psu

            recommendations["cpu_upgrades"].append(
                {
                    "name": cand.name,
                    "socket": cand.socket,
                    "cores": cand.cores,
                    "score": cand.score,
                    "gain_pct": gain_pct,
                    "keep_mainboard": True,
                    "psu_ok": psu_ok,
                    "needed_psu": needed_psu,
                    "note": (
                        "Same socket; current motherboard can support this upgrade."
                        if psu_ok
                        else f"Requires at least {needed_psu}W PSU."
                    ),
                }
            )

    # ---------------------------------------------------------
    # 4. GPU
    # At least 20% performance improvement.
    # Budget is applied when a usable price exists.
    # ---------------------------------------------------------
    current_gpu_score = current_gpu.get("score") or 0

    if current_gpu_score > 0:
        candidate_gpus = (
            db.query(gpu_model)
            .filter(gpu_model.score > current_gpu_score * 1.20)
            .order_by(gpu_model.score.asc())
            .all()
        )

        suitable_gpus = []

        for cand in candidate_gpus:
            gain_pct = round(
                ((cand.score - current_gpu_score) / current_gpu_score) * 100
            )

            needed_psu = (
                (current_cpu.get("tdp") or 0)
                + (cand.tdp or 0)
                + 150
            )
            psu_ok = psu_watt >= needed_psu

            # Resolution suitability.
            res_suitable = True

            if resolution == "1440p" and (cand.vram or 0) < 8:
                res_suitable = False
            elif resolution == "4k" and (cand.vram or 0) < 12:
                res_suitable = False

            # Budget support. Old rows without price remain usable.
            price = getattr(cand, "price", None)
            within_budget = True

            if budget and budget > 0 and price is not None and price > 0:
                within_budget = price <= budget

            suitable_gpus.append(
                {
                    "name": cand.name,
                    "vram": cand.vram,
                    "tdp": cand.tdp,
                    "score": cand.score,
                    "price": price if price is not None else 0,
                    "gain_pct": gain_pct,
                    "psu_ok": psu_ok,
                    "needed_psu": needed_psu,
                    "res_suitable": res_suitable,
                    "within_budget": within_budget,
                    "note": (
                        f"Compatible with the current {psu_watt}W PSU."
                        if psu_ok
                        else f"Requires at least {needed_psu}W PSU."
                    ),
                }
            )

        # Prefer cards suitable for the requested resolution and budget.
        # Do not completely remove all results if price data is unavailable.
        budget_matches = [
            g for g in suitable_gpus
            if g["within_budget"] and g["res_suitable"]
        ]
        resolution_matches = [
            g for g in suitable_gpus
            if g["res_suitable"]
        ]

        if budget_matches:
            recommendations["gpu_upgrades"] = budget_matches[:3]
        elif resolution_matches:
            recommendations["gpu_upgrades"] = resolution_matches[:3]
        else:
            recommendations["gpu_upgrades"] = suitable_gpus[:3]

    return recommendations
