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
    decision: dict
) -> Dict[str, Any]:
    recommendations = {
        "cpu_upgrades": [],
        "gpu_upgrades": [],
        "ram_recommendation": None,
        "storage_recommendation": None
    }

    # 1. Storage recommendations
    if storage_type == "HDD":
        recommendations["storage_recommendation"] = {
            "title": "Upgrade to an NVMe M.2 SSD",
            "reason": "Moving the OS from HDD to NVMe SSD can improve boot times and overall system responsiveness by 5-10x."
        }
    elif storage_type == "SATA SSD" and usage in ["editing", "ai"]:
        recommendations["storage_recommendation"] = {
            "title": "Add an NVMe Gen 4 drive",
            "reason": "Video editing and AI model loading involve heavy sustained I/O, and NVMe Gen 4 minimizes file access wait time."
        }

    # 2. RAM recommendations
    target_ram = 16
    if usage in ["editing", "programming"]:
        target_ram = 32
    elif usage == "ai":
        target_ram = 32

    if ram_gb < target_ram:
        recommendations["ram_recommendation"] = {
            "title": f"Upgrade to {target_ram}GB RAM ({current_mb.get('ram_type', 'DDR4')})",
            "reason": f"The current {ram_gb}GB capacity is not enough for smooth {usage.upper()} workloads. The current motherboard supports {current_mb.get('ram_type', 'DDR4')} memory."
        }

    # 3. CPU recommendations (prefer same socket to keep the motherboard)
    candidate_cpus = db.query(cpu_model).filter(
        cpu_model.socket == current_mb["socket"],
        cpu_model.score > current_cpu["score"] * 1.15
    ).order_by(cpu_model.score.asc()).all()

    for cand in candidate_cpus[:3]:
        gain_pct = round(((cand.score - current_cpu["score"]) / current_cpu["score"]) * 100)
        needed_psu = cand.tdp + current_gpu["tdp"] + 150
        psu_ok = psu_watt >= needed_psu

        recommendations["cpu_upgrades"].append({
            "name": cand.name,
            "socket": cand.socket,
            "cores": cand.cores,
            "score": cand.score,
            "gain_pct": gain_pct,
            "keep_mainboard": True,
            "psu_ok": psu_ok,
            "needed_psu": needed_psu,
            "note": "Same socket; compatible with the current motherboard" if psu_ok else f"Requires at least {needed_psu}W PSU"
        })

    # 4. GPU recommendations (based on target resolution and performance)
    candidate_gpus = db.query(gpu_model).filter(
        gpu_model.score > current_gpu["score"] * 1.2
    ).order_by(gpu_model.score.asc()).all()

    for cand in candidate_gpus[:3]:
        gain_pct = round(((cand.score - current_gpu["score"]) / current_gpu["score"]) * 100)
        needed_psu = current_cpu["tdp"] + cand.tdp + 150
        psu_ok = psu_watt >= needed_psu

        res_suitable = True
        if resolution == "1440p" and cand.vram < 8:
            res_suitable = False
        elif resolution == "4k" and cand.vram < 12:
            res_suitable = False

        recommendations["gpu_upgrades"].append({
            "name": cand.name,
            "vram": cand.vram,
            "tdp": cand.tdp,
            "score": cand.score,
            "gain_pct": gain_pct,
            "psu_ok": psu_ok,
            "needed_psu": needed_psu,
            "res_suitable": res_suitable,
            "note": f"Compatible with the current {psu_watt}W PSU" if psu_ok else f"Requires at least {needed_psu}W PSU"
        })

    return recommendations