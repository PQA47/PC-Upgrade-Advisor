from fastapi import APIRouter, Request
import json

from fastapi.responses import RedirectResponse, HTMLResponse

from app.database.database import SessionLocal
from app.models.analysis import Analysis

router = APIRouter()


@router.get("/history")
def history(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    try:
        analyses = (
            db.query(Analysis)
            .filter(Analysis.user_id == user_id)
            .order_by(Analysis.created_at.desc())
            .all()
        )
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="history.html",
            context={"analyses": analyses},
        )
    finally:
        db.close()


@router.get("/history/{analysis_id}", response_class=HTMLResponse)
def view_analysis(analysis_id: int, request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    try:
        analysis = (
            db.query(Analysis)
            .filter(Analysis.id == analysis_id, Analysis.user_id == user_id)
            .first()
        )
        if not analysis:
            return RedirectResponse("/history", status_code=303)

        if not analysis.result_json:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="history_detail_missing.html",
                context={"analysis": analysis},
                status_code=404,
            )

        context = json.loads(analysis.result_json)
        context["history_item"] = analysis
        context["from_history"] = True

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="results.html",
            context=context,
        )
    except (json.JSONDecodeError, TypeError, ValueError):
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="history_detail_missing.html",
            context={"analysis": analysis},
            status_code=500,
        )
    finally:
        db.close()


@router.post("/history/delete/{analysis_id}")
def delete_analysis(analysis_id: int, request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    db = SessionLocal()
    try:
        analysis = (
            db.query(Analysis)
            .filter(Analysis.id == analysis_id, Analysis.user_id == user_id)
            .first()
        )
        if analysis:
            db.delete(analysis)
            db.commit()
        return RedirectResponse("/history", status_code=303)
    finally:
        db.close()
