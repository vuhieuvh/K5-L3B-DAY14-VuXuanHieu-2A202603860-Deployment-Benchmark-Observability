# Deployment — CP6 (chưa thực hiện)

**Trạng thái:** CP5 local PASS12/12, 42/42. Chưa tạo Render service/Key Value, chưa có URL public, chưa đặt secret trên cloud. Không nhận cấu hình file là bằng chứng deploy thành công.

## Cấu hình đã chuẩn bị

- Blueprint: `06-lab-complete/render.yaml`.
- Agent: Docker, rootDir `06-lab-complete`, Dockerfile/context trong thư mục đó, healthCheckPath `/health`.
- Redis-compatible service: Render Key Value; REDIS_URL lấy connectionString nội bộ qua fromService, cùng region Singapore.
- AGENT_API_KEY dùng generateValue, không có giá trị secret trong repo.
- ENVIRONMENT production; RATE_LIMIT_PER_MINUTE 10; DAILY_BUDGET_USD 1; REDIS_KEY_PREFIX day14-part6. PORT do nền tảng cấp, Docker CMD và HEALTHCHECK đọc biến này.
- Chọn plan free trong file; chưa khởi tạo hay đồng ý dịch vụ tính phí. Theo [Render Blueprint reference](https://render.com/docs/blueprint-spec), Key Value free không có data persistence qua restart dịch vụ; cần hiểu giới hạn này trước khi dùng thực tế.

## Công việc CP6 tiếp theo

1. Đưa code đã kiểm tra lên bản fork GitHub để Render đọc được.
2. Đăng nhập Render, tạo Blueprint từ repo, chọn Blueprint path `06-lab-complete/render.yaml`.
3. Kiểm tra plan và tạo web + Key Value; lấy key từ Environment trên dashboard, không gửi key trong chat hoặc commit.
4. Đợi deploy, kiểm tra `/ready` 200 (Redis kết nối), rồi mới lưu ảnh và URL.
5. Ghi URL public tại mục bên dưới, chạy bốn HTTP check theo CP6. Screenshot/log chỉ hiển thị HTTP code, không lộ key.
6. Chụp dashboard.png, running.png, test.png trong screenshots/; bổ sung Part 3 trong MISSION_ANSWERS gồm so sánh Railway/Render và pipeline Cloud Run.

## URL và kết quả cloud

- URL public: **chưa có**.
- GET /health: **chưa kiểm tra trên cloud**.
- GET /ready: **chưa kiểm tra trên cloud**.
- POST /ask thiếu key: **chưa kiểm tra trên cloud**.
- POST /ask có key: **chưa kiểm tra trên cloud**.
- Biến môi trường đã đặt trên Render: **chưa đặt**.
- Ảnh deploy: **chưa có**.

Không dùng kết quả local ở reports/part6 để điền thay kết quả cloud.
