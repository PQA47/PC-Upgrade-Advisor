from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.background import BackgroundScheduler

from app.database.database import engine, Base, SessionLocal

# Support both component.py and components.py filenames automatically
try:
    from app.models.component import CPU, GPU, Motherboard
except ImportError:
    from app.models.components import CPU, GPU, Motherboard

from app.routes import recommendations
from app.routes.recommendations import run_background_scraper

# Create SQLite tables if they do not already exist
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

# Configure template path
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

# Register the analysis and synchronization routes
app.include_router(recommendations.router)


@app.get("/")
def index(request: Request):
    """Home page: load all components from SQLite and render them into the search form."""
    db = SessionLocal()
    try:
        cpus = db.query(CPU).order_by(CPU.score.desc()).all()
        gpus = db.query(GPU).order_by(GPU.score.desc()).all()
        mbs = db.query(Motherboard).order_by(Motherboard.name.asc()).all()

        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "cpus": cpus,
                "gpus": gpus,
                "motherboards": mbs
            }
        )
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)