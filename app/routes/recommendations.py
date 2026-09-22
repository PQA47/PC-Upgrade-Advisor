import sys
import subprocess
from pathlib import Path

from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse

from app.database.database import SessionLocal

try:
    from app.models.component import CPU, GPU, Motherboard
except ImportError:
    from app.models.components import CPU, GPU, Motherboard

from app.services.compatibility import check_compatibility
from app.services.analyzer import decide_upgrade
from app.services.recommender import get_recommendations


router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCRAPER_SCRIPT = BASE_DIR / "scripts" / "scraper.py"


def run_background_scraper():
    """Run the scraper in a background child process."""
    try:
        subprocess.run(
            [sys.executable, str(SCRAPER_SCRIPT)],
            check=True,
        )
        print("✓ Background scraper sync completed!")
    except Exception as e:
        print(f"❌ Error while running the background scraper: {e}")


@router.get("/api/sync-data")
def trigger_sync(background_tasks: BackgroundTasks):
    """Trigger the scraper to run in the background."""
    background_tasks.add_task(run_background_scraper)

    return {
        "status": "success",
        "message": (
            "The system is syncing hardware data in the background. "
            "Please refresh the page after the sync finishes."
        ),
    }


@router.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    cpu_name: str = Form(...),
    gpu_name: str = Form(...),
    mb_name: str = Form(...),
    ram_gb: int = Form(...),
    storage_type: str = Form(...),
    resolution: str = Form(...),
    usage: str = Form(...),
    psu_watt: int = Form(...),
    budget: float = Form(...),
):
    db = SessionLocal()

    try:
        clean_cpu = cpu_name.strip()
        clean_gpu = gpu_name.strip()
        clean_mb = mb_name.strip()

        # ---------------------------------------------------------
        # 1. FIND COMPONENTS
        # ---------------------------------------------------------
        cpu_obj = (
            db.query(CPU)
            .filter(CPU.name == clean_cpu)
            .first()
        )
        if not cpu_obj:
            cpu_obj = (
                db.query(CPU)
                .filter(CPU.name.ilike(f"%{clean_cpu}%"))
                .first()
            )

        gpu_obj = (
            db.query(GPU)
            .filter(GPU.name == clean_gpu)
            .first()
        )
        if not gpu_obj:
            gpu_obj = (
                db.query(GPU)
                .filter(GPU.name.ilike(f"%{clean_gpu}%"))
                .first()
            )

        mb_obj = (
            db.query(Motherboard)
            .filter(Motherboard.name == clean_mb)
            .first()
        )
        if not mb_obj:
            mb_obj = (
                db.query(Motherboard)
                .filter(Motherboard.name.ilike(f"%{clean_mb}%"))
                .first()
            )

        # ---------------------------------------------------------
        # 2. HANDLE MISSING COMPONENTS
        # ---------------------------------------------------------
        missing = []

        if not cpu_obj:
            missing.append(f"CPU: '{cpu_name}'")

        if not gpu_obj:
            missing.append(f"GPU: '{gpu_name}'")

        if not mb_obj:
            missing.append(f"Motherboard: '{mb_name}'")

        if missing:
            items = "".join(
                f"<li><strong>{item}</strong></li>"
                for item in missing
            )

            err_html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Components not found</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-slate-950 text-slate-100 min-h-screen p-8">
                <div class="max-w-xl mx-auto mt-16 bg-slate-900
                            border border-rose-500/40 rounded-2xl p-8">
                    <h1 class="text-2xl font-black text-rose-400">
                        ⚠️ Components not found
                    </h1>

                    <p class="text-slate-300 mt-3">
                        The system could not find these components in the database:
                    </p>

                    <ul class="list-disc ml-6 mt-4 text-rose-300 space-y-1">
                        {items}
                    </ul>

                    <a href="/"
                       class="inline-block mt-6 bg-cyan-600 hover:bg-cyan-500
                              px-5 py-3 rounded-xl font-bold">
                        ← Try again
                    </a>
                </div>
            </body>
            </html>
            """

            return HTMLResponse(err_html, status_code=400)

        # ---------------------------------------------------------
        # 3. CONVERT ORM OBJECTS TO DICTS
        # ---------------------------------------------------------
        cpu_dict = {
            "name": cpu_obj.name,
            "socket": cpu_obj.socket,
            "tdp": cpu_obj.tdp or 0,
            "score": cpu_obj.score or 0,
            "cores": cpu_obj.cores or 0,
        }

        gpu_dict = {
            "name": gpu_obj.name,
            "tdp": gpu_obj.tdp or 0,
            "score": gpu_obj.score or 0,
            "vram": gpu_obj.vram or 0,
            "target_res": gpu_obj.target_res,
        }

        mb_dict = {
            "name": mb_obj.name,
            "socket": mb_obj.socket,
            "ram_type": mb_obj.ram_type,
        }

        # ---------------------------------------------------------
        # 4. COMPATIBILITY
        # ---------------------------------------------------------
        compat = check_compatibility(
            cpu=cpu_dict,
            motherboard=mb_dict,
            gpu=gpu_dict,
            psu_wattage=psu_watt,
        )

        # ---------------------------------------------------------
        # 5. PERFORMANCE / BOTTLENECK ANALYSIS
        # ---------------------------------------------------------
        decision = decide_upgrade(
            cpu=cpu_dict,
            gpu=gpu_dict,
            ram_gb=ram_gb,
            storage_type=storage_type,
            resolution=resolution,
            usage=usage,
        )

        # ---------------------------------------------------------
        # 6. RECOMMENDATIONS
        #
        # IMPORTANT:
        # Socket mismatch blocks upgrade analysis.
        # PSU weakness only creates a warning, so the user can still
        # see possible upgrades and which PSU they need.
        # ---------------------------------------------------------
        if compat["hardware_compatible"]:
            recomms = get_recommendations(
                db=db,
                cpu_model=CPU,
                gpu_model=GPU,
                current_cpu=cpu_dict,
                current_gpu=gpu_dict,
                current_mb=mb_dict,
                psu_watt=psu_watt,
                ram_gb=ram_gb,
                storage_type=storage_type,
                resolution=resolution,
                usage=usage,
                decision=decision,
                budget=budget,
            )
        else:
            recomms = {
                "cpu_upgrades": [],
                "gpu_upgrades": [],
                "ram_recommendation": None,
                "storage_recommendation": None,
            }

        # ---------------------------------------------------------
        # 7. RENDER
        # ---------------------------------------------------------
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="results.html",
            context={
                "cpu": cpu_dict,
                "gpu": gpu_dict,
                "mb": mb_dict,
                "ram_gb": ram_gb,
                "storage_type": storage_type,
                "resolution": resolution,
                "usage": usage,
                "psu_watt": psu_watt,
                "budget": budget,
                "compat": compat,
                "decision": decision,
                "recomms": recomms,
            },
        )

    finally:
        db.close()
