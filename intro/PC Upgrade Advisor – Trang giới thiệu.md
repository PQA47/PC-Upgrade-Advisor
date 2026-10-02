# PC Upgrade Advisor

## Overview
PC Upgrade Advisor helps users understand their PC configuration, identify potential CPU/GPU bottlenecks, check component compatibility, and explore upgrade recommendations based on workload and budget.

## Main features
- CPU and GPU benchmark-based bottleneck analysis.
- CPU–motherboard socket compatibility checks and estimated PSU requirements.
- Recommendations for gaming, content creation, programming, and AI workloads.
- Budget-aware component suggestions with available retail price references in VND.
- User accounts, saved analysis history, and email-based password recovery.

## Workflow
1. **Enter your configuration:** CPU, GPU, motherboard, RAM, storage, PSU wattage, resolution, workload, and budget.
2. **Analyze:** review compatibility, estimated power needs, and benchmark comparisons.
3. **Review recommendations:** explore suggested components, estimated performance changes, and available price references.

## Technology
Python 3.11, FastAPI, SQLAlchemy, SQLite, Jinja2, Tailwind CSS, APScheduler, and Argon2.

Hardware data is collected by a scraper and refreshed every seven days while the application scheduler is running. Benchmark coverage is still being expanded, so recommendations should be treated as guidance rather than a guarantee.

## Run locally on Windows
```powershell
git clone https://github.com/PQA47/PC-Upgrade-Advisor.git
cd PC-Upgrade-Advisor
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
py scripts\scraper.py
py -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000. Configure SMTP settings in `.env` to test password recovery.

Source code: https://github.com/PQA47/PC-Upgrade-Advisor
