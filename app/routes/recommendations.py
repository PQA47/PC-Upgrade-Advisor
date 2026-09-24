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
    """Function that runs the scraper script in a background child process."""
    try:
        subprocess.run([sys.executable, str(SCRAPER_SCRIPT)], check=True)
        print("✓ Background scraper sync completed!")
    except Exception as e:
        print(f"❌ Error while running the background scraper: {e}")


@router.get("/api/sync-data")
def trigger_sync(background_tasks: BackgroundTasks):
    """Trigger the scraper to run in the background."""
    background_tasks.add_task(run_background_scraper)
    return {
        "status": "success",
        "message": "The system is syncing hardware data from PassMark in the background. Please refresh the page in 30-60 seconds!"
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
    budget: float = Form(0)
):
    db = SessionLocal()
    try:
        clean_cpu = cpu_name.strip()
        clean_gpu = gpu_name.strip()
        clean_mb = mb_name.strip()

        # 1. Search CPU (Exact match -> fuzzy match)
        cpu_obj = db.query(CPU).filter(CPU.name == clean_cpu).first()
        if not cpu_obj:
            cpu_obj = db.query(CPU).filter(CPU.name.ilike(f"%{clean_cpu}%")).first()

        # 2. Search GPU
        gpu_obj = db.query(GPU).filter(GPU.name == clean_gpu).first()
        if not gpu_obj:
            gpu_obj = db.query(GPU).filter(GPU.name.ilike(f"%{clean_gpu}%")).first()

        # 3. Search motherboard
        mb_obj = db.query(Motherboard).filter(Motherboard.name == clean_mb).first()
        if not mb_obj:
            mb_obj = db.query(Motherboard).filter(Motherboard.name.ilike(f"%{clean_mb}%")).first()

        # Handle cases where the user enters a component name not in the database
        missing = []
        if not cpu_obj: missing.append(f"CPU: '{cpu_name}'")
        if not gpu_obj: missing.append(f"GPU: '{gpu_name}'")
        if not mb_obj: missing.append(f"Motherboard: '{mb_name}'")

        if missing:
            err_html = f"""
            <div style="background-color: #020617; color: #f87171; font-family: ui-sans-serif, system-ui; padding: 40px; min-height: 100vh;">
                <div style="max-width: 600px; margin: 0 auto; background: #0f172a; padding: 30px; border-radius: 16px; border: 1px solid #ef4444;">
                    <h2 style="margin-top: 0; color: #ef4444;">⚠️ Components not found</h2>
                    <p style="color: #cbd5e1;">The system could not find the following components in the database:</p>
                    <ul style="color: #fca5a5;">
                        {''.join(f'<li><strong>{m}</strong></li>' for m in missing)}
                    </ul>
                    <p style="font-size: 14px; color: #94a3b8;">Tip: Type a few characters and select the suggested option directly from the dropdown list.</p>
                    <a href="/" style="display: inline-block; margin-top: 15px; padding: 10px 20px; background: #0284c7; color: white; text-decoration: none; border-radius: 8px; font-weight: bold;">← Try again</a>
                </div>
            </div>
            """
            return HTMLResponse(err_html, status_code=400)

        # Convert ORM objects to dicts compatible with the service layer
        cpu_dict = {
            "name": cpu_obj.name,
            "socket": cpu_obj.socket,
            "tdp": cpu_obj.tdp,
            "score": cpu_obj.score,
            "cores": cpu_obj.cores,
            "price": getattr(cpu_obj, "price", 0.0)
        }
        gpu_dict = {
            "name": gpu_obj.name,
            "tdp": gpu_obj.tdp,
            "score": gpu_obj.score,
            "vram": gpu_obj.vram,
            "target_res": gpu_obj.target_res,
            "price": getattr(gpu_obj, "price", 0.0)
        }
        mb_dict = {
            "name": mb_obj.name,
            "socket": mb_obj.socket,
            "ram_type": mb_obj.ram_type
        }

        # 4. Check physical socket compatibility and power requirements
        compat = check_compatibility(cpu_dict, mb_dict, gpu_dict, psu_watt)

        # 5. Analyze bottlenecks and decide whether an upgrade is needed for the task
        decision = decide_upgrade(
            cpu=cpu_dict,
            gpu=gpu_dict,
            ram_gb=ram_gb,
            storage_type=storage_type,
            resolution=resolution,
            usage=usage
        )

        # 6. Generate specific upgrade suggestions (keep the same socket, upgrade GPU based on PSU, etc.)
        if compat.get("hardware_compatible", compat["is_compatible"]):
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
                budget=budget
            )
        else:
            recomms = {
                "cpu_upgrades": [],
                "gpu_upgrades": [],
                "ram_recommendation": None,
                "storage_recommendation": None
            }

        # 7. Render results via Jinja2 template
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
                "compat": compat,
                "decision": decision,
                "recomms": recomms,
                "budget": budget
            }
        )
    finally:
        db.close()