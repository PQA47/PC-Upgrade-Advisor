## Installation & Setup

### 1. Clone the repository

```powershell
git clone https://github.com/PQA47/PC_UPGRADE.git
cd PC_UPGRADE
```

If you are using a different branch:

```powershell
git switch <branch-name>
```

---

### 2. Install Python dependencies

Make sure Python 3.11+ is installed.

Install all required dependencies:

```powershell
py -m pip install -r requirements.txt
```

If you are using a virtual environment, create and activate it first:

```powershell
py -m venv .venv
.venv\Scripts\activate
```

Then install dependencies:

```powershell
pip install -r requirements.txt
```

---

### 3. Configure environment variables

The application uses environment variables for sensitive configuration such as SMTP credentials and the session secret.

Create a `.env` file from the provided template:

```powershell
copy .env.example .env
```

Then open it:

```powershell
notepad .env
```

Configure:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM=your-email@gmail.com

APP_BASE_URL=http://127.0.0.1:8000

SESSION_SECRET=generate-your-own-random-secret
```

#### SMTP configuration

- `SMTP_HOST`: Gmail SMTP server. Keep `smtp.gmail.com`.
- `SMTP_PORT`: Gmail SMTP port. Keep `587`.
- `SMTP_USERNAME`: Gmail account used to send password reset emails.
- `SMTP_PASSWORD`: Google App Password, **not** your normal Gmail password.
- `SMTP_FROM`: Email address shown as the sender.

For Gmail, enable **2-Step Verification** and create an **App Password** for this application.

#### Session secret

Generate a random session secret:

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

When deployed, replace this with the real application URL.

---

### 4. Keep `.env` private

Do **not** commit `.env` to GitHub.

The repository should contain:

```text
.env.example    ✅ Safe to commit
.env            ❌ Do not commit
```

Make sure `.gitignore` contains:

```gitignore
.env
__pycache__/
*.pyc
```

Other developers can create their own configuration with:

```powershell
copy .env.example .env
```

and then enter their own credentials.

---

## Data Synchronization

The project contains a hardware scraper that synchronizes CPU, GPU, motherboard, benchmark, and retail price data.

The scraper should be run before starting the web application when setting up the database for the first time or when you want to refresh hardware data.

### 5. Run the hardware scraper

From the project root:

```powershell
py scripts\scraper.py
```

The scraper will synchronize:

- CPU specifications and benchmark scores
- GPU specifications and benchmark scores
- Motherboard information
- Current retail prices from supported sources

A successful run should end with a message similar to:

```text
🎉 Hardware synchronization completed!
```

The scraper uses the project's SQLite database and updates existing records instead of requiring the database to be deleted.

---

## Run the Web Application

### 6. Start FastAPI

From the project root:

```powershell
py -m uvicorn app.main:app --reload
```

You should see:

```text
Uvicorn running on http://127.0.0.1:8000
```

Open the application in your browser:

```text
http://127.0.0.1:8000
```

---

## Application Features

The application currently includes:

- PC hardware configuration analysis
- CPU/GPU benchmark comparison
- Hardware compatibility checking
- Bottleneck analysis
- Upgrade recommendations
- Current retail price integration
- User registration and login
- Logout
- Analysis history
- Reopening previous analysis results
- Password recovery by email
- Password reset using temporary one-time tokens

### Password Recovery Flow

```text
Login
   ↓
Forgot password?
   ↓
Enter email
   ↓
Password reset email
   ↓
Open reset link
   ↓
Set new password
```

Password reset links are temporary and can only be used once.

---

## Development Workflow

A typical local development workflow is:

```powershell
# 1. Install dependencies
py -m pip install -r requirements.txt

# 2. Configure .env
copy .env.example .env

# 3. Update hardware and price data
py scripts\scraper.py

# 4. Start the web server
py -m uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

### Updating hardware data later

You can re-run:

```powershell
py scripts\scraper.py
```

The scraper will update the existing database with newly available benchmark and price information.

---

## Important Security Notes

Never commit sensitive information such as:

- Gmail App Passwords
- Session secrets
- API keys
- Database credentials
- Other private environment variables

Use `.env.example` for configuration templates and `.env` for local secrets.
