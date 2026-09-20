Mở **PowerShell** tại thư mục dự án và dán toàn bộ khối lệnh dưới đây để hệ thống tự động thiết lập môi trường, cài đặt thư viện, nạp cơ sở dữ liệu và bật server:

```powershell```
Cấp quyền thực thi script cho PowerShell (nếu bị chặn):
Set-ExecutionPolicy Unrestricted -Scope Process -Force

Tạo môi trường ảo:
python -m venv venv

Kích hoạt môi trường ảo:
.\venv\Scripts\Activate.ps1

Cài đặt các thư viện cần thiết:
pip install -r requirements.txt

Nạp dữ liệu linh kiện vào SQLite (nếu muốn cập nhật db mới nhất):
python scripts/scraper.py

Khởi động máy chủ Web:
python -m uvicorn app.main:app --reload
