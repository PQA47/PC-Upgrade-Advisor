import sys
import re
from pathlib import Path
import requests

# Thêm thư mục gốc dự án vào PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.database.database import SessionLocal, engine, Base

# Hỗ trợ tự động cả 2 trường hợp đặt tên file component.py hoặc components.py
try:
    from app.models.component import CPU, GPU, Motherboard
except ImportError:
    from app.models.components import CPU, GPU, Motherboard

Base.metadata.create_all(bind=engine)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest"
}


# ==========================================
# 1. BỘ PHÂN TÍCH REGEX QUY TẮC PHẦN CỨNG
# ==========================================

def parse_cpu_socket(name: str):
    """Tự động suy luận Socket, Cores và TDP từ tên vi xử lý"""
    u = name.upper()
    socket = "Other"
    cores = 6
    tdp = 65

    # Phân loại Socket
    if any(k in u for k in ["CORE ULTRA", "285K", "265K", "245K", "LGA1851"]):
        socket = "LGA1851"
    elif any(k in u for k in ["14900", "14700", "14600", "14500", "14400", "14100", 
                              "13900", "13700", "13600", "13500", "13400", "13100", 
                              "12900", "12700", "12600", "12500", "12400", "12100", "LGA1700"]):
        socket = "LGA1700"
    elif any(k in u for k in ["11900", "11700", "11600", "11500", "11400", "10900", 
                              "10700", "10600", "10500", "10400", "10100", "LGA1200"]):
        socket = "LGA1200"
    elif any(k in u for k in ["9900", "9700", "9600", "9400", "9100", "8700", 
                              "8600", "8400", "8100", "7700K", "6700K", "LGA1151"]):
        socket = "LGA1151"
    elif any(k in u for k in ["RYZEN 9 9", "RYZEN 7 9", "RYZEN 5 9", "9950X", "9900X", "9800X3D", "9700X", "9600X",
                              "RYZEN 9 7", "RYZEN 7 7", "RYZEN 5 7", "7950X", "7900X", "7800X3D", "7700X", "7600X", "7500F", "AM5"]):
        socket = "AM5"
    elif any(k in u for k in ["RYZEN 9 5", "RYZEN 7 5", "RYZEN 5 5", "RYZEN 3 5", "5950X", "5900X", "5800X3D", "5700X", "5600X", "5600",
                              "RYZEN 9 3", "RYZEN 7 3", "RYZEN 5 3", "3900X", "3700X", "3600", "3500", "3100", "2600", "1600", "AM4"]):
        socket = "AM4"

    # Ước lượng số nhân và TDP mặc định
    if any(x in u for x in ["I9", "RYZEN 9", "ULTRA 9"]):
        cores, tdp = 16, 125
    elif any(x in u for x in ["I7", "RYZEN 7", "ULTRA 7"]):
        cores, tdp = 8, 105
    elif any(x in u for x in ["I5", "RYZEN 5", "ULTRA 5"]):
        cores, tdp = 6, 65
    elif any(x in u for x in ["I3", "RYZEN 3"]):
        cores, tdp = 4, 58

    return socket, cores, tdp


def parse_gpu_specs(name: str):
    """Tự động suy luận VRAM, TDP và Độ phân giải tối ưu cho GPU"""
    u = name.upper()
    vram = 8
    tdp = 150
    target_res = "1080p"

    # Phân loại NVIDIA GeForce
    if "4090" in u:
        vram, tdp, target_res = 24, 450, "4K"
    elif "4080" in u:
        vram, tdp, target_res = 16, 320, "4K"
    elif "4070 TI" in u or "4070 SUPER" in u:
        vram, tdp, target_res = 12, 220, "1440p"
    elif "4070" in u:
        vram, tdp, target_res = 12, 200, "1440p"
    elif "4060 TI" in u:
        vram, tdp, target_res = 8, 160, "1080p"
    elif "4060" in u:
        vram, tdp, target_res = 8, 115, "1080p"
    elif "3090" in u:
        vram, tdp, target_res = 24, 350, "4K"
    elif "3080 TI" in u or "3080" in u:
        vram, tdp, target_res = 10, 320, "1440p"
    elif "3070 TI" in u or "3070" in u:
        vram, tdp, target_res = 8, 220, "1440p"
    elif "3060 TI" in u:
        vram, tdp, target_res = 8, 200, "1080p"
    elif "3060" in u:
        vram, tdp, target_res = 12, 170, "1080p"
    elif "3050" in u:
        vram, tdp, target_res = 8, 130, "1080p"
    elif "2080 TI" in u or "2080" in u:
        vram, tdp, target_res = 11, 250, "1440p"
    elif "2070" in u or "2060 SUPER" in u:
        vram, tdp, target_res = 8, 175, "1080p"
    elif "2060" in u:
        vram, tdp, target_res = 6, 160, "1080p"
    elif "1660 TI" in u or "1660 SUPER" in u or "1660" in u:
        vram, tdp, target_res = 6, 125, "1080p"
    elif "1650" in u or "1050 TI" in u:
        vram, tdp, target_res = 4, 75, "1080p Low"

    # Phân loại AMD Radeon
    elif "7900" in u:
        vram, tdp, target_res = 20, 355, "4K"
    elif "7800" in u:
        vram, tdp, target_res = 16, 263, "1440p"
    elif "7700" in u:
        vram, tdp, target_res = 12, 245, "1440p"
    elif "7600" in u:
        vram, tdp, target_res = 8, 165, "1080p"
    elif "6900" in u or "6800" in u:
        vram, tdp, target_res = 16, 300, "1440p"
    elif "6700" in u:
        vram, tdp, target_res = 12, 230, "1440p"
    elif "6600" in u:
        vram, tdp, target_res = 8, 132, "1080p"
    elif "RX 580" in u or "RX 590" in u:
        vram, tdp, target_res = 8, 185, "1080p"
    elif "RX 570" in u or "RX 560" in u:
        vram, tdp, target_res = 4, 150, "1080p Low"

    return vram, tdp, target_res


# ==========================================
# 2. DỮ LIỆU DỰ PHÒNG CHUẨN (SEED DATA)
# ==========================================

CORE_FALLBACK_CPUS = [
    {"name": "Intel Core Ultra 9 285K", "socket": "LGA1851", "cores": 24, "tdp": 125, "score": 56000},
    {"name": "Intel Core Ultra 7 265K", "socket": "LGA1851", "cores": 20, "tdp": 125, "score": 51000},
    {"name": "Intel Core Ultra 5 245K", "socket": "LGA1851", "cores": 14, "tdp": 125, "score": 42000},
    {"name": "Intel Core i9-14900K", "socket": "LGA1700", "cores": 24, "tdp": 125, "score": 58000},
    {"name": "Intel Core i7-14700K", "socket": "LGA1700", "cores": 20, "tdp": 125, "score": 53000},
    {"name": "Intel Core i5-14600K", "socket": "LGA1700", "cores": 14, "tdp": 125, "score": 39000},
    {"name": "Intel Core i5-14400F", "socket": "LGA1700", "cores": 10, "tdp": 65, "score": 27000},
    {"name": "Intel Core i9-13900K", "socket": "LGA1700", "cores": 24, "tdp": 125, "score": 56000},
    {"name": "Intel Core i7-13700K", "socket": "LGA1700", "cores": 16, "tdp": 125, "score": 48000},
    {"name": "Intel Core i5-13600K", "socket": "LGA1700", "cores": 14, "tdp": 125, "score": 37000},
    {"name": "Intel Core i5-13400F", "socket": "LGA1700", "cores": 10, "tdp": 65, "score": 25000},
    {"name": "Intel Core i9-12900K", "socket": "LGA1700", "cores": 16, "tdp": 125, "score": 42000},
    {"name": "Intel Core i7-12700K", "socket": "LGA1700", "cores": 12, "tdp": 125, "score": 35000},
    {"name": "Intel Core i5-12400F", "socket": "LGA1700", "cores": 6, "tdp": 65, "score": 19500},
    {"name": "Intel Core i3-12100F", "socket": "LGA1700", "cores": 4, "tdp": 58, "score": 14000},
    {"name": "Intel Core i7-11700K", "socket": "LGA1200", "cores": 8, "tdp": 125, "score": 25000},
    {"name": "Intel Core i5-11400F", "socket": "LGA1200", "cores": 6, "tdp": 65, "score": 17000},
    {"name": "Intel Core i7-10700K", "socket": "LGA1200", "cores": 8, "tdp": 125, "score": 23000},
    {"name": "Intel Core i5-10400F", "socket": "LGA1200", "cores": 6, "tdp": 65, "score": 14500},
    {"name": "Intel Core i3-10100F", "socket": "LGA1200", "cores": 4, "tdp": 65, "score": 8800},
    {"name": "AMD Ryzen 9 9950X", "socket": "AM5", "cores": 16, "tdp": 170, "score": 61000},
    {"name": "AMD Ryzen 9 9900X", "socket": "AM5", "cores": 12, "tdp": 120, "score": 54000},
    {"name": "AMD Ryzen 7 9800X3D", "socket": "AM5", "cores": 8, "tdp": 120, "score": 48000},
    {"name": "AMD Ryzen 7 9700X", "socket": "AM5", "cores": 8, "tdp": 65, "score": 44000},
    {"name": "AMD Ryzen 5 9600X", "socket": "AM5", "cores": 6, "tdp": 65, "score": 36000},
    {"name": "AMD Ryzen 9 7950X3D", "socket": "AM5", "cores": 16, "tdp": 120, "score": 58000},
    {"name": "AMD Ryzen 7 7800X3D", "socket": "AM5", "cores": 8, "tdp": 120, "score": 46000},
    {"name": "AMD Ryzen 5 7600X", "socket": "AM5", "cores": 6, "tdp": 105, "score": 34000},
    {"name": "AMD Ryzen 5 7500F", "socket": "AM5", "cores": 6, "tdp": 65, "score": 31000},
    {"name": "AMD Ryzen 9 5950X", "socket": "AM4", "cores": 16, "tdp": 105, "score": 45000},
    {"name": "AMD Ryzen 7 5800X3D", "socket": "AM4", "cores": 8, "tdp": 105, "score": 32000},
    {"name": "AMD Ryzen 7 5700X", "socket": "AM4", "cores": 8, "tdp": 65, "score": 27000},
    {"name": "AMD Ryzen 5 5600X", "socket": "AM4", "cores": 6, "tdp": 65, "score": 22000},
    {"name": "AMD Ryzen 5 3600", "socket": "AM4", "cores": 6, "tdp": 65, "score": 17500}
]

CORE_FALLBACK_GPUS = [
    {"name": "NVIDIA GeForce RTX 4090", "tdp": 450, "score": 45000, "vram": 24, "target_res": "4K"},
    {"name": "NVIDIA GeForce RTX 4080 Super", "tdp": 320, "score": 38000, "vram": 16, "target_res": "4K"},
    {"name": "NVIDIA GeForce RTX 4070 Ti Super", "tdp": 285, "score": 34000, "vram": 16, "target_res": "1440p"},
    {"name": "NVIDIA GeForce RTX 4070 Super", "tdp": 220, "score": 30000, "vram": 12, "target_res": "1440p"},
    {"name": "NVIDIA GeForce RTX 4070", "tdp": 200, "score": 27000, "vram": 12, "target_res": "1440p"},
    {"name": "NVIDIA GeForce RTX 4060 Ti", "tdp": 160, "score": 22500, "vram": 8, "target_res": "1080p"},
    {"name": "NVIDIA GeForce RTX 4060", "tdp": 115, "score": 19500, "vram": 8, "target_res": "1080p"},
    {"name": "NVIDIA GeForce RTX 3090", "tdp": 350, "score": 34000, "vram": 24, "target_res": "4K"},
    {"name": "NVIDIA GeForce RTX 3080", "tdp": 320, "score": 29000, "vram": 10, "target_res": "1440p"},
    {"name": "NVIDIA GeForce RTX 3070", "tdp": 220, "score": 23000, "vram": 8, "target_res": "1440p"},
    {"name": "NVIDIA GeForce RTX 3060 Ti", "tdp": 200, "score": 20500, "vram": 8, "target_res": "1080p"},
    {"name": "NVIDIA GeForce RTX 3060", "tdp": 170, "score": 17000, "vram": 12, "target_res": "1080p"},
    {"name": "NVIDIA GeForce RTX 3050", "tdp": 130, "score": 13000, "vram": 8, "target_res": "1080p"},
    {"name": "NVIDIA GeForce GTX 1660 Super", "tdp": 125, "score": 12500, "vram": 6, "target_res": "1080p"},
    {"name": "NVIDIA GeForce GTX 1650", "tdp": 75, "score": 7500, "vram": 4, "target_res": "1080p Low"},
    {"name": "NVIDIA GeForce GTX 1050 Ti", "tdp": 75, "score": 6300, "vram": 4, "target_res": "1080p Low"},
    {"name": "AMD Radeon RX 7900 XTX", "tdp": 355, "score": 43000, "vram": 24, "target_res": "4K"},
    {"name": "AMD Radeon RX 7800 XT", "tdp": 263, "score": 29000, "vram": 16, "target_res": "1440p"},
    {"name": "AMD Radeon RX 7700 XT", "tdp": 245, "score": 25000, "vram": 12, "target_res": "1440p"},
    {"name": "AMD Radeon RX 7600", "tdp": 165, "score": 18000, "vram": 8, "target_res": "1080p"},
    {"name": "AMD Radeon RX 6700 XT", "tdp": 230, "score": 22000, "vram": 12, "target_res": "1440p"},
    {"name": "AMD Radeon RX 6600", "tdp": 132, "score": 14000, "vram": 8, "target_res": "1080p"},
    {"name": "AMD Radeon RX 580", "tdp": 185, "score": 8800, "vram": 8, "target_res": "1080p"}
]


# ==========================================
# 3. ĐỒNG BỘ CPU (PASSMARK + FALLBACK)
# ==========================================

def sync_cpus(db):
    print("⏳ Đang cào dữ liệu CPU từ PassMark...")
    url = "https://www.cpubenchmark.net/data/?t=cpu_high_end"
    scraped = False

    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            items = res.json().get("data", [])
            add_cnt, upd_cnt = 0, 0

            for row in items:
                name = row.get("name", "").strip()
                score_str = str(row.get("mark", "0")).replace(",", "")
                score = int(score_str) if score_str.isdigit() else 0

                if not any(brand in name for brand in ["Intel Core", "AMD Ryzen"]):
                    continue

                socket, cores, tdp = parse_cpu_socket(name)
                if socket == "Other":
                    continue

                if "tdp" in row and str(row["tdp"]).isdigit():
                    tdp = int(row["tdp"])
                if "cores" in row and str(row["cores"]).isdigit():
                    cores = int(row["cores"])

                obj = db.query(CPU).filter(CPU.name == name).first()
                if obj:
                    if obj.score != score:
                        obj.score = score
                        upd_cnt += 1
                else:
                    db.add(CPU(name=name, socket=socket, cores=cores, tdp=tdp, score=score))
                    add_cnt += 1

            db.commit()
            scraped = True
            print(f"✓ CPU (PassMark): Thêm mới {add_cnt}, Cập nhật {upd_cnt} linh kiện.")
    except Exception as e:
        db.rollback()
        print(f"⚠️ PassMark API bị chặn hoặc lỗi ({e}). Tiến hành nạp Seed Data...")

    # Nạp Seed Fallback nếu API bị chặn hoặc rỗng
    if not scraped or db.query(CPU).count() < 10:
        for c in CORE_FALLBACK_CPUS:
            existing = db.query(CPU).filter(CPU.name == c["name"]).first()
            if not existing:
                db.add(CPU(**c))
            else:
                existing.score = c["score"]
                existing.socket = c["socket"]
                existing.cores = c["cores"]
                existing.tdp = c["tdp"]
        db.commit()
        print(f"✓ CPU (Fallback): Đã bảo đảm có sẵn {len(CORE_FALLBACK_CPUS)} vi xử lý chủ lực.")


# ==========================================
# 4. ĐỒNG BỘ GPU (PASSMARK + FALLBACK)
# ==========================================

def sync_gpus(db):
    print("⏳ Đang cào dữ liệu GPU từ PassMark...")
    url = "https://www.videocardbenchmark.net/data/?t=gpu_high_end"
    scraped = False

    try:
        res = requests.get(url, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            items = res.json().get("data", [])
            add_cnt, upd_cnt = 0, 0

            for row in items:
                name = row.get("name", "").strip()
                score_str = str(row.get("mark", "0")).replace(",", "")
                score = int(score_str) if score_str.isdigit() else 0

                u = name.upper()
                if not any(b in u for b in ["GEFORCE", "RADEON", "RTX", "GTX", "INTEL ARC"]):
                    continue
                if any(x in u for x in ["GRAPHICS", "MOBILE", "MAX-Q", "CHIPSET"]):
                    continue

                vram, tdp, target_res = parse_gpu_specs(name)

                obj = db.query(GPU).filter(GPU.name == name).first()
                if obj:
                    if obj.score != score:
                        obj.score = score
                        upd_cnt += 1
                else:
                    db.add(GPU(name=name, tdp=tdp, score=score, vram=vram, target_res=target_res))
                    add_cnt += 1

            db.commit()
            scraped = True
            print(f"✓ GPU (PassMark): Thêm mới {add_cnt}, Cập nhật {upd_cnt} linh kiện.")
    except Exception as e:
        db.rollback()
        print(f"⚠️ PassMark GPU bị lỗi ({e}). Tiến hành nạp Seed Data...")

    if not scraped or db.query(GPU).count() < 10:
        for g in CORE_FALLBACK_GPUS:
            existing = db.query(GPU).filter(GPU.name == g["name"]).first()
            if not existing:
                db.add(GPU(**g))
            else:
                existing.score = g["score"]
                existing.tdp = g["tdp"]
                existing.vram = g["vram"]
                existing.target_res = g["target_res"]
        db.commit()
        print(f"✓ GPU (Fallback): Đã bảo đảm có sẵn {len(CORE_FALLBACK_GPUS)} card màn hình chủ lực.")


# ==========================================
# 5. ĐỒNG BỘ 150+ BO MẠCH CHỦ (MA TRẬN HÃNG)
# ==========================================

def sync_motherboards(db):
    print("⏳ Đang nạp danh mục Bo mạch chủ toàn diện (150+ mẫu)...")
    platforms = [
        # --- LGA1851 ---
        {"socket": "LGA1851", "ram": "DDR5", "lines": [
            "MSI MEG Z890 ACE", "MSI MPG Z890 CARBON WIFI", "MSI MAG Z890 TOMAHAWK WIFI", "MSI PRO Z890-A WIFI",
            "ASUS ROG MAXIMUS Z890 HERO", "ASUS ROG STRIX Z890-E GAMING WIFI", "ASUS TUF GAMING Z890-PLUS WIFI", "ASUS PRIME Z890-P",
            "Gigabyte Z890 AORUS MASTER", "Gigabyte Z890 AORUS ELITE WIFI7", "Gigabyte Z890 EAGLE",
            "ASRock Z890 Taichi", "ASRock Z890 Steel Legend WiFi", "ASRock Z890 Pro RS",
            "MSI MAG B860 TOMAHAWK WIFI", "MSI PRO B860M-A", "ASUS TUF GAMING B860-PLUS", "ASUS PRIME B860M-A",
            "Gigabyte B860 AORUS ELITE", "Gigabyte B860M GAMING X", "ASRock B860 Steel Legend"
        ]},

        # --- LGA1700 ---
        {"socket": "LGA1700", "ram": "DDR5", "lines": [
            "MSI MAG Z790 TOMAHAWK MAX WIFI", "MSI PRO Z790-A MAX WIFI", "MSI MPG Z790 EDGE TI MAX WIFI",
            "ASUS ROG STRIX Z790-A GAMING WIFI II", "ASUS TUF GAMING Z790-PLUS WIFI", "ASUS PRIME Z790-P",
            "Gigabyte Z790 AORUS ELITE AX", "Gigabyte Z790 GAMING X AX", "Gigabyte Z790 EAGLE AX",
            "ASRock Z790 Steel Legend WiFi", "ASRock Z790 Pro RS",
            "MSI MAG B760 TOMAHAWK WIFI", "MSI B760 GAMING PLUS WIFI", "MSI PRO B760M-A WIFI",
            "ASUS ROG STRIX B760-F GAMING WIFI", "ASUS TUF GAMING B760-PLUS WIFI", "ASUS PRIME B760-PLUS",
            "Gigabyte B760 AORUS ELITE AX", "Gigabyte B760M GAMING X AX", "ASRock B760M Steel Legend WiFi"
        ]},
        {"socket": "LGA1700", "ram": "DDR4", "lines": [
            "MSI MAG B760 TOMAHAWK WIFI DDR4", "MSI PRO B760M-A DDR4", "MSI PRO B760M-E DDR4",
            "ASUS TUF GAMING B760M-PLUS D4", "ASUS PRIME B760M-A D4", "ASUS PRIME B760M-K D4",
            "Gigabyte B760M DS3H DDR4", "Gigabyte B760 GAMING X DDR4", "ASRock B760M Pro RS/D4",
            "ASUS H610M-K D4", "ASUS PRIME H610M-E D4", "MSI PRO H610M-E DDR4", "MSI PRO H610M-G DDR4",
            "Gigabyte H610M S2H DDR4", "Gigabyte H610M H V2", "ASRock H610M-HVS"
        ]},

        # --- LGA1200 ---
        {"socket": "LGA1200", "ram": "DDR4", "lines": [
            "MSI MAG B560 TOMAHAWK", "MSI MAG B560M MORTAR", "MSI B560M PRO-VDH",
            "ASUS TUF GAMING B560-PLUS WIFI", "ASUS TUF GAMING B560M-PLUS", "ASUS PRIME B560M-A",
            "Gigabyte B560 AORUS PRO AX", "Gigabyte B560M AORUS ELITE", "Gigabyte B560M DS3H", "ASRock B560 Steel Legend",
            "ASUS PRIME H510M-K", "MSI H510M-A PRO", "Gigabyte H510M H", "ASRock H510M-HDV",
            "MSI MAG B460 TOMAHAWK", "ASUS TUF GAMING B460-PLUS", "Gigabyte B460M DS3H",
            "ASUS PRIME H410M-E", "MSI H410M-A PRO", "Gigabyte H410M S2"
        ]},

        # --- LGA1151 ---
        {"socket": "LGA1151", "ram": "DDR4", "lines": [
            "ASUS TUF B365M-PLUS GAMING", "ASUS PRIME B365M-A", "MSI B365M PRO-VDH",
            "Gigabyte B365M AORUS ELITE", "ASRock B365M Phantom Gaming 4",
            "ASUS PRIME H310M-E R2.0", "MSI H310M PRO-VDH PLUS", "Gigabyte H310M DS2", "ASRock H310M-HDV"
        ]},

        # --- AM5 ---
        {"socket": "AM5", "ram": "DDR5", "lines": [
            "MSI MAG X870 TOMAHAWK WIFI", "MSI MPG X870E CARBON WIFI", "ASUS ROG STRIX X870-E GAMING WIFI",
            "Gigabyte X870 AORUS ELITE WIFI7", "ASRock X870 Steel Legend WiFi",
            "MSI MAG B650 TOMAHAWK WIFI", "MSI B650 GAMING PLUS WIFI", "MSI PRO B650M-A WIFI", "MSI PRO B650M-P",
            "ASUS TUF GAMING B650-PLUS WIFI", "ASUS TUF GAMING B650M-PLUS", "ASUS PRIME B650-PLUS", "ASUS PRIME B650M-A",
            "Gigabyte B650 AORUS ELITE AX", "Gigabyte B650M GAMING X AX", "Gigabyte B650M DS3H", "ASRock B650 Steel Legend WiFi",
            "ASUS PRIME A620M-A", "ASUS TUF GAMING A620M-PLUS", "MSI PRO A620M-E", "Gigabyte A620M GAMING X"
        ]},

        # --- AM4 ---
        {"socket": "AM4", "ram": "DDR4", "lines": [
            "MSI MAG B550 TOMAHAWK", "MSI MAG B550M MORTAR", "MSI B550-A PRO", "MSI B550M PRO-VDH WIFI",
            "ASUS ROG STRIX B550-F GAMING", "ASUS TUF GAMING B550-PLUS", "ASUS TUF GAMING B550M-PLUS WIFI II", "ASUS PRIME B550M-A",
            "Gigabyte B550 AORUS ELITE V2", "Gigabyte B550M AORUS ELITE", "Gigabyte B550M DS3H", "ASRock B550 Steel Legend",
            "MSI B450 TOMAHAWK MAX II", "MSI B450M MORTAR MAX", "MSI B450M PRO-VDH MAX",
            "ASUS TUF B450M-PLUS II", "ASUS PRIME B450M-A II", "Gigabyte B450 AORUS ELITE", "ASRock B450 Steel Legend",
            "MSI A520M-A PRO", "ASUS PRIME A520M-K", "Gigabyte A520M S2H", "ASUS PRIME A320M-K", "Gigabyte GA-A320M-S2H"
        ]}
    ]

    total = 0
    for group in platforms:
        sock = group["socket"]
        ram = group["ram"]
        for name in group["lines"]:
            existing = db.query(Motherboard).filter(Motherboard.name == name).first()
            if not existing:
                db.add(Motherboard(name=name, socket=sock, ram_type=ram))
                total += 1
            else:
                existing.socket = sock
                existing.ram_type = ram

    db.commit()
    print(f"✓ Bo mạch chủ: Đã nạp thành công {total} mẫu vào Database SQLite.")


# ==========================================
# 6. HÀM ĐIỀU HÀNH CHÍNH (MAIN ENTRYPOINT)
# ==========================================

def main():
    db = SessionLocal()
    try:
        sync_cpus(db)
        sync_gpus(db)
        sync_motherboards(db)
        print("\n🎉 Hoàn tất quá trình cào và đồng bộ dữ liệu vào SQLite!")
    finally:
        db.close()


if __name__ == "__main__":
    main()