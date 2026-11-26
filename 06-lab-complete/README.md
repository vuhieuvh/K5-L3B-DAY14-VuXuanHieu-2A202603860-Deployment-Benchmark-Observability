# Part 6 — Final Project: Production-ready AI Agent

> **Trạng thái bản fork — CP5 ngày 26/11/2026:** đã hoàn thiện các module app và cấu hình Docker/Render. Script chấm nguyên bản đạt **PASS 12/12, 42/42 checks** trên Ubuntu WSL2. Đây là kết quả local; **chưa deploy Render, chưa có URL public**. Bằng chứng: [production-check.txt](../reports/part6/production-check.txt), [Compose smoke](../reports/part6/compose-results.json), [bài làm và AI log](../MISSION_ANSWERS.md). Phần mô tả bản khung/TODO bên dưới là đề gốc.

## Chạy bản đã hoàn thiện

Dùng Python Linux 3.11 để khớp requirements pin của lab. Môi trường đã tạo trên máy học viên:

```bash
source ~/venvs/day14-part6/bin/activate
cd /mnt/e/ai_thuc_chien/day_14_thuc_hanh/K5-L3B-DAY14-VuXuanHieu-2A202603860-Deployment-Benchmark-Observability/06-lab-complete
python check_production_ready.py
```

Muốn chạy Compose local thủ công, tạo `.env` và sinh key mới (không commit hoặc log key):

```bash
cp -n .env.example .env
python -c "from dotenv import set_key; import secrets; set_key('.env', 'AGENT_API_KEY', secrets.token_urlsafe(32))"
docker compose -p k5-day14-part6 up -d --build
curl http://localhost:18006/health
curl http://localhost:18006/ready
```

API `/ask` cần header X-API-Key trùng giá trị trong `.env`. Không cấu hình key thì tất cả request /ask bị 401. Không dùng cùng key cho môi trường cloud và local. Host port 18006 tránh cổng 8000/8080 đang dùng bởi bài trước và ứng dụng khác.

```bash
docker compose -p k5-day14-part6 down
```

Redis có named volume và AOF; `down` giữ volume, `down -v` xóa state. Thử smoke có tự tạo key và tự dọn stack: `python ../scripts/run_part6_compose.py` từ thư mục này.

Tests bổ sung (ngoài grader): cài `requirements-dev.txt`; chạy Redis tạm riêng ở host 18086 rồi `python -m unittest discover -s tests -v`. Biến TEST_REDIS_URL mặc định là `redis://127.0.0.1:18086/15`, chỉ trỏ tới Redis test dùng một lần, không trỏ cloud. Test dùng namespace ngẫu nhiên và Redis thật.

### Giới hạn đã biết

- Chi phí và token là mô phỏng của mock LLM, không phải hóa đơn nhà cung cấp.
- Process chết sau khi reserve budget có thể giữ khoản dự trữ đến khi key hết hạn: an toàn ngân sách nhưng giảm khả dụng. Chưa có job đối soát reservation bị bỏ dở.
- Unexpected exception có thể thiếu request log/X-Request-ID; Uvicorn có thể ghi traceback riêng. Trước khi thay mock bằng provider thật, cần rà soát đường lỗi và lọc thông tin nhạy cảm trong exception log.
- Không có tính năng conversation history trong Part 6 này, không bắt buộc tính điểm.
- Cấu hình Render và cách làm tiếp ở [DEPLOYMENT.md](../DEPLOYMENT.md); chưa tạo service cloud. Tài liệu Blueprint tham chiếu: [Render](https://render.com/docs/blueprint-spec).

---


Bạn tự xây một AI agent đủ chuẩn production từ **bản khung** trong thư mục này, kết hợp mọi thứ đã học ở Part 1–5.
Mọi file đều đã có sẵn, phần việc của bạn nằm ở các chỗ ghi `TODO`. Bản khung chạy được nhưng **chưa đạt tiêu chí nào**.

Bài chỉ được tính hoàn thành khi script chấm báo **`PASS 12/12`**:

```bash
pip install -r requirements.txt
python check_production_ready.py
```

---

## Checklist Deliverable

- [ ] Dockerfile (multi-stage, < 500 MB)
- [ ] docker-compose.yml (agent + redis)
- [ ] .dockerignore
- [ ] Health check endpoint (`GET /health`)
- [ ] Readiness endpoint (`GET /ready`)
- [ ] API Key authentication
- [ ] Rate limiting
- [ ] Cost guard
- [ ] Config từ environment variables
- [ ] Structured logging
- [ ] Graceful shutdown
- [ ] Public URL ready (Railway / Render config)

---

## Script chấm dựa vào những tiêu chí dưới đây

Script tự khởi động agent của bạn, gọi API thật, build và chạy Docker image. Để chấm được, agent phải tuân theo các quy ước sau:

| Hạng mục | Yêu cầu |
|----------|---------|
| Điểm vào | `app/main.py` có biến `app` (FastAPI), chạy được bằng `uvicorn app.main:app --workers 2` từ thư mục này |
| `GET /health` | Luôn trả **200** khi process còn chạy, kể cả khi Redis chưa kết nối được |
| `GET /ready` | **200** khi sẵn sàng; **503** khi Redis (`REDIS_URL`) không kết nối được |
| `POST /ask` | Body JSON `{"question": "..."}` (được phép có thêm `user_id`) → **200** |
| API key | Header `X-API-Key` phải trùng biến `AGENT_API_KEY`; thiếu hoặc sai → **401** |
| Rate limit | Tối đa `RATE_LIMIT_PER_MINUTE` request / 60 giây cho mỗi API key; vượt → **429** (nên có header `Retry-After`). State lưu trong **Redis**, vẫn còn sau khi restart agent |
| Cost guard | Tổng chi phí vượt `DAILY_BUDGET_USD` (hoặc `MONTHLY_BUDGET_USD`) → **402** |
| Biến môi trường | Đọc từ env: `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD` / `MONTHLY_BUDGET_USD`, `PORT`, `ENVIRONMENT`. Liệt kê đủ trong `.env.example`. Script chạy với `ENVIRONMENT=staging` |
| Log | Mỗi dòng log của app là **1 JSON object hợp lệ** (log của uvicorn không tính) |
| Graceful shutdown | Nhận SIGTERM khi đang có request → request đó vẫn trả 200, process tự thoát với exit code 0. Trong Docker, `docker stop` phải xong trong < 10 giây |
| Docker image | Multi-stage, base slim, user non-root, có `HEALTHCHECK`, < 500 MB. `CMD` lắng nghe theo biến `PORT` (mặc định 8000), uvicorn là PID 1. Container khởi động được khi **không có** Redis |
| Compose | Một service build từ `Dockerfile` + một service dùng image `redis:*`; agent có `REDIS_URL` trỏ tới service Redis và `depends_on` nó |
| `.dockerignore` | Loại trừ `.env`, `__pycache__`, `venv` |
| Deploy config | `railway.toml` (builder `DOCKERFILE`, `healthcheckPath = "/health"`) **hoặc** `render.yaml` (`type: web`, `healthCheckPath: /health`, secret dùng `generateValue` / `sync: false`) |

---

## Bản khung

```
06-lab-complete/
├── app/
│   ├── main.py           # TODO: /health, /ready, nối auth + rate limit + cost guard vào /ask, log JSON, shutdown
│   ├── config.py         # TODO: đọc cấu hình từ biến môi trường
│   ├── auth.py           # TODO: verify_api_key → 401
│   ├── rate_limiter.py   # TODO: check_rate_limit → 429 (Redis)
│   ├── cost_guard.py     # TODO: check_budget → 402, record_cost (Redis)
│   └── redis_client.py   # TODO: kết nối Redis + redis_healthy() cho /ready
├── utils/mock_llm.py     # Mock LLM — có sẵn, không cần sửa
├── Dockerfile            # TODO: viết lại thành multi-stage production
├── docker-compose.yml    # TODO: thêm redis
├── .dockerignore         # TODO
├── .env.example          # TODO: liệt kê đủ biến
├── railway.toml          # TODO (hoặc render.yaml)
├── render.yaml           # TODO (hoặc railway.toml)
├── requirements.txt      # Có sẵn
├── check_production_ready.py   # Script chấm — không sửa
└── benchmark-observability/    # Part 7 — làm sau khi xong Part 6
```

**Gợi ý thứ tự làm:** `/health` → `config.py` → log JSON → `auth.py` → `redis_client.py` + `/ready` → `rate_limiter.py` → `cost_guard.py` → graceful shutdown → `Dockerfile` + `.dockerignore` → `docker-compose.yml` → `railway.toml` / `render.yaml`. Hướng dẫn từng bước: [CODE_LAB.md — Part 6](../CODE_LAB.md#part-6-final-project-60-phút).

---

## Chạy local

```bash
pip install -r requirements.txt
cp .env.example .env

# Chạy nhanh không cần Docker (cần Redis riêng nếu muốn test rate limit thật)
AGENT_API_KEY=dev-key uvicorn app.main:app --reload

# Chạy cả agent + redis
docker compose up --build

curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
     -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
     -d '{"question": "What is deployment?"}'
```

---

## Chấm bài

```bash
python check_production_ready.py                 # chấm đầy đủ — cần Docker đang chạy
python check_production_ready.py --skip-docker   # chế độ nhanh khi đang làm (bỏ build image)
python check_production_ready.py --static-only   # chỉ đọc file, không chạy agent
python check_production_ready.py --public-url https://your-app.railway.app   # thêm kiểm tra URL đã deploy
```

- Kết quả in theo từng tiêu chí: ✅ đạt · ❌ chưa đạt · ⚠️ chưa kiểm tra được.
- **Chỉ PASS khi cả 12 tiêu chí ✅.** Mục ⚠️ (vd máy chưa bật Docker) cũng tính là chưa đạt, nên khi nộp bài phải chạy chế độ đầy đủ.
- Lần đầu chạy, script build Docker image nên mất vài phút. Bài test stateless cần Redis: script dùng `REDIS_URL` nếu có, không thì tự bật container `redis:7-alpine` tạm thời.

---

## Deploy

**Railway**

```bash
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=your-secret-key
railway up
railway domain        # nhận public URL
```

**Render:** push repo lên GitHub → Render Dashboard → New → Blueprint → chọn repo (Render đọc `render.yaml`) → điền secret → Deploy.

Sau khi deploy: `python check_production_ready.py --public-url <URL>` và ghi URL vào `DEPLOYMENT.md` (xem [DAY14_DELIVERY_CHECKLIST.md](../DAY14_DELIVERY_CHECKLIST.md)).

---

## Part 7 — Benchmark & Observability

Agent đã chạy được, bước tiếp theo là đo xem nó **nhanh** và **đúng** tới đâu, rồi **giám sát** khi chạy thật:

```bash
cd benchmark-observability
```

| Thư mục | Nội dung |
|---------|----------|
| `develop/` | Agent có `/metrics`, load test (p50/p95/p99, SLO), eval trên golden dataset + quality gate |
| `production/` | Docker Compose: agent x2 + Nginx + Prometheus + Grafana + Jaeger + Locust, 4 alert rules |

Hướng dẫn đầy đủ: [benchmark-observability/README.md](benchmark-observability/README.md). Nộp kèm `BENCHMARK_REPORT.md` theo [mẫu](benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md).
