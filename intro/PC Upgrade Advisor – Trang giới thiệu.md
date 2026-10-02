**PC Upgrade Advisor**

[Cách hoạt động](#cach-hoat-dong)[Tính năng](#tinh-nang)[Chạy thử](#chay-thu)

# Máy của bạn đang chậm ở đâu, nâng cấp gì trước?

Nhập CPU, card đồ họa, mainboard và nhu cầu sử dụng. Ứng dụng kiểm tra tương thích, tìm điểm nghẽn và gợi ý linh kiện nâng cấp theo ngân sách bằng VND.

[Chạy thử trên máy bạn](#chay-thu) [Xem mã nguồn](https://github.com/PQA47/PC-Upgrade-Advisor)

## Thử nhanh: điểm nghẽn là CPU hay GPU?

Kéo hai thanh trượt. Công thức giống bước phân tích của ứng dụng: lấy điểm CPU chia điểm GPU.

Điểm CPU

Điểm GPU

CPU yếu hơnCân bằngGPU yếu hơn

## Từ cấu hình hiện tại đến danh sách nâng cấp

1. ### Nhập cấu hình

   Chọn CPU, GPU, mainboard, dung lượng RAM, loại ổ cứng, công suất nguồn, độ phân giải, mục đích sử dụng và ngân sách.
2. ### Phân tích

   Kiểm tra socket CPU với mainboard, ước tính công suất nguồn cần có, và so sánh điểm benchmark CPU với GPU.
3. ### Nhận gợi ý

   Xem kết luận có cần nâng cấp không, linh kiện đề xuất cùng socket, mức tăng hiệu năng và giá tham khảo.

## Những gì ứng dụng làm được

Phân tích điểm nghẽn

Cho biết CPU hay GPU đang kéo hiệu năng xuống, kèm tỷ lệ phần trăm.

Kiểm tra tương thích

Báo lỗi khi CPU không khớp socket mainboard, cảnh báo khi nguồn không đủ công suất.

Gợi ý theo nhu cầu

Đánh giá theo game, dựng phim, lập trình hoặc AI, ở độ phân giải 1080p, 1440p hay 4K. Có cả gợi ý RAM và ổ SSD.

Giá bán lẻ bằng VND

Lấy giá từ cửa hàng VTCOM. Linh kiện chưa có giá sẽ ghi “Price unavailable” thay vì tính là 0 đồng.

Tài khoản và lịch sử

Đăng ký, đăng nhập, lưu mỗi lần phân tích để mở lại hoặc xoá sau này.

Quên mật khẩu qua email

Liên kết đặt lại có hiệu lực 30 phút và chỉ dùng được một lần.

## Xây dựng bằng

- Python 3.11
- FastAPI
- SQLAlchemy + SQLite
- Jinja2
- Tailwind CSS
- APScheduler
- Argon2

Một script thu thập dữ liệu CPU, GPU, mainboard và giá bán lẻ, tự chạy lại mỗi 7 ngày. Dự án đang được phát triển và dữ liệu benchmark vẫn đang được bổ sung, nên kết quả hiện nên xem như tham khảo.

## Chạy thử trên máy Windows

```
git clone https://github.com/PQA47/PC-Upgrade-Advisor.git
cd PC-Upgrade-Advisor
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
py scripts\scraper.py
py -m uvicorn app.main:app --reload
```

Sau đó mở **http://127.0.0.1:8000**. Cần điền SMTP trong `.env` nếu muốn thử chức năng quên mật khẩu.

PC Upgrade Advisor · Mã nguồn tại [GitHub](https://github.com/PQA47/PC-Upgrade-Advisor)