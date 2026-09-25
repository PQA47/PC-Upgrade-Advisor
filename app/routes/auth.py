import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database.database import SessionLocal
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.services.auth import hash_password, verify_password
from app.services.email import send_password_reset_email

router = APIRouter()


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"error": None},
    )


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
):
    db = SessionLocal()
    try:
        username = username.strip()
        email = email.strip().lower()

        if len(username) < 3:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="register.html",
                context={"error": "Username must be at least 3 characters."},
                status_code=400,
            )

        if len(password) < 8:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="register.html",
                context={"error": "Password must be at least 8 characters."},
                status_code=400,
            )

        existing = (
            db.query(User)
            .filter((User.username == username) | (User.email == email))
            .first()
        )
        if existing:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="register.html",
                context={"error": "Username or email already exists."},
                status_code=400,
            )

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        request.session["user_id"] = user.id
        request.session["username"] = user.username
        return RedirectResponse("/", status_code=303)
    finally:
        db.close()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None},
    )


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username.strip()).first()

        if not user or not verify_password(password, user.password_hash):
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Invalid username or password."},
                status_code=401,
            )

        request.session["user_id"] = user.id
        request.session["username"] = user.username
        return RedirectResponse("/", status_code=303)
    finally:
        db.close()


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={"message": None, "error": None},
    )


@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
):
    db = SessionLocal()
    try:
        email = email.strip().lower()
        message = (
            "If an account with that email exists, a password reset link has been sent."
        )

        user = db.query(User).filter(User.email == email).first()
        if not user:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="forgot_password.html",
                context={"message": message, "error": None},
            )

        # Invalidate previous unused tokens for this account.
        now = utc_now()
        old_tokens = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .all()
        )
        for old_token in old_tokens:
            old_token.used_at = now

        raw_token = secrets.token_urlsafe(32)
        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=now + timedelta(minutes=30),
        )
        db.add(reset_record)
        db.commit()

        base_url = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        reset_url = f"{base_url}/reset-password?token={raw_token}"

        background_tasks.add_task(
            send_password_reset_email,
            user.email,
            reset_url,
        )

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="forgot_password.html",
            context={"message": message, "error": None},
        )
    finally:
        db.close()


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str):
    db = SessionLocal()
    try:
        record = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == hash_reset_token(token),
                PasswordResetToken.used_at.is_(None),
            )
            .first()
        )
        if not record or record.expires_at <= utc_now():
            return HTMLResponse("<h2>Invalid or expired reset link.</h2>", status_code=400)

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="reset_password.html",
            context={"token": token, "error": None},
        )
    finally:
        db.close()


@router.post("/reset-password", response_class=HTMLResponse)
def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    db = SessionLocal()
    try:
        context = {"token": token, "error": None}

        if len(password) < 8:
            context["error"] = "Password must be at least 8 characters."
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="reset_password.html",
                context=context,
                status_code=400,
            )

        if password != password_confirm:
            context["error"] = "Passwords do not match."
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="reset_password.html",
                context=context,
                status_code=400,
            )

        record = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == hash_reset_token(token),
                PasswordResetToken.used_at.is_(None),
            )
            .first()
        )
        if not record or record.expires_at <= utc_now():
            return HTMLResponse("<h2>Invalid or expired reset link.</h2>", status_code=400)

        user = db.query(User).filter(User.id == record.user_id).first()
        if not user:
            return HTMLResponse("<h2>User not found.</h2>", status_code=404)

        user.password_hash = hash_password(password)
        record.used_at = utc_now()
        db.commit()

        request.session.clear()
        request.session["user_id"] = user.id
        request.session["username"] = user.username

        return RedirectResponse("/", status_code=303)
    finally:
        db.close()
