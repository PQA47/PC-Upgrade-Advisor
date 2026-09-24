from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database.database import SessionLocal
from app.models.user import User
from app.services.auth import hash_password, verify_password

router = APIRouter()


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
