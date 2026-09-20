def analyze_bottleneck(cpu_score: int, gpu_score: int) -> dict:
    """Calculate the basic CPU/GPU performance gap ratio."""
    ratio = cpu_score / max(gpu_score, 1)

    if ratio < 0.75:
        pct = round((1 - ratio) * 100, 1)
        msg = f"CPU is the bottleneck (~{pct}%). The GPU is not being fully utilized under heavy load."
        status = "CPU Bottleneck"
    elif ratio > 1.6:
        pct = round((1 - (1 / ratio)) * 100, 1)
        msg = f"GPU is the bottleneck (~{pct}%). The CPU is overpowered for this graphics card."
        status = "GPU Bottleneck"
    else:
        pct = 0.0
        msg = "The system is well-balanced between CPU and GPU."
        status = "Balanced"

    return {
        "status": status,
        "percentage": pct,
        "message": msg
    }


def decide_upgrade(
    cpu: dict,
    gpu: dict,
    ram_gb: int,
    storage_type: str,
    resolution: str,
    usage: str
) -> dict:
    """Evaluate the system comprehensively against real-world needs to decide whether an upgrade is necessary."""
    reasons = []
    verdict_needed = False
    bottleneck_component = None

    # 1. Analyze storage
    if storage_type == "HDD":
        verdict_needed = True
        reasons.append("⚠️ The system is currently using an HDD as the primary drive: read/write speeds are very slow, and upgrading to an NVMe SSD should be the top priority to improve responsiveness.")

    # 2. Analyze RAM according to workload
    if usage in ["gaming", "editing", "programming", "ai"] and ram_gb < 16:
        verdict_needed = True
        reasons.append(f"⚠️ The current RAM capacity of {ram_gb}GB is too low for {usage.upper()} workloads. You should upgrade to at least 16GB or 32GB.")
    elif usage == "ai" and ram_gb < 32:
        reasons.append("💡 AI workload recommendation: use at least 32GB of system RAM to load datasets and models smoothly.")

    # 3. Analyze GPU based on screen resolution and workload
    gpu_vram = gpu.get("vram", 4)
    gpu_score = gpu.get("score", 0)

    if usage == "gaming":
        if resolution == "1440p" and (gpu_score < 18000 or gpu_vram < 8):
            verdict_needed = True
            bottleneck_component = "GPU"
            reasons.append(
                f"⚠️ The current graphics card ({gpu['name']}) is only suitable for 1080p screens, "
                f"but it is becoming the main bottleneck at {resolution} due to insufficient VRAM ({gpu_vram}GB)."
            )
        elif resolution == "4k" and (gpu_score < 28000 or gpu_vram < 12):
            verdict_needed = True
            bottleneck_component = "GPU"
            reasons.append("⚠️ The current graphics card is not powerful enough for 4K gaming.")

    elif usage == "ai":
        if gpu_vram < 8:
            verdict_needed = True
            bottleneck_component = "GPU"
            reasons.append(
                f"⚠️ AI / Deep Learning workloads require a minimum of 8GB-12GB VRAM. "
                f"The current card ({gpu['name']} - {gpu_vram}GB VRAM) will often hit out-of-memory errors."
            )

    # 4. Analyze the CPU vs GPU balance
    cpu_score = cpu.get("score", 0)
    ratio = cpu_score / max(gpu_score, 1)

    if ratio < 0.75:
        verdict_needed = True
        bottleneck_component = "CPU"
        reasons.append(f"⚠️ The CPU ({cpu['name']}) is significantly weaker than the GPU ({gpu['name']}), causing a bottleneck under heavy load.")

    # Final verdict
    if verdict_needed:
        verdict_title = "UPGRADE REQUIRED"
        verdict_summary = "The current configuration has components that are not aligned with your needs or the resolution you selected."
    else:
        verdict_title = "NO UPGRADE REQUIRED"
        verdict_summary = f"Your computer is still handling {usage.upper()} workloads at {resolution} very well."

    return {
        "verdict_title": verdict_title,
        "verdict_needed": verdict_needed,
        "verdict_summary": verdict_summary,
        "reasons": reasons,
        "bottleneck_component": bottleneck_component
    }