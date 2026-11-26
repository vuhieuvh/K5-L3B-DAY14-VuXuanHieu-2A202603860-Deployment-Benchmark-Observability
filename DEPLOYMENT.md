# Deployment — CP6 (đủ bằng chứng triển khai)

**Trạng thái:** CP5 local PASS12/12, 42/42. Học viên đã tạo Blueprint từ commit 462991b, Render hiển thị tạo day14-agent và day14-redis thành công. Học viên cung cấp URL public; AI gọi trực tiếp health/ready/ask thiếu key được 200/200/401. Đã kiểm tra /ask với key hợp lệ trả 200 và có đủ ba ảnh dashboard/running/test. Chưa xác minh key hiện tại đã thay khác các key từng chia sẻ trong chat; không coi ảnh Environment updated là chứng minh giá trị key mới.

## Cấu hình đã chuẩn bị

- Blueprint: `06-lab-complete/render.yaml`.
- Agent: Docker, rootDir `06-lab-complete`, Dockerfile/context trong thư mục đó, healthCheckPath `/health`.
- Redis-compatible service: Render Key Value; REDIS_URL lấy connectionString nội bộ qua fromService, cùng region Singapore.
- AGENT_API_KEY dùng generateValue, không có giá trị secret trong repo.
- ENVIRONMENT production; RATE_LIMIT_PER_MINUTE 10; DAILY_BUDGET_USD 1; REDIS_KEY_PREFIX day14-part6. PORT do nền tảng cấp, Docker CMD và HEALTHCHECK đọc biến này.
- Chọn plan free trong file; chưa khởi tạo hay đồng ý dịch vụ tính phí. Theo [Render Blueprint reference](https://render.com/docs/blueprint-spec), Key Value free không có data persistence qua restart dịch vụ; cần hiểu giới hạn này trước khi dùng thực tế.

## Các bước CP6 đã thực hiện

1. Đưa code đã kiểm tra lên bản fork GitHub để Render đọc được.
2. Đăng nhập Render, tạo Blueprint từ repo, chọn Blueprint path `06-lab-complete/render.yaml`.
3. Kiểm tra plan và tạo web + Key Value; lấy key từ Environment trên dashboard, không gửi key trong chat hoặc commit.
4. Đợi deploy, kiểm tra `/ready` 200 (Redis kết nối), rồi mới lưu ảnh và URL.
5. Ghi URL public tại mục bên dưới, chạy bốn HTTP check theo CP6. Screenshot/log chỉ hiển thị HTTP code, không lộ key.
6. Chụp dashboard.png, running.png, test.png trong screenshots/; bổ sung Part 3 trong MISSION_ANSWERS gồm so sánh Railway/Render và pipeline Cloud Run.

## URL và kết quả cloud

- URL public: https://day14-agent-mi52.onrender.com
- GET /health: **200**, body status ok, AI kiểm tra trực tiếp URL public.
- GET /ready: **200**, body ready true; xác nhận dependency Redis sẵn sàng theo code app.
- POST /ask thiếu key: **401**, detail Missing or invalid API key.
- POST /ask có key hợp lệ: **200**, trả lời câu hỏi What is deployment?; bằng chứng reports/part3/ask-authenticated.json và ask-authenticated.txt, key không lưu trong file.
- Biến môi trường: Blueprint cấu hình ENVIRONMENT, AGENT_API_KEY (generateValue), REDIS_URL (fromService), RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD, REDIS_KEY_PREFIX; PORT do Render cấp. AI chưa trực tiếp xem Environment trên dashboard; đã sử dụng key học viên cung cấp qua chat để kiểm tra HTTP, không lưu key trong file. Đã xác nhận /ask 200 bằng key học viên cung cấp; không lưu giá trị key vào repo.
- Ảnh test: `screenshots/test.png`, học viên cung cấp ảnh POST /ask trên URL Render, HTTP/2 200 và JSON response, Date 26/11/2026 10:18:27 GMT. Ảnh không hiển thị giá trị key. Đã có `screenshots/running.png`: trang Render hiển thị day14-agent, Docker Free, URL public, main commit 462991b và Live. Đã có `screenshots/dashboard.png`: Overview hiển thị day14-agent Deployed và day14-redis Available, runtime datastore Valkey 8, cùng region Singapore.

Không dùng kết quả local ở reports/part6 để điền thay kết quả cloud.

Bằng chứng HTTP cloud thực tế: [public-checks.json](reports/part3/public-checks.json), checked_at 2026-11-26T16:52:27.569308+07:00. Không có token/key trong file. Chưa dùng kết quả local thay kết quả authenticated cloud.

Kiểm tra authenticated cloud lúc 2026-11-26T16:59:45.683631+07:00: HTTP200. Học viên đã chia sẻ key trong chat để AI kiểm tra; cần thay AGENT_API_KEY trên Render và kiểm tra lại bằng key mới. Không đưa giá trị key cũ/mới vào tài liệu hoặc ảnh.
