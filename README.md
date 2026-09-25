## Environment Configuration

The application uses environment variables for sensitive configuration such as SMTP credentials and the session secret.

### 1. Create the environment file

After cloning the repository, create a `.env` file from the provided template:

```powershell
copy .env.example .env
```

Then open the file:

```powershell
notepad .env
```

### 2. Configure `.env`

Fill in the following values:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM=your-email@gmail.com

APP_BASE_URL=http://127.0.0.1:8000

SESSION_SECRET=generate-your-own-random-secret
```

#### SMTP settings

- `SMTP_HOST`: Gmail SMTP server. Keep it as `smtp.gmail.com`.
- `SMTP_PORT`: Gmail SMTP port. Keep it as `587`.
- `SMTP_USERNAME`: The Gmail account used to send password reset emails.
- `SMTP_PASSWORD`: A **Google App Password**, not your normal Gmail password.
- `SMTP_FROM`: The sender email address. Normally this should be the same Gmail account as `SMTP_USERNAME`.

To use Gmail App Passwords, enable **2-Step Verification** on your Google account and create an App Password for the application.

#### Session secret

`SESSION_SECRET` is used to protect user sessions. Generate a random value with:

```powershell
py -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the generated value into:

```env
SESSION_SECRET=your-generated-secret
```

#### Application URL

For local development:

```env
APP_BASE_URL=http://127.0.0.1:8000
```

When deploying the application, replace this with the actual application URL.

### 3. Install dependencies

```powershell
py -m pip install -r requirements.txt
```

### 4. Run the application

```powershell
py -m uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

### 5. Password recovery

The application supports password recovery through email:

```text
Login
  ↓
Forgot password?
  ↓
Enter email
  ↓
Password reset email
  ↓
Reset link
  ↓
Set a new password
```

Reset links are temporary and can only be used once.

### Security

Do **not** commit `.env` to GitHub because it contains sensitive credentials.

The repository should contain:

```text
.env.example    ✅ Commit this file
.env            ❌ Do not commit this file
```

The `.gitignore` file should contain:

```gitignore
.env
```

Other developers can create their own configuration with:

```powershell
copy .env.example .env
```

and then provide their own Gmail credentials and `SESSION_SECRET`.

Never publish a real Gmail App Password, session secret, API key, or other credentials in the repository.
