import sys
import re
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

TIMEOUT = 15

# Parallel CPU downloads make the scraper much faster than sequential requests.
CPU_WORKERS = 16

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


# ------------------------------------------------------------
# VTCOM retail price source
#
# VTCOM is a Vietnamese PC retailer. Its CPU and VGA collection
# pages currently expose product prices in VND. We use the lowest
# currently listed price for a matching CPU/GPU model, rather than
# inventing a price.
# ------------------------------------------------------------

VTCOM_COLLECTIONS = {
    "cpu": "https://vtcom.com.vn/collections/chip-xu-ly-cpu-1",
    "gpu": "https://vtcom.com.vn/collections/vga",
}

VTCOM_MAX_PAGES = 10


def normalize_price_model_name(name: str) -> str:
    """Normalize names so retailer names match benchmark database names."""
    value = clean_text(name).lower()
    value = value.replace("™", "").replace("®", "")
    value = value.replace("geforce", " ").replace("radeon", " ")
    value = value.replace("graphics", " ")
    value = re.sub(r"\b(cpu|vga|card|card màn hình)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def cpu_price_key(name: str) -> str:
    """Extract the CPU family/model used for retail-price matching."""
    n = normalize_price_model_name(name)

    patterns = [
        r"\b(core ultra [3579]\s+\d{3,4}[a-z0-9]*)\b",
        r"\b(core [i3579]\s+\d{3,5}[a-z0-9]*)\b",
        r"\b(ryzen\s+(?:threadripper\s+)?[3579]\s+\d{3,5}[a-z0-9]*)\b",
        r"\b(ryzen\s+\d{3,5}[a-z0-9]*)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, n, re.I)
        if match:
            return normalize_price_model_name(match.group(1))

    return n


def gpu_price_key(name: str) -> str:
    """
    Convert both database names and retailer board-partner names to the same
    canonical GPU model.

    Examples:
      NVIDIA GeForce RTX 3060 -> rtx 3060
      ASUS Dual GeForce RTX 3060 OC Edition 12GB -> rtx 3060
      MSI GeForce RTX 3060 VENTUS 2X 12G OC -> rtx 3060
      AMD Radeon RX 6700 XT -> rx 6700 xt
      SAPPHIRE Radeon RX 6700 XT -> rx 6700 xt
    """
    n = normalize_price_model_name(name)

    # Put the model suffix before optional VRAM text.
    patterns = [
        r"\brtx\s*([2-5]\d{3})\s*(ti\s*super|ti|super)?\b",
        r"\bgtx\s*(\d{3,4})\s*(ti|super)?\b",
        r"\brx\s*(\d{3,4})\s*(xtx|xt|gre)?\b",
        r"\barc\s*([ab]\d{3,4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, n, re.I)
        if not match:
            continue

        model = match.group(0)
        model = re.sub(r"\s+", " ", model).strip()
        return model.lower()

    return n


def parse_vnd_price(value: Any) -> float:
    """Convert VND text/numeric values to a positive float."""
    if value is None:
        return 0.0

    text = clean_text(value)
    if not text:
        return 0.0

    # 5,990,000₫ / 5.990.000 đ / 5990000
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        return 0.0

    try:
        price = float(digits)
    except ValueError:
        return 0.0

    # Retail VND prices should be meaningful hardware prices.
    return price if price >= 100_000 else 0.0


def fetch_vtcom_json_collection(url: str, kind: str) -> list[dict]:
    """Fetch Shopify collection pages concurrently and return {name, price} records."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    PAGE_WORKERS = 6

    def fetch_page(page):
        endpoint = f"{url}/products.json?limit=250&page={page}"

        try:
            response = requests.get(
                endpoint,
                headers={
                    **HEADERS,
                    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
                },
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            return page, payload.get("products", [])
        except Exception as exc:
            print(f"\n⚠️ VTCOM {kind} page {page} failed: {exc}")
            return page, []

    products = []

    # Shopify pagination is independent, so fetch the first batch concurrently.
    with ThreadPoolExecutor(max_workers=PAGE_WORKERS) as executor:
        futures = [
            executor.submit(fetch_page, page)
            for page in range(1, VTCOM_MAX_PAGES + 1)
        ]

        for future in as_completed(futures):
            _, page_products = future.result()

            for product in page_products:
                name = normalize_name(product.get("title", ""))
                if not name:
                    continue

                prices = [
                    parse_vnd_price(v.get("price"))
                    for v in product.get("variants", [])
                ]
                prices = [p for p in prices if p > 0]

                if prices:
                    products.append({
                        "name": name,
                        "price": min(prices),
                    })

    return products


def scrape_vtcom_prices(kind: str) -> dict[str, float]:
    """
    Return model-key -> lowest current VTCOM retail price in VND.

    VTCOM is used only for price enrichment; hardware specifications
    continue to come from TechAPI/RightNow.
    """
    url = VTCOM_COLLECTIONS[kind]

    print(f"\n⏳ Fetching current VTCOM {kind.upper()} retail prices...")

    products = fetch_vtcom_json_collection(url, kind)

    if not products:
        print(f"⚠️ No VTCOM {kind.upper()} prices were found.")
        return {}

    prices = {}

    key_func = cpu_price_key if kind == "cpu" else gpu_price_key

    for product in products:
        key = key_func(product["name"])
        price = product["price"]

        if not key or price <= 0:
            continue

        if key not in prices or price < prices[key]:
            prices[key] = price

    print(
        f"✓ Found {len(prices)} current VTCOM {kind.upper()} model prices."
    )

    return prices


def enrich_cpu_prices(cpu_data: list[dict], price_map: dict[str, float]) -> int:
    matched = 0

    for cpu in cpu_data:
        key = cpu_price_key(cpu["name"])
        price = price_map.get(key, 0.0)

        if price > 0:
            cpu["price"] = price
            matched += 1

    return matched


def enrich_gpu_prices(gpu_data: list[dict], price_map: dict[str, float]) -> int:
    matched = 0

    for gpu in gpu_data:
        key = gpu_price_key(gpu["name"])
        price = price_map.get(key, 0.0)

        if price > 0:
            gpu["price"] = price
            matched += 1

    return matched


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
# PROGRESS DISPLAY
# ============================================================

def show_progress(current: int, total: int, label: str = "", width: int = 32):
    """Draw a simple terminal progress bar without extra dependencies."""
    if total <= 0:
        return

    current = min(current, total)
    ratio = current / total
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    percent = ratio * 100
    message = f"[{bar}] {percent:6.2f}% ({current}/{total})"
    if label:
        message += f" | {label[:55]}"

    print("\r" + message.ljust(100), end="", flush=True)

    if current >= total:
        print()


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


def extract_price_vnd(data: dict) -> float:
    """Extract a retail price in VND when the source actually provides one.

    The current TechAPI and RightNow GPU datasets are specification datasets and
    normally do not contain retail prices. Therefore this function returns 0.0
    when no explicit price field is present instead of inventing a price.
    """
    candidates = [
        "price",
        "priceVnd",
        "price_vnd",
        "retailPrice",
        "retail_price",
        "msrp",
        "MSRP",
    ]

    for key in candidates:
        value = data.get(key)
        if value is None or value == "":
            continue

        # Support nested objects such as {"amount": 123, "currency": "VND"}.
        if isinstance(value, dict):
            amount = first_value(value, "amount", "value", "price", default=None)
            currency = clean_text(first_value(value, "currency", "currencyCode", default="")).upper()
            if amount is not None and (not currency or currency in {"VND", "VNĐ", "₫"}):
                parsed = to_float(amount)
                if parsed > 0:
                    return parsed
            continue

        text = clean_text(value)
        upper = text.upper()
        parsed = to_float(value)
        if parsed <= 0:
            continue

        # Only treat an explicit VND/₫ value as VND. Numeric values are accepted
        # because the project database stores component prices in VND.
        if "VND" in upper or "VNĐ" in upper or "₫" in text or re.fullmatch(r"[\d\s,.-]+", text):
            return parsed

    return 0.0


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
        "\n⏳ Discovering CPU JSON files from TechAPI..."
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

    # CPU data is stored as many small JSON files. Downloading them one-by-one
    # is the main bottleneck, so fetch several files concurrently.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    MAX_WORKERS = CPU_WORKERS
    total_files = len(files)
    results = []
    completed = 0

    def fetch_cpu(path):
        url = TECHAPI_RAW_BASE + path
        data = get_json(url)

        if not isinstance(data, dict):
            return None

        name = normalize_name(first_value(
            data, "name", "model", "title", default=""
        ))

        if not name or not is_desktop_cpu(name):
            return None

        return {
            "name": name,
            "score": extract_cpu_score(data),
            "price": extract_price_vnd(data),
            "socket": extract_socket(data),
            "cores": extract_cpu_cores(data),
            "tdp": extract_cpu_tdp(data),
        }

    print(f"⏳ Downloading {total_files} CPU files with {MAX_WORKERS} workers...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_cpu, path): path for path in files}

        for future in as_completed(futures):
            path = futures[future]
            completed += 1

            try:
                cpu = future.result()
                if cpu is not None:
                    results.append(cpu)
                label = f"CPU: {Path(path).name}"
            except Exception as exc:
                label = f"CPU error: {Path(path).name} ({exc})"

            show_progress(completed, total_files, label)

    # --------------------------------------------------------
    # Retail price enrichment
    # --------------------------------------------------------

    cpu_price_map = scrape_vtcom_prices("cpu")
    cpu_price_matches = enrich_cpu_prices(results, cpu_price_map)

    print(
        f"✓ Matched current VTCOM prices to {cpu_price_matches} CPU records."
    )

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

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

            if cpu.get("price", 0) > 0:
                existing["price"] = cpu["price"]

    results = list(unique.values())

    print(f"✓ Prepared {len(results)} desktop CPU records.")

    return results

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

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

            if (
                cpu["socket"] != "Other"
            ):
                existing["socket"] = cpu["socket"]

            if cpu["tdp"] > 0:
                existing["tdp"] = cpu["tdp"]

            if cpu.get("price", 0) > 0:
                existing["price"] = cpu["price"]

    results = list(
        unique.values()
    )

    print(
        f"✓ Prepared {len(results)} desktop CPU records."
    )

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
        "\n⏳ Loading GPU data from structured sources..."
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

    total_records = len(all_records)

    for index, record in enumerate(all_records, start=1):

        show_progress(
            index - 1,
            total_records,
            "GPU: processing records"
        )

        if not isinstance(
            record,
            dict
        ):
            show_progress(index, total_records, "GPU: skipped invalid record")
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

        price = extract_price_vnd(record)

        results.append({
            "name": name,
            "score": score,
            "price": price,
            "vram": vram,
            "tdp": tdp,
            "target_res": target_resolution(
                vram
            ),
        })

        show_progress(
            index,
            total_records,
            f"GPU: processed {name}"
        )

    # --------------------------------------------------------
    # Retail price enrichment
    # --------------------------------------------------------

    gpu_price_map = scrape_vtcom_prices("gpu")
    gpu_price_matches = enrich_gpu_prices(results, gpu_price_map)

    print(
        f"✓ Matched current VTCOM prices to {gpu_price_matches} GPU records."
    )

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

            if gpu.get("price", 0) > 0:
                existing["price"] = gpu["price"]

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

            if data.get("price", 0) > 0:

                existing.price = data["price"]

            updated += 1

        else:

            db.add(
                CPU(
                    name=data["name"],
                    score=data["score"],
                    socket=data["socket"],
                    cores=data["cores"],
                    tdp=data["tdp"],
                    price=data.get("price", 0.0),
                )
            )

            added += 1

    db.commit()

    priced = sum(1 for data in cpu_data if data.get("price", 0) > 0)
    print(
        f"✓ CPU database: "
        f"{added} added, "
        f"{updated} updated, "
        f"{scores_updated} scores updated, "
        f"{priced} source prices found."
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

            # Keep the existing database price unless the source provides
            # a new explicit VND price.
            if data.get("price", 0) > 0:
                existing.price = data["price"]

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

    priced = sum(1 for data in gpu_data if data.get("price", 0) > 0)
    print(
        f"✓ GPU database: "
        f"{added} added, "
        f"{updated} updated, "
        f"{scores_updated} scores updated, "
        f"{priced} source prices found."
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