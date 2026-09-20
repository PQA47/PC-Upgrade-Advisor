Mở **PowerShell** tại thư mục dự án và dán toàn bộ khối lệnh dưới đây để hệ thống tự động thiết lập môi trường, cài đặt thư viện, nạp cơ sở dữ liệu và bật server:

```powershell```

Set-ExecutionPolicy Unrestricted -Scope Process -Force
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/scraper.py
python -m uvicorn app.main:app --reload
