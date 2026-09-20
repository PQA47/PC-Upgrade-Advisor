def check_compatibility(cpu: dict, motherboard: dict, gpu: dict, psu_wattage: int) -> dict:
    issues = []

    # 1. Check CPU socket vs motherboard socket
    if cpu.get("socket") != motherboard.get("socket"):
        issues.append(
            f"Socket mismatch: CPU {cpu.get('name')} ({cpu.get('socket')}) "
            f"cannot be installed on motherboard {motherboard.get('name')} ({motherboard.get('socket')})."
        )

    # 2. Check PSU capacity (CPU TDP + GPU TDP + 150W headroom)
    total_tdp = cpu.get("tdp", 0) + gpu.get("tdp", 0)
    recommended_psu = total_tdp + 150

    if psu_wattage < recommended_psu:
        issues.append(
            f"Weak PSU: the system is estimated to consume {total_tdp}W (recommended PSU from {recommended_psu}W), "
            f"but you selected a {psu_wattage}W power supply."
        )

    return {
        "is_compatible": len(issues) == 0,
        "issues": issues,
        "estimated_tdp": total_tdp,
        "recommended_psu": recommended_psu
    }