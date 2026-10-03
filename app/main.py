from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import os
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

load_dotenv()

from app.database.database import engine, Base, SessionLocal, ensure_schema_columns

# Support both component.py and components.py filenames automatically
try:
    from app.models.component import CPU, GPU, Motherboard
except ImportError:
    from app.models.components import CPU, GPU, Motherboard

from app.routes import recommendations, auth, history
from app.routes.recommendations import run_background_scraper
from app.models.user import User
from app.models.analysis import Analysis
from app.models.password_reset import PasswordResetToken

# Migrate existing SQLite tables before SQLAlchemy issues queries.
ensure_schema_columns()
Base.metadata.create_all(bind=engine)

# Initialize the background scheduler
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Start the automatic data sync job every 7 days
    scheduler.add_job(
        run_background_scraper,
        trigger="interval",
        days=7,
        id="auto_hardware_sync",
        replace_existing=True
    )
    scheduler.start()
    print("🚀 [Scheduler] Enabled automatic hardware data synchronization every 7 days")

    yield

    # 2. Shut down the scheduler safely when the server stops
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("🛑 [Scheduler] Scheduler has been stopped.")


app = FastAPI(
    title="PC Upgrade Advisor",
    description="A tool for analyzing PC configurations and providing upgrade recommendations.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-only-change-this"),
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=False,
)

# Configure template path
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

# Register the analysis and synchronization routes
app.include_router(recommendations.router)
app.include_router(auth.router)
app.include_router(history.router)


@app.get("/")
def landing(request: Request):
    """Public landing page introducing PC Upgrade Advisor."""
    return templates.TemplateResponse(
        request=request,
        name="landing.html",
        context={"request": request}
    )


@app.get("/devices")
def device_selection(request: Request):
    """Device selection page for future advisor modules."""
    return templates.TemplateResponse(
        request=request,
        name="device_selection.html",
        context={"request": request}
    )

@app.get("/select-platform")
def select_platform(request: Request):
    """Let the user choose Intel or AMD before entering the PC configuration form."""
    return templates.TemplateResponse(
        request=request,
        name="platform_selection.html",
        context={"request": request}
    )


@app.get("/pc-upgrade")
def pc_upgrade(request: Request, platform: str = Query("intel")):
    """Render the PC form with CPU/motherboard data pre-filtered by platform."""
    platform = (platform or "intel").lower().strip()
    if platform not in {"intel", "amd"}:
        platform = "intel"

    db = SessionLocal()
    try:
        if platform == "intel":
            # Intel desktop sockets currently represented in the database.
            cpus = (
                db.query(CPU)
                .filter(CPU.socket.like("LGA%"))
                .order_by(CPU.score.desc())
                .all()
            )
            mbs = (
                db.query(Motherboard)
                .filter(Motherboard.socket.like("LGA%"))
                .order_by(Motherboard.name.asc())
                .all()
            )
        else:
            cpus = (
                db.query(CPU)
                .filter(CPU.socket.like("AM%"))
                .order_by(CPU.score.desc())
                .all()
            )
            mbs = (
                db.query(Motherboard)
                .filter(Motherboard.socket.like("AM%"))
                .order_by(Motherboard.name.asc())
                .all()
            )

        gpus = db.query(GPU).order_by(GPU.score.desc()).all()

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "cpus": cpus,
                "gpus": gpus,
                "motherboards": mbs,
                "platform": platform
            }
        )
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)