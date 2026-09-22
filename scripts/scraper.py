import sys
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional

import requests


# ============================================================
# PROJECT SETUP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.database.database import SessionLocal, engine, Base

try:
    from app.models.component import CPU, GPU, Motherboard
except ImportError:
    from app.models.components import CPU, GPU, Motherboard


Base.metadata.create_all(bind=engine)


# ============================================================
# CONFIG
# ============================================================

TIMEOUT = 30

HEADERS = {
    "User-Agent": "PC-Advisor-University-Project/1.0",
    "Accept": "application/json",
}

# ------------------------------------------------------------
# TechAPI
#
# Structured CPU specifications.
#
# Current repository layout:
#
# data/cpu/<manufacturer>/<year>/<segment>/<slug>.json
#
# We use GitHub's REST Git Trees API to discover those files.
# ------------------------------------------------------------

TECHAPI_REPO_API = (
    "https://api.github.com/repos/"
    "GetTechAPI/TechAPI/git/trees/develop"
)

TECHAPI_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "GetTechAPI/TechAPI/develop/"
)


# ------------------------------------------------------------
# RightNow GPU Database
#
# Correct organization name is RightNow-AI.
# ------------------------------------------------------------

GPU_URLS = {
    "nvidia": (
        "https://raw.githubusercontent.com/"
        "RightNow-AI/RightNow-GPU-Database/"
        "main/data/nvidia/all.json"
    ),

    "amd": (
        "https://raw.githubusercontent.com/"
        "RightNow-AI/RightNow-GPU-Database/"
        "main/data/amd/all.json"
    ),

    "intel": (
        "https://raw.githubusercontent.com/"
        "RightNow-AI/RightNow-GPU-Database/"
        "main/data/intel/all.json"
    ),
}


# ============================================================
# HTTP
# ============================================================

def get_json(url: str) -> Optional[Any]:

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:

        print("⚠️ Failed to download:")
        print(f"   {url}")
        print(f"   {exc}")

        return None

    except ValueError as exc:

        print("⚠️ Invalid JSON:")
        print(f"   {url}")
        print(f"   {exc}")

        return None


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value: Any) -> str:

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def first_value(
    data: dict,
    *keys,
    default=None
):

    for key in keys:

        value = data.get(key)

        if value is not None and value != "":
            return value

    return default


def to_int(
    value,
    default=0
):

    if value is None:
        return default

    try:

        if isinstance(value, bool):
            return default

        text = str(value)

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            text.replace(",", "")
        )

        if not match:
            return default

        return int(
            float(match.group())
        )

    except (
        ValueError,
        TypeError
    ):

        return default


def to_float(
    value,
    default=0.0
):

    if value is None:
        return default

    try:

        text = str(value)

        match = re.search(
            r"-?\d+(?:\.\d+)?",
            text.replace(",", "")
        )

        if not match:
            return default

        return float(
            match.group()
        )

    except (
        ValueError,
        TypeError
    ):

        return default


def normalize_name(
    name: str
) -> str:

    name = clean_text(name)

    name = (
        name
        .replace("®", "")
        .replace("™", "")
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.strip()


# ============================================================
# CPU FILTERING
# ============================================================

def is_desktop_cpu(
    name: str
) -> bool:

    u = name.upper()

    valid_families = [
        "CORE I3",
        "CORE I5",
        "CORE I7",
        "CORE I9",
        "CORE ULTRA",
        "RYZEN 3",
        "RYZEN 5",
        "RYZEN 7",
        "RYZEN 9",
        "THREADRIPPER",
    ]

    if not any(
        family in u
        for family in valid_families
    ):
        return False

    excluded = [
        "MOBILE",
        "LAPTOP",
        "NOTEBOOK",
        "EPYC",
        "XEON",
    ]

    if any(
        item in u
        for item in excluded
    ):
        return False

    return True


# ============================================================
# CPU SOCKET
# ============================================================

def normalize_socket(
    value: str
) -> str:

    if not value:
        return "Other"

    u = str(value).upper()

    sockets = [
        "LGA1851",
        "LGA1700",
        "LGA1200",
        "LGA1151",
        "AM5",
        "AM4",
    ]

    for socket in sockets:

        if socket in u:
            return socket

    return "Other"


def extract_socket(
    data: dict
) -> str:

    value = first_value(
        data,
        "socket",
        "Socket",
        "package",
        "Package",
        "socketType",
        "socket_type",
        default=""
    )

    return normalize_socket(
        clean_text(value)
    )


# ============================================================
# CPU SPEC EXTRACTION
# ============================================================

def extract_cpu_cores(
    data: dict
) -> int:

    value = first_value(
        data,
        "cores",
        "coreCount",
        "core_count",
        "physicalCores",
        "physical_cores",
        default=0
    )

    if isinstance(value, dict):

        value = first_value(
            value,
            "total",
            "physical",
            "count",
            default=0
        )

    return to_int(value)


def extract_cpu_tdp(
    data: dict
) -> int:

    value = first_value(
        data,
        "tdp",
        "TDP",
        "defaultTdp",
        "default_tdp",
        "thermalDesignPower",
        "thermal_design_power",
        default=65
    )

    return to_int(
        value,
        default=65
    )


def extract_cpu_score(
    data: dict
) -> int:

    """
    Only accept an explicitly supplied benchmark score.

    We do NOT calculate a fake benchmark score.
    """

    value = first_value(
        data,
        "score",
        "benchmarkScore",
        "benchmark_score",
        "performanceScore",
        "performance_score",
        default=0
    )

    return to_int(value)


# ============================================================
# TECHAPI TREE
# ============================================================

def get_techapi_cpu_files():

    print(
        "⏳ Discovering CPU JSON files from TechAPI..."
    )

    payload = get_json(
        TECHAPI_REPO_API
        + "?recursive=1"
    )

    if payload is None:

        print(
            "⚠️ Could not access TechAPI GitHub tree."
        )

        return []

    tree = payload.get(
        "tree",
        []
    )

    cpu_files = []

    for item in tree:

        if item.get("type") != "blob":
            continue

        path = item.get(
            "path",
            ""
        )

        # Only CPU JSON records.
        if not path.startswith(
            "data/cpu/"
        ):
            continue

        if not path.endswith(
            ".json"
        ):
            continue

        cpu_files.append(path)

    print(
        f"✓ Found {len(cpu_files)} CPU JSON files."
    )

    return cpu_files


# ============================================================
# CPU SCRAPER
# ============================================================

def scrape_cpus():

    files = get_techapi_cpu_files()

    if not files:
        return []

    def fetch_cpu(path):
        url = TECHAPI_RAW_BASE + path
        return path, get_json(url)

    results = []
    completed = 0
    total = len(files)

    # TechAPI contains thousands of small JSON files. Download them
    # concurrently so the scraper does not spend several minutes waiting
    # on one HTTP request at a time.
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_cpu, path) for path in files]

        for future in as_completed(futures):
            path, data = future.result()
            completed += 1

            if completed % 100 == 0 or completed == total:
                print(f"   Processed {completed}/{total} CPU files...")

            if not isinstance(data, dict):
                continue

            name = first_value(
                data,
                "name",
                "model",
                "title",
                default=""
            )
            name = normalize_name(name)

            if not name or not is_desktop_cpu(name):
                continue

            results.append({
                "name": name,
                "score": extract_cpu_score(data),
                "socket": extract_socket(data),
                "cores": extract_cpu_cores(data),
                "tdp": extract_cpu_tdp(data),
            })

    # Deduplicate
    unique = {}
    for cpu in results:
        key = cpu["name"].lower()
        if key not in unique:
            unique[key] = cpu
        else:
            existing = unique[key]
            if cpu["score"] > existing["score"]:
                existing["score"] = cpu["score"]
            if cpu["cores"] > existing["cores"]:
                existing["cores"] = cpu["cores"]
            if cpu["socket"] != "Other":
                existing["socket"] = cpu["socket"]
            if cpu["tdp"] > 0:
                existing["tdp"] = cpu["tdp"]

    results = list(unique.values())
    print(f"✓ Prepared {len(results)} desktop CPU records.")
    return results


# ============================================================
# GPU
# ============================================================

def is_desktop_gpu(
    name: str
) -> bool:

    u = name.upper()

    valid = [
        "GEFORCE",
        "RTX",
        "GTX",
        "RADEON",
        "RX ",
        "ARC",
    ]

    if not any(
        item in u
        for item in valid
    ):
        return False

    excluded = [
        "LAPTOP",
        "MOBILE",
        "MAX-Q",
        "TESLA",
        "QUADRO",
        "FIREPRO",
        "INTEGRATED",
        "VIRTUAL",
    ]

    if any(
        item in u
        for item in excluded
    ):
        return False

    return True


def extract_gpu_vram(
    data: dict
) -> int:

    value = first_value(
        data,
        "memorySize",
        "memory_size",
        "vram",
        "VRAM",
        default=0
    )

    return int(
        round(
            to_float(value)
        )
    )


def extract_gpu_tdp(
    data: dict
) -> int:

    value = first_value(
        data,
        "tdp",
        "TDP",
        default=150
    )

    return to_int(
        value,
        default=150
    )


def extract_gpu_score(
    data: dict
) -> int:

    """
    Do not manufacture a PassMark score.

    If the structured source has an explicit benchmark
    score, use it. Otherwise return 0.
    """

    value = first_value(
        data,
        "score",
        "benchmarkScore",
        "benchmark_score",
        "performanceScore",
        "performance_score",
        default=0
    )

    return to_int(value)


def target_resolution(
    vram: int
) -> str:

    if vram >= 16:
        return "4K"

    if vram >= 8:
        return "1440p"

    return "1080p"


def load_gpu_source(
    manufacturer: str,
    url: str
):

    print(
        f"   Loading {manufacturer.upper()} GPU data..."
    )

    payload = get_json(url)

    if not isinstance(
        payload,
        list
    ):

        print(
            f"   ⚠️ No usable {manufacturer} "
            "GPU data."
        )

        return []

    print(
        f"   ✓ Received {len(payload)} records."
    )

    return payload


def scrape_gpus():

    print(
        "⏳ Loading GPU data from structured sources..."
    )

    all_records = []

    for manufacturer, url in GPU_URLS.items():

        records = load_gpu_source(
            manufacturer,
            url
        )

        all_records.extend(
            records
        )

    if not all_records:

        print(
            "⚠️ No GPU records received."
        )

        return []

    results = []

    for record in all_records:

        if not isinstance(
            record,
            dict
        ):
            continue

        name = first_value(
            record,
            "name",
            "model",
            "title",
            default=""
        )

        name = normalize_name(
            name
        )

        if not name:
            continue

        if not is_desktop_gpu(
            name
        ):
            continue

        vram = extract_gpu_vram(
            record
        )

        tdp = extract_gpu_tdp(
            record
        )

        score = extract_gpu_score(
            record
        )

        results.append({
            "name": name,
            "score": score,
            "price": 0.0,
            "vram": vram,
            "tdp": tdp,
            "target_res": target_resolution(
                vram
            ),
        })

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    unique = {}

    for gpu in results:

        key = gpu["name"].lower()

        if key not in unique:

            unique[key] = gpu

        else:

            existing = unique[key]

            if gpu["score"] > existing["score"]:
                existing["score"] = gpu["score"]

            if gpu["vram"] > existing["vram"]:
                existing["vram"] = gpu["vram"]

            if gpu["tdp"] > 0:
                existing["tdp"] = gpu["tdp"]

            existing["target_res"] = (
                target_resolution(
                    existing["vram"]
                )
            )

    results = list(
        unique.values()
    )

    print(
        f"✓ Prepared {len(results)} desktop GPU records."
    )

    return results


# ============================================================
# DATABASE - CPU
# ============================================================

def save_cpus(
    db,
    cpu_data
):

    added = 0
    updated = 0
    scores_updated = 0

    for data in cpu_data:

        existing = (
            db.query(CPU)
            .filter(
                CPU.name == data["name"]
            )
            .first()
        )

        if existing:

            if data["score"] > 0:

                existing.score = data["score"]

                scores_updated += 1

            if (
                data["socket"] != "Other"
            ):

                existing.socket = data["socket"]

            if data["cores"] > 0:

                existing.cores = data["cores"]

            if data["tdp"] > 0:

                existing.tdp = data["tdp"]

            updated += 1

        else:

            db.add(
                CPU(
                    name=data["name"],
                    score=data["score"],
                    socket=data["socket"],
                    cores=data["cores"],
                    tdp=data["tdp"],
                )
            )

            added += 1

    db.commit()

    print(
        f"✓ CPU database: "
        f"{added} added, "
        f"{updated} updated, "
        f"{scores_updated} scores updated."
    )


# ============================================================
# DATABASE - GPU
# ============================================================

def save_gpus(
    db,
    gpu_data
):

    added = 0
    updated = 0
    scores_updated = 0

    for data in gpu_data:

        existing = (
            db.query(GPU)
            .filter(
                GPU.name == data["name"]
            )
            .first()
        )

        if existing:

            if data["score"] > 0:

                existing.score = data["score"]

                scores_updated += 1

            if data["vram"] > 0:

                existing.vram = data["vram"]

            if data["tdp"] > 0:

                existing.tdp = data["tdp"]

            existing.target_res = (
                data["target_res"]
            )

            # IMPORTANT:
            #
            # Do not overwrite existing prices.
            #
            # This source provides hardware specs,
            # not retail pricing.

            updated += 1

        else:

            db.add(
                GPU(
                    name=data["name"],
                    score=data["score"],
                    price=data["price"],
                    vram=data["vram"],
                    tdp=data["tdp"],
                    target_res=data["target_res"],
                )
            )

            added += 1

    db.commit()

    print(
        f"✓ GPU database: "
        f"{added} added, "
        f"{updated} updated, "
        f"{scores_updated} scores updated."
    )


# ============================================================
# MOTHERBOARDS
# ============================================================

def sync_motherboards(db):

    print(
        "⏳ Syncing motherboard compatibility data..."
    )

    platforms = [

        # LGA1851
        {
            "socket": "LGA1851",
            "ram": "DDR5",
            "boards": [
                "MSI MEG Z890 ACE",
                "MSI MPG Z890 CARBON WIFI",
                "MSI MAG Z890 TOMAHAWK WIFI",
                "MSI PRO Z890-A WIFI",
                "ASUS ROG MAXIMUS Z890 HERO",
                "ASUS ROG STRIX Z890-E GAMING WIFI",
                "ASUS TUF GAMING Z890-PLUS WIFI",
                "ASUS PRIME Z890-P",
                "Gigabyte Z890 AORUS MASTER",
                "Gigabyte Z890 AORUS ELITE WIFI7",
                "Gigabyte Z890 EAGLE",
                "ASRock Z890 Taichi",
                "ASRock Z890 Steel Legend WiFi",
                "ASRock Z890 Pro RS",
            ],
        },

        # LGA1700 DDR5
        {
            "socket": "LGA1700",
            "ram": "DDR5",
            "boards": [
                "MSI MAG Z790 TOMAHAWK MAX WIFI",
                "MSI PRO Z790-A MAX WIFI",
                "MSI MPG Z790 EDGE TI MAX WIFI",
                "ASUS ROG STRIX Z790-A GAMING WIFI II",
                "ASUS TUF GAMING Z790-PLUS WIFI",
                "ASUS PRIME Z790-P",
                "Gigabyte Z790 AORUS ELITE AX",
                "Gigabyte Z790 GAMING X AX",
                "Gigabyte Z790 EAGLE AX",
                "ASRock Z790 Steel Legend WiFi",
            ],
        },

        # LGA1700 DDR4
        {
            "socket": "LGA1700",
            "ram": "DDR4",
            "boards": [
                "MSI MAG B760 TOMAHAWK WIFI DDR4",
                "MSI PRO B760M-A DDR4",
                "ASUS TUF GAMING B760M-PLUS D4",
                "ASUS PRIME B760M-A D4",
                "Gigabyte B760M DS3H DDR4",
                "Gigabyte B760 GAMING X DDR4",
                "ASRock B760M Pro RS/D4",
                "ASUS H610M-K D4",
                "ASUS PRIME H610M-E D4",
                "MSI PRO H610M-E DDR4",
            ],
        },

        # LGA1200
        {
            "socket": "LGA1200",
            "ram": "DDR4",
            "boards": [
                "MSI MAG B560 TOMAHAWK",
                "MSI MAG B560M MORTAR",
                "MSI B560M PRO-VDH",
                "ASUS TUF GAMING B560-PLUS WIFI",
                "ASUS TUF GAMING B560M-PLUS",
                "ASUS PRIME B560M-A",
                "Gigabyte B560 AORUS PRO AX",
                "Gigabyte B560M AORUS ELITE",
                "Gigabyte B560M DS3H",
                "ASRock B560 Steel Legend",
            ],
        },

        # AM5
        {
            "socket": "AM5",
            "ram": "DDR5",
            "boards": [
                "MSI MAG X870 TOMAHAWK WIFI",
                "MSI MPG X870E CARBON WIFI",
                "ASUS ROG STRIX X870-E GAMING WIFI",
                "Gigabyte X870 AORUS ELITE WIFI7",
                "ASRock X870 Steel Legend WiFi",
                "MSI MAG B650 TOMAHAWK WIFI",
                "MSI B650 GAMING PLUS WIFI",
                "MSI PRO B650M-A WIFI",
                "MSI PRO B650M-P",
                "ASUS TUF GAMING B650-PLUS WIFI",
                "ASUS TUF GAMING B650M-PLUS",
                "ASUS PRIME B650-PLUS",
                "ASUS PRIME B650M-A",
                "Gigabyte B650 AORUS ELITE AX",
                "Gigabyte B650M GAMING X AX",
                "Gigabyte B650M DS3H",
                "ASRock B650 Steel Legend WiFi",
            ],
        },

        # AM4
        {
            "socket": "AM4",
            "ram": "DDR4",
            "boards": [
                "MSI MAG B550 TOMAHAWK",
                "MSI MAG B550M MORTAR",
                "MSI B550-A PRO",
                "MSI B550M PRO-VDH WIFI",
                "ASUS ROG STRIX B550-F GAMING",
                "ASUS TUF GAMING B550-PLUS",
                "ASUS TUF GAMING B550M-PLUS WIFI II",
                "ASUS PRIME B550M-A",
                "Gigabyte B550 AORUS ELITE V2",
                "Gigabyte B550M AORUS ELITE",
                "Gigabyte B550M DS3H",
                "ASRock B550 Steel Legend",
            ],
        },
    ]

    added = 0
    updated = 0

    for platform in platforms:

        for name in platform["boards"]:

            existing = (
                db.query(Motherboard)
                .filter(
                    Motherboard.name == name
                )
                .first()
            )

            if existing:

                existing.socket = (
                    platform["socket"]
                )

                existing.ram_type = (
                    platform["ram"]
                )

                updated += 1

            else:

                db.add(
                    Motherboard(
                        name=name,
                        socket=platform["socket"],
                        ram_type=platform["ram"],
                    )
                )

                added += 1

    db.commit()

    print(
        f"✓ Motherboards: "
        f"{added} added, "
        f"{updated} updated."
    )


# ============================================================
# SYNC FUNCTIONS
# ============================================================

def sync_cpus(db):

    cpu_data = scrape_cpus()

    if not cpu_data:

        print(
            "⚠️ No CPU data was loaded."
        )

        print(
            "   Existing CPU records were preserved."
        )

        return

    save_cpus(
        db,
        cpu_data
    )


def sync_gpus(db):

    gpu_data = scrape_gpus()

    if not gpu_data:

        print(
            "⚠️ No GPU data was loaded."
        )

        print(
            "   Existing GPU records were preserved."
        )

        return

    save_gpus(
        db,
        gpu_data
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print(
        "PC ADVISOR - STRUCTURED HARDWARE DATA SYNC"
    )
    print("=" * 60)

    db = SessionLocal()

    try:

        sync_cpus(db)

        print()

        sync_gpus(db)

        print()

        sync_motherboards(db)

        print()

        print("=" * 60)
        print(
            "🎉 Hardware synchronization completed!"
        )
        print("=" * 60)

    except Exception as exc:

        db.rollback()

        print()
        print(
            "❌ Synchronization failed:"
        )
        print(exc)

        raise

    finally:

        db.close()


if __name__ == "__main__":
    main()