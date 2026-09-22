def check_compatibility(cpu: dict, motherboard: dict, gpu: dict, psu_wattage: int) -> dict:
    """
    Check the two important hardware constraints used by the advisor.

    - CPU socket mismatch = hard incompatibility.
    - PSU shortage = power warning, but it should NOT hide the upgrade analysis.
    """

    issues = []

    cpu_socket = cpu.get("socket")
    mb_socket = motherboard.get("socket")

    socket_compatible = cpu_socket == mb_socket

    if not socket_compatible:
        issues.append(
            f"Socket mismatch: CPU {cpu.get('name')} ({cpu_socket}) "
            f"cannot be installed on motherboard {motherboard.get('name')} ({mb_socket})."
        )

    cpu_tdp = cpu.get("tdp") or 0
    gpu_tdp = gpu.get("tdp") or 0

    estimated_tdp = cpu_tdp + gpu_tdp
    recommended_psu = estimated_tdp + 150
    psu_ok = psu_wattage >= recommended_psu

    if not psu_ok:
        issues.append(
            f"Weak PSU: the system is estimated to consume about {estimated_tdp}W "
            f"and needs at least {recommended_psu}W, but you selected {psu_wattage}W."
        )

    return {
        # Hard compatibility: used to decide whether the upgrade engine can run.
        "is_compatible": socket_compatible,

        # More explicit flags for the template.
        "hardware_compatible": socket_compatible,
        "socket_compatible": socket_compatible,
        "psu_ok": psu_ok,

        # True when any warning exists.
        "has_warnings": len(issues) > 0,

        "issues": issues,
        "estimated_tdp": estimated_tdp,
        "recommended_psu": recommended_psu,
    }
