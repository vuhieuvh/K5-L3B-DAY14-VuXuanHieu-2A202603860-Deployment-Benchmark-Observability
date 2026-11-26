# Day 14 Lab — Mission Answers

Phạm vi hiện tại: Part 1, 2, 4, 5 và CP5 Part 6 đã có nội dung/bằng chứng. Part 6 đạt script 12/12 local; Part 3/CP6 deploy cloud và Part 7 chưa thực hiện.
Áp dụng hướng dẫn K5 trong README.md và CHECKPOINTS.md; tiêu chí Part 1 theo INSTRUCTOR_GUIDE.md.

## Part 1: Localhost vs Production

### Exercise 1.1: Phát hiện anti-patterns

Đường dẫn và dòng dưới đây tham chiếu `01-localhost-vs-production/develop/app.py` nguyên bản.

| # | Vấn đề và vị trí | Tác hại | Cách xử lý phù hợp |
|---|---|---|---|
| 1 | API key và URL database chứa thông tin đăng nhập nằm trong code, dòng 17–18 | Nếu là thông tin thật, push public sẽ làm lộ quyền truy cập; xóa file không xóa secret trong lịch sử Git | Đọc từ env hoặc secret manager, không commit secret; thu hồi và thay key nếu đã lộ |
| 2 | `DEBUG`, `MAX_TOKENS` cố định, dòng 21–22 | Đổi cấu hình phải sửa code; khai báo biến chưa có nghĩa là đã áp dụng, vì endpoint chưa dùng hai biến này | Tập trung cấu hình và đọc env, truyền cấu hình thực sự tới thành phần sử dụng |
| 3 | `print` cho request và response, dòng 33, 38 | Thiếu timestamp, severity, event chuẩn; nội dung câu hỏi/câu trả lời có thể chứa dữ liệu nhạy cảm | Dùng logging có cấu trúc, log metadata cần thiết và lọc dữ liệu nhạy cảm |
| 4 | In API key ra log, dòng 34 | Secret có thể lộ qua log tập trung dù code không public | Không log secret; chỉ log trạng thái cấu hình hoặc mã định danh không nhạy cảm |
| 5 | Không có endpoint `/health`, xem các route trong file | Nền tảng không có HTTP probe chuyên biệt để kiểm tra process; restart còn phụ thuộc cấu hình nền tảng | Thêm liveness endpoint nhẹ; readiness riêng cho tình trạng sẵn sàng |
| 6 | Bind `localhost`, dòng 51 | Chỉ nhận kết nối loopback trong môi trường chạy; traffic tới interface mạng của container không vào được | Bind `0.0.0.0` trong container, kiểm soát truy cập bằng mạng và xác thực |
| 7 | Port cố định `8000`, dòng 52 | Không thích ứng với `PORT` do nền tảng cấp | Đọc và kiểm tra `PORT` từ env |
| 8 | `reload=True` bật cứng, dòng 53 | Tạo watcher/reloader phục vụ phát triển, tăng chi phí vận hành và có thể restart khi file thay đổi | Chỉ bật reload ở môi trường phát triển |

Ngoài ra, bản develop không có lifespan cleanup riêng cho tài nguyên ứng dụng. Không kết luận rằng Uvicorn luôn tắt đột ngột: server có cơ chế shutdown của nó; muốn chứng minh request không bị cắt cần thử SIGTERM khi đang xử lý request.

Các credential ở ví dụ là dữ liệu giả của đề bài; bài thực hành dùng mock LLM, không gọi OpenAI thật.

### Exercise 1.2: Chạy bản develop — bằng chứng thực tế

Học viên đã tạo môi trường Linux `~/venvs/day14`, cài requirements của Part 1 production và tự chạy script trong Ubuntu WSL2. Phiên bản thực tế: Python 3.14.4, FastAPI 0.115.0, Uvicorn 0.30.0. Lần chạy lưu bằng chứng: 26/11/2026 lúc 14:59:53 GMT+7.

**Môi trường đã xác nhận:** Ubuntu WSL2, `os.name = posix`; file bằng chứng ghi `Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.43`. Kết quả này thay thế lần thử ban đầu trên Windows. Chưa kiểm chứng graceful shutdown với request đang chạy: script ghi rõ `graceful_shutdown_tested: false`, dù server được dừng khi kết thúc kiểm tra.

Chạy lại toàn bộ các HTTP check từ gốc repo trong Ubuntu WSL2:

```bash
source ~/venvs/day14/bin/activate
python -m pip install -r 01-localhost-vs-production/production/requirements.txt
python scripts/run_part1.py
```

Script chạy hai app nguyên bản qua Uvicorn CLI, không bật reload, rồi dừng các process do nó tạo. Develop dùng `127.0.0.1:8000`, production dùng `127.0.0.1:8001`. Đây là kiểm tra HTTP chức năng, không đo benchmark và không kiểm tra cấu hình host/port trong khối `if __name__ == '__main__'`.

Lệnh khởi động tương đương cho develop, từ `01-localhost-vs-production/develop/`:

```bash
source ~/venvs/day14/bin/activate
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Ở terminal khác:

```bash
curl -i -X POST "http://127.0.0.1:8000/ask?question=Hello"
```

Kết quả của lần chạy được ghi trong [http-results.json](reports/part1/http-results.json), trường `run_at` có múi giờ +07:00. Dữ liệu dưới đây lấy từ file đó:

| Bản | Request | HTTP thực nhận | Nhận xét |
|---|---|---:|---|
| Develop | `GET /` | 200 | App đang phục vụ |
| Develop | `POST /ask?question=Hello` | 200 | Có trường `answer` chứa câu trả lời mock |
| Develop | `POST /ask`, JSON `{"question":"Hello"}` | 422 | Báo thiếu `query.question`; bản này không nhận question từ JSON |
| Develop | `GET /health` | 404 | Chưa có health endpoint |
| Production | `POST /ask`, JSON `{"question":"Hello"}` | 200 | Có `question`, `answer`, `model` |
| Production | `GET /health` | 200 | `status: ok` |
| Production | `GET /ready` | 200 | `ready: true` sau startup |
| Production | `POST /ask`, JSON `{}` | 422 | `question field is required` |

Response nguyên văn của develop với `Hello` trong lần chạy được lưu:

```json
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Mock chọn ngẫu nhiên câu trả lời, nên chạy lại có thể nhận nội dung khác. JSON và log sẽ được cập nhật cùng lần chạy; không coi câu trả lời trên là kết quả cố định.

Log server thực tế: [develop-server.log](reports/part1/develop-server.log), [production-server.log](reports/part1/production-server.log). Log develop cho thấy code in cả key giả ra console.

### Exercise 1.3: Bảng so sánh và ý nghĩa

| Feature | Develop | Production trong code mẫu | Tại sao quan trọng? |
|---|---|---|---|
| Config | Hằng số trong `app.py` | `config.py` dùng dataclass và `os.getenv`, có validation | Giữ cùng code giữa môi trường, thay cấu hình khi triển khai; phát hiện sớm cấu hình thiếu |
| Secrets | Hardcode key và URL database; in key ra console | Đọc `OPENAI_API_KEY`, `AGENT_API_KEY` từ env; endpoint chỉ log metadata | Giảm nguy cơ lộ credential qua Git/log; vẫn phải bảo vệ env và quyền truy cập nền tảng |
| Host/port | `localhost:8000` cố định trong entrypoint | `settings.host` mặc định `0.0.0.0`; `settings.port` từ `PORT` | Container cần nhận traffic từ bên ngoài loopback; cloud có thể cấp port riêng. Đây là đối chiếu code, vì lần chạy dùng CLI chỉ định host/port |
| Health check | Không có `/health`; thực chạy trả 404 | `/health` trả trạng thái và uptime; thực chạy trả 200 | Cung cấp liveness probe để hệ thống giám sát/orchestrator đánh giá process; phải cấu hình probe trên nền tảng |
| Readiness | Không có route `/ready` | Cờ `is_ready` trong lifespan; thực chạy sau startup trả 200 | Cho load balancer biết có thể nhận traffic; ví dụ chỉ dùng cờ, chưa kiểm tra dependency như Redis |
| Logging | `print`, log nguyên câu hỏi, response và key | Có `logger`, event và metadata; khai báo format hướng tới JSON | Log có cấu trúc giúp lọc, tìm và tổng hợp sự cố; mẫu hiện có giới hạn nêu bên dưới |
| Shutdown | Không có cleanup riêng trong lifespan | Có lifespan startup/shutdown và khai báo SIGTERM handler | Cần ngừng nhận tải, hoàn thành request đang chạy và đóng tài nguyên trước khi thoát. Chưa thử SIGTERM khi có request đang chạy trong lần kiểm tra này |
| Reload | Luôn bật trong `python app.py` | Đọc `DEBUG`, mặc định false | Tránh chạy watcher và reload ngoài ý muốn trong production |
| Input | `question: str` là query parameter | Đọc JSON, kiểm tra question trống | Client phải gọi đúng hợp đồng API; production mẫu vẫn cần validation chặt hơn cho kiểu dữ liệu và JSON không hợp lệ |

**Giới hạn logging quan sát được:** `production/config.py` gọi `logging.warning` khi thiếu `OPENAI_API_KEY`, trước `logging.basicConfig` trong `app.py`. Trong lần chạy không có key thật, root logger được cấu hình trước, nên `basicConfig` sau đó không áp dụng format mong muốn; log có `WARNING:root:...`, các event INFO của app không xuất hiện. Ngoài ra, ngay cả khi format đó được áp dụng, chèn `json.dumps(...)` vào chuỗi `"msg":"%(message)s"` không tự escape dấu nháy, có nguy cơ sinh JSON không hợp lệ. Vì vậy không khẳng định bản mẫu đã đạt yêu cầu mỗi dòng app log là JSON hợp lệ. Part 6 cần xử lý và kiểm tra riêng; Part 1 giữ nguyên code để so sánh.

### Câu hỏi thảo luận

1. **Push API key thật lên GitHub public:** người khác có thể lấy key để dùng dịch vụ, phát sinh chi phí hoặc truy cập dữ liệu trong phạm vi quyền của key. Phải thu hồi key, tạo key mới và xử lý lịch sử Git nếu cần; chỉ xóa dòng code là chưa đủ.
2. **Vì sao stateless quan trọng khi scale:** request có thể tới instance khác hoặc instance bị restart. State trong RAM từng instance không được chia sẻ và có thể mất; đưa session, rate limit, budget vào Redis/database giúp các instance dùng chung state. Stateless không tự đảm bảo scale vô hạn: Redis, database và dịch vụ LLM vẫn có giới hạn.
3. **Dev/prod parity:** giữ phiên bản runtime, dependency, loại dịch vụ và cách khởi động gần nhau để giảm lỗi chỉ xuất hiện khi deploy. Docker và dependency được pin giúp giảm khác biệt; các secret/URL và quy mô vẫn thay đổi theo môi trường.
4. **Health khác readiness:** health trả lời process còn sống không; readiness trả lời có nhận request được không. Mất Redis không nhất thiết đồng nghĩa process chết; trong yêu cầu Part 6, `/health` vẫn 200 còn `/ready` phải 503.
5. **Graceful shutdown:** khi nền tảng yêu cầu dừng, server cần xử lý request đang chạy trong thời gian cho phép và cleanup tài nguyên. Có handler hoặc log shutdown chưa chứng minh request đang chạy hoàn thành; cần phép thử thực tế trên Linux.

### Tự đánh giá theo rubric Part 1

| Tiêu chí | Điểm tối đa | Đánh giá nội dung/bằng chứng hiện có |
|---|---:|---|
| Exercise 1.1: ≥ 5 anti-patterns | 2 | Đủ: 8 vấn đề, vị trí code, tác hại và hướng xử lý |
| Exercise 1.2: chạy develop thành công | 2 | Đủ: học viên tự chạy trên Ubuntu WSL2, HTTP 200 từ app thật; có JSON và log |
| Exercise 1.3: bảng so sánh có giải thích | 4 | Đủ bảng, giải thích WHY, phân biệt đọc code và thực nghiệm |

Ước tính theo nội dung ba mục: **8/8**. Đây là tự đánh giá, không phải điểm chính thức. Đã có bằng chứng chạy trong WSL2 Linux đúng yêu cầu môi trường K5 cho Part 1. Không áp dụng kết quả Part 1 để suy ra PASS 12/12 Part 6 hay điểm các Part khác.

## Part 2: Docker

### Exercise 2.1: Dockerfile cơ bản

Đối chiếu trực tiếp `02-docker/develop/Dockerfile`:

1. **Base image:** `python:3.11` (bản đầy đủ), chứa môi trường hệ điều hành và Python để cài thư viện/chạy app. Bản develop này không dùng tag `slim`.
2. **Working directory:** `WORKDIR /app` đặt thư mục làm việc cho các lệnh tiếp theo và lệnh khởi động. Các đích COPY tương đối được tính từ thư mục này.
3. **COPY requirements trước source:** Docker có thể tái sử dụng layer cài dependency khi chỉ source thay đổi, vì requirements và các layer trước đó không đổi. Thay requirements hoặc base image có thể khiến layer cài thư viện phải build lại.
4. **CMD và ENTRYPOINT:** CMD định nghĩa lệnh/đối số mặc định, có thể được thay bằng đối số sau tên image khi `docker run`. ENTRYPOINT định nghĩa chương trình chính; khi kết hợp dạng exec, CMD thường cung cấp đối số mặc định cho chương trình đó. ENTRYPOINT vẫn có thể thay bằng `--entrypoint`. File develop dùng `CMD ["python", "app.py"]`, không khai báo ENTRYPOINT riêng.

### Exercise 2.2: Build và chạy container

**Nguồn bằng chứng:** output học viên tự chạy trong Ubuntu WSL2 và gửi trong chat ngày 26/11/2026; AI chưa tự thực thi lại các lệnh Docker này. Học viên xác nhận build xong; output `docker ps`, HTTP và server log bên dưới xác nhận image đã chạy thành container.

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name day14-develop -p 127.0.0.1:8000:8000 my-agent:develop
docker ps --filter name=day14-develop
curl -i http://localhost:8000/health
curl -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker?"
docker logs day14-develop
```

Build context là gốc repo (`.`); Dockerfile COPY theo đường dẫn từ gốc. `-d` chạy nền; `--name` đặt tên; `-p 127.0.0.1:8000:8000` nối cổng 8000 loopback của máy với cổng 8000 trong container. EXPOSE chỉ mô tả cổng, không tự publish ra máy.

Kết quả học viên gửi:

- Container ID: `ed11855d6a06c52b4d639a8b70e1ea161fc3fa18c15aaff56afc66cb3bb7f5b3`.
- `docker ps`: image `my-agent:develop`, command `"python app.py"`, trạng thái `Up 14 seconds`, tên `day14-develop`, cổng `127.0.0.1:8000->8000/tcp`.
- `GET /health`: **HTTP/1.1 200 OK**, header Date `Thu, 26 Nov 2026 08:17:46 GMT`; body:

```json
{"status":"ok","uptime_seconds":26.0,"container":true}
```

- `POST /ask?question=What%20is%20Docker?`: **HTTP/1.1 200 OK**, header Date `Thu, 26 Nov 2026 08:18:16 GMT`; body:

```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Log học viên gửi xác nhận Uvicorn chạy trên `0.0.0.0:8000`, có hai access log tương ứng GET /health và POST /ask trả 200. Chuỗi lệnh trong đoạn chat có ký tự dán lặp, nhưng response và access log cho thấy endpoint thực nhận đúng query. Đây là kiểm tra chức năng, không phải số liệu latency benchmark.

**Dung lượng thực đo:** đã có output `docker images` và `docker image inspect` do học viên gửi; bảng và phép tính ở Exercise 2.3 bên dưới.

### Exercise 2.3: Multi-stage build — phân tích và số đo thực tế

Đối chiếu `02-docker/production/Dockerfile`:

- **Builder:** dùng `python:3.11-slim`, cài gcc và libpq-dev, cài requirements với `pip --user` vào `/root/.local`.
- **Runtime:** bắt đầu từ một image `python:3.11-slim` mới, copy thư viện từ builder và code ứng dụng, chạy bằng user `appuser`, có HEALTHCHECK và chạy Uvicorn 2 workers.
- **Vì sao có thể nhỏ hơn:** runtime dùng base slim và không mang theo các layer cài build tools của builder. Chỉ artifact cần để chạy được copy sang runtime. Mức giảm thực tế còn phụ thuộc base và dependency; phải đo, không lấy dung lượng ước lượng trong comment làm kết quả.
- **Lưu ý:** HEALTHCHECK đánh dấu trạng thái healthy/unhealthy; riêng HEALTHCHECK không tự khiến Docker restart container. Việc phục hồi cần chính sách và cơ chế điều phối phù hợp.

Học viên đã chạy build production từ gốc repo:

```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images --filter "reference=my-agent:*"
docker image inspect my-agent:develop my-agent:advanced --format '{{.RepoTags}} size_bytes={{.Size}}'
```

Output học viên gửi (nguồn bằng chứng trong chat, AI chưa tự đo lại):

```text
IMAGE               ID             DISK USAGE   CONTENT SIZE
my-agent:advanced   8f8e839ec753        240MB         57.4MB
my-agent:develop    b90e87db2390       1.67GB          426MB

[my-agent:develop] size_bytes=1667784544
[my-agent:advanced] size_bytes=239811351
```

| Image | Size từ inspect (byte) | MB thập phân (1 MB = 1.000.000 byte) |
|---|---:|---:|
| Develop | 1.667.784.544 | 1.667,78 |
| Advanced | 239.811.351 | 239,81 |

Công thức: `(Size_develop - Size_advanced) / Size_develop × 100`.

Kết quả từ số byte: **giảm 85,62%**, tương đương **1.427.973.193 byte** (khoảng 1.427,97 MB). Advanced nhỏ hơn 500 MB theo số Size được báo.

Dùng cùng trường `.Size` để tính; không lấy CONTENT SIZE của image này so với DISK USAGE của image kia. Các giá trị MB/GB ở bảng Docker đã làm tròn. Chênh lệch này phản ánh cả thay đổi base full → slim, multi-stage và các thành phần của từng image; không quy toàn bộ mức giảm riêng cho multi-stage. Chưa kiểm tra advanced chạy thành công chỉ từ việc build và đo dung lượng.


### Exercise 2.4: Docker Compose stack

Đối chiếu `02-docker/production/docker-compose.yml` và `nginx/nginx.conf`, stack có **4 service**:

```text
Client (Ubuntu/Windows)
    |
    | HTTP 127.0.0.1:18080 (host) -> 80 (container)
    v
  Nginx ----- proxy_pass -----> agent:8000 (FastAPI, 2 Uvicorn workers)
                                  |
                         cấu hình địa chỉ dependency
                         /                         \
                redis:6379                    qdrant:6333
```

- **Nginx:** reverse proxy tới upstream `agent:8000`, có rate limit 10 request/giây theo IP cho location `/`, security headers và đường dẫn `/health` riêng. Host chỉ publish HTTP loopback 18080; không có TLS trong config mẫu.
- **Agent:** build từ target runtime của Dockerfile production; không publish cổng trực tiếp ra host. Hai workers là hai process trong một container; Compose hiện chưa cấu hình scale thành hai replica dù comment đầu file nhắc đến replicas.
- **Redis:** image `redis:7-alpine`, có health check `redis-cli ping`, volume `redis_data`.
- **Qdrant:** image `qdrant/qdrant:v1.9.0`, vector database, volume `qdrant_data`, kiểm tra cổng 6333 trong health check.
- Các service cùng network bridge `internal`, dùng tên service để phân giải địa chỉ. Agent chờ Redis và Qdrant healthy qua `depends_on`; Nginx phụ thuộc agent nhưng không chờ điều kiện agent healthy.
- `REDIS_URL` và `QDRANT_URL` được truyền qua env. **Code `main.py` hiện chỉ gọi mock LLM, chưa dùng Redis/Qdrant để đọc ghi**; sơ đồ dependency không phải bằng chứng đã có luồng cache hoặc retrieval thực tế.

**Thao tác và lỗi đã gặp:** học viên tạo `.env.local` trống (được gitignore) và chạy `docker compose -p k5-day14-docker up -d --build`. Output ban đầu xác nhận build agent xong, Redis và Qdrant healthy, agent started; Nginx lỗi publish host port 80. Thử 8080 vẫn lỗi. Kiểm tra Windows cho thấy port 80 excluded/listener PID 4, port 8080 do `chat24-api` dùng. Thử bind 18080 thành công, sau đó đổi mapping hiện hành sang `127.0.0.1:18080:80`, bỏ publish 443 vì chưa cấu hình TLS. Các cổng bên trong stack không thay đổi.

**Bằng chứng HTTP do học viên tự chạy và gửi trong chat:**

```bash
curl -i -X POST http://localhost:18080/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Explain microservices"}'
```

```text
HTTP/1.1 200 OK
Server: nginx
Date: Thu, 26 Nov 2026 08:32:13 GMT
Content-Type: application/json
Content-Length: 126
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
```

```json
{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

Kết quả xác nhận request tới cổng host 18080 được Nginx xử lý và agent trả câu trả lời mock. Chuỗi dán lệnh trong chat có phần lặp, nên lệnh ở trên là phiên bản sạch để chạy lại; response là kết quả học viên gửi, không phải AI tự gọi API. Đã bổ sung và AI đã đọc trực tiếp các file do học viên lưu bằng `tee`:

| File bằng chứng | Kết quả đã đối chiếu |
|---|---|
| [compose-ps.txt](reports/part2/compose-ps.txt) | Agent, Qdrant, Redis đều Up (healthy); Nginx Up, mapping `127.0.0.1:18080->80/tcp` |
| [nginx-health.txt](reports/part2/nginx-health.txt) | HTTP 200, Server nginx, Date 26/11/2026 08:34:15 GMT, body status ok, version 2.0.0 |
| [nginx-ask.txt](reports/part2/nginx-ask.txt) | HTTP 200, Server nginx, Date 26/11/2026 08:34:26 GMT, body có answer mock |

Response `/ask` trong lần lưu file khác lần 08:32:13 ở trên vì mock chọn ngẫu nhiên; cả hai lần đều trả 200. Nginx không khai báo HEALTHCHECK riêng, nên chỉ ghi nhận Up, không gọi nó healthy. Uptime trong `/health` là thời gian sống của worker, không phải latency request.

### Tự đánh giá theo rubric Part 2

- Exercise 2.1: nội dung đã đủ 4 câu theo Dockerfile thực tế (tối đa 2 điểm).
- Exercise 2.2: có bằng chứng container hoạt động và HTTP 200 do học viên gửi (tối đa 2 điểm).
- Exercise 2.3: đã phân tích hai stage, có image production và dung lượng thực đo của cả hai image, tính mức giảm 85,62% (tối đa 2 điểm).
- Exercise 2.4: đủ sơ đồ và giải thích các service; có file Compose ps, GET /health và POST /ask qua Nginx, cả hai HTTP check trả 200 (tối đa 2 điểm).
- Tự đánh giá **8/8** theo nội dung và bằng chứng đã đối chiếu; không phải điểm chính thức. Agent, Redis và Qdrant healthy, Nginx Up và phục vụ HTTP thành công.

## Part 4: API Security — CP3

### Exercise 4.1: API key authentication

Đối chiếu `04-api-gateway/develop/app.py`:

1. **API key được kiểm tra ở đâu?** `APIKeyHeader(name="X-API-Key", auto_error=False)` đọc header, `verify_api_key` kiểm tra có key và so sánh với `API_KEY` đọc từ biến môi trường `AGENT_API_KEY`. Endpoint `/ask` sử dụng dependency `Depends(verify_api_key)`. `/` và `/health` là public.
2. **Thiếu hoặc sai key thì sao?** Thiếu key trả 401 với hướng dẫn thêm header; sai key trả 403 với `Invalid API key.`. Đây là hành vi của mẫu Part 4 develop; Part 6 yêu cầu cả thiếu và sai key đều trả 401.
3. **Rotate key thế nào?** Tạo key mới, cập nhật `AGENT_API_KEY` trên server, restart/redeploy vì code đọc env khi import, và cập nhật client. Khi cần chuyển đổi không gián đoạn, thiết kế khoảng chuyển tiếp chấp nhận hai key rồi thu hồi key cũ; code mẫu hiện chỉ nhận một key. Không ghi key thật vào Git/log. Bản mẫu in key ra console khi startup, chỉ phù hợp key demo và cần bỏ hành vi này khi làm production.

Học viên tự khởi động trong Ubuntu WSL2:

```bash
cd 04-api-gateway/develop
AGENT_API_KEY=secret-key-123 python app.py
```

`secret-key-123` là key demo theo hướng dẫn lab. Giữ server ở terminal thứ nhất, dùng terminal thứ hai gửi JSON tới `/ask`. Ba file học viên lưu bằng `tee` đã được AI đọc trực tiếp và đối chiếu:

| Trường hợp | File bằng chứng | Kết quả thực nhận | Date header (GMT), 26/11/2026 |
|---|---|---|---|
| Không có header key | [api-key-missing.txt](reports/part4/api-key-missing.txt) | 401 Unauthorized, detail Missing API key | 08:45:26 |
| Header key demo sai | [api-key-invalid.txt](reports/part4/api-key-invalid.txt) | 403 Forbidden, detail Invalid API key | 08:45:56 |
| Header key demo hợp lệ | [api-key-valid.txt](reports/part4/api-key-valid.txt) | 200 OK, có question Hello và answer mock | 08:46:14 |

Chuỗi lệnh copy trong chat có chỗ lặp, nhưng các file chứa đầy đủ response và JSON hợp lệ, bao gồm body 403 không hiển thị trong đoạn chat. Không có benchmark hoặc chi phí LLM thật ở phép thử này.

### Exercise 4.2: JWT authentication

**Đọc code `production/auth.py`:**

1. Client gửi JSON username/password tới `POST /auth/token`; tài khoản mẫu là `student` / `demo123`, role `user`.
2. `authenticate_user` kiểm tra tài khoản demo. `create_token` ký JWT bằng HS256, secret lấy từ `JWT_SECRET`; claims gồm `sub` (username), `role`, `iat`, `exp`, hết hạn sau 60 phút.
3. Client gửi `Authorization: Bearer <token>` khi gọi `POST /ask`. `verify_token` kiểm tra chữ ký và hạn token, lấy username/role; token thiếu trả 401, token hết hạn trả 401, token không hợp lệ trả 403 theo code mẫu.
4. Chữ ký chống sửa nội dung token, không mã hóa payload; không đưa secret hoặc dữ liệu nhạy cảm vào claims. JWT không thay thế HTTPS, bảo vệ signing secret và quản lý quyền.

**Bằng chứng do AI trực tiếp chạy trong Ubuntu WSL2 theo yêu cầu học viên:** script `scripts/run_part4.py`, server cô lập ở `127.0.0.1:8004`, dùng app production nguyên bản, không reload. Tạo JWT_SECRET ngẫu nhiên cho process, chỉ giữ token trong RAM; không lưu secret/token thật vào file. Server develop của học viên trên cổng 8000 được giữ nguyên.

| Phép thử | HTTP thực nhận |
|---|---:|
| POST /ask thiếu Bearer token | 401 |
| POST /auth/token sai password demo | 401 |
| POST /auth/token đúng student/demo123 | 200 |
| POST /ask với JWT student hợp lệ | 200 |
| GET /admin/stats với JWT student | 403 |

Kết quả cho thấy xác thực thành công không đồng nghĩa có quyền admin. File bằng chứng [jwt-rate-cost-results.json](reports/part4/jwt-rate-cost-results.json), mục `jwt_results`, có response và headers. Body login đã che cả `access_token` và token prefix trong `hint`; headers là metadata của response gốc, không phải kích thước body JSON đã che token.

### Exercise 4.3: Rate limiting

- **Thuật toán thực tế:** sliding window dạng log timestamp; mỗi user có deque thời điểm request. Trước khi kiểm tra, loại bỏ timestamps cũ hơn 60 giây; đạt giới hạn thì trả 429, ngược lại thêm timestamp mới. Comment gọi là Sliding Window Counter nhưng cấu trúc code giữ từng timestamp, không chỉ một counter tổng hợp.
- **Giới hạn:** role user 10 request/60 giây, role admin 100 request/60 giây. Các trường daily_limit trong DEMO_USERS không quyết định limiter này.
- **Admin có bypass không?** Code hiện chỉ chọn limiter cao hơn bằng role, không bỏ giới hạn hoàn toàn. Nếu sản phẩm cần miễn giới hạn thì phải thêm chính sách quyền rõ ràng; không mặc nhiên coi admin được unlimited.
- **Kết quả chạy thật:** đã gọi /ask thành công 1 lần để kiểm JWT, rồi gửi thêm 20 request trong cùng cửa sổ. Vòng 20 lần có **9 lần HTTP 200 và 11 lần HTTP 429**; tổng cộng 10 /ask thành công. GET /me/usage ghi requests = 10. Những request bị chặn không gọi mock LLM.
- Response 429 đầu tiên có `X-RateLimit-Limit: 10`, `X-RateLimit-Remaining: 0`, `Retry-After: 59`, JSON detail `Rate limit exceeded`, window_seconds 60. Giá trị Retry-After là kết quả lần chạy này, có thể khác khi chạy lại.
- **Giới hạn demo:** state trong RAM theo process, không dùng Redis. Restart làm mất state, nhiều worker/replica có thể có bộ đếm riêng. Part 6 cần state dùng chung trong Redis.

Bằng chứng: mục `rate_test` trong [jwt-rate-cost-results.json](reports/part4/jwt-rate-cost-results.json), chứa đủ 20 response, thống kê được tính từ HTTP thực nhận. Log: [jwt-rate-server.log](reports/part4/jwt-rate-server.log).

### Exercise 4.4: Cost guard

**Logic của code mẫu đang chạy (`production/cost_guard.py` và app.py):**

1. Sau xác thực và rate limit, `check_budget(username)` kiểm tra chi phí đã ghi nhận trước khi gọi mock LLM.
2. Budget mặc định mỗi user là 1 USD/ngày; global là 10 USD/ngày. Khi user đạt/vượt budget thì 402; khi global đạt/vượt thì 503 theo code, không phải 402 cho mọi trường hợp.
3. Gọi mock LLM thành công mới tính input/output token bằng số từ nhân 2, rồi `record_usage` cộng chi phí theo các hằng đơn giá trong đề. Đây là ước tính giả lập, không phải token hoặc hóa đơn nhà cung cấp thật, cũng không xác minh giá model hiện hành.
4. Record per-user tạo lại khi ngày đổi. Global có `_global_today` nhưng không thấy logic reset `_global_cost` theo ngày; không kết luận global reset đúng chỉ từ comment. Mốc ngày dùng time.strftime theo timezone process, trong khi thông báo nói UTC; triển khai thật cần thống nhất timezone.
5. `/me/usage` trả cost đã dùng và ngân sách còn lại. Trong response `/ask`, field `budget_remaining_usd` đang gán nhầm `usage.total_cost_usd` (chi phí đã dùng), nên không dùng field đó làm số dư ngân sách.

**Thí nghiệm thật để quan sát 402:** tạo process riêng trên `127.0.0.1:8005`, import app mẫu rồi đặt `app.cost_guard.daily_budget_usd = 0.000001` trong RAM trước khi chạy Uvicorn. Không sửa file nguồn hoặc trạng thái server khác. Budget này là cấu hình thí nghiệm chủ động, không phải budget mặc định hay số đo chi phí thật.

| Bước | Kết quả thực tế |
|---|---|
| Login student | HTTP 200, token che khi lưu |
| POST /ask lần 1 | HTTP 200; mock usage ghi 2 input tokens, 34 output tokens, cost 0,000021 USD |
| POST /ask lần 2 | HTTP 402, Daily budget exceeded; used_usd 0,000021, budget_usd 0,000001 |
| GET /me/usage | requests = 1, budget_remaining_usd = 0 |

**Kết luận từ phép thử:** mẫu chặn request tiếp theo khi chi phí đã ghi nhận vượt budget. Request đầu vẫn có thể vượt budget vì chỉ kiểm tra chi phí cũ, chưa cộng dự toán của request sắp chạy. Không khẳng định đây là hard cap tuyệt đối.

Bằng chứng: mục `cost_experiment` trong [jwt-rate-cost-results.json](reports/part4/jwt-rate-cost-results.json) và [cost-experiment-server.log](reports/part4/cost-experiment-server.log). Các số token/chi phí trên là dữ liệu mô phỏng từ lần chạy thật, không phải dữ liệu LLM thật.

**Giải thích thiết kế Redis cho bài toán 10 USD/tháng trong Exercise 4.4:**

- Tạo key theo user và tháng, ví dụ `budget:<user_id>:<YYYY-MM>`, chọn tháng theo UTC nhất quán. Sang tháng mới dùng key mới; TTL dọn dữ liệu cũ.
- Trước gọi LLM, tính estimated_cost dựa trên input và giới hạn output, kiểm tra `used + reserved + estimated_cost <= 10`.
- Thực hiện kiểm tra và reserve nguyên tử bằng Redis Lua hoặc transaction có retry để request song song không cùng vượt kiểm tra. Mẫu GET rồi INCRBYFLOAT riêng lẻ không đảm bảo điều này.
- Sau response, ghi chi phí thực tế, đối soát phần reserve; xử lý lỗi, timeout và retry bằng request ID để tránh tính trùng hoặc giải phóng nhầm. Nếu cần hard cap, phải có giới hạn token phù hợp với khoản đã reserve.
- Không lưu bộ đếm chỉ trong RAM khi chạy nhiều worker; cần chính sách persistence và không tự reset budget chỉ vì server restart.

Theo CHECKPOINTS K5, Part 4 chạy ví dụ và giải thích cost guard; ở đây giữ nguyên code mẫu. Chưa triển khai Redis budget vào app Part 4 và không nhận đó là kết quả đã có. Việc tích hợp vào code TODO của Part 6 là công việc sau.

### Tự đánh giá Part 4 / CP3

| Tiêu chí | Điểm tự đánh giá | Bằng chứng |
|---|---:|---|
| 4.1 API key | 2/2 | Ba file thực nghiệm 401, 403, 200 và giải thích rotate |
| 4.2 JWT | 2/2 | Login, gọi API thành công và kiểm tra quyền student |
| 4.3 Rate limit | 2/2 | Đủ 20 response, quan sát 429, giải thích thuật toán và role |
| 4.4 Cost guard (theo hướng dẫn K5) | 2/2 | Đọc/giải thích code, thí nghiệm 402 thật với budget mock nhỏ; giải thích thiết kế Redis |

**Tự đánh giá 8/8**, không phải điểm chính thức. Không suy ra agent đã production-ready hoặc đạt Part 6 từ kết quả này.

Chạy lại từ gốc repo trong Ubuntu:

```bash
source ~/venvs/day14/bin/activate
python -m pip install -r 04-api-gateway/production/requirements.txt
python scripts/run_part4.py
```

Script dùng cổng 8004/8005, lưu lại JSON/log (ghi đè bằng lần chạy mới), tự dừng hai server do nó tạo. Nội dung mock và chi phí mô phỏng có thể thay đổi giữa các lần chạy; cần đối chiếu lại số liệu trong bài làm nếu chạy lại.

## Part 5: Scaling & Reliability — CP4

### Môi trường và bằng chứng

AI trực tiếp chạy theo yêu cầu tiếp tục lab: Ubuntu WSL2, Python 3.14.4 ở host; agent Docker dùng Python 3.11 theo Dockerfile. Đã cài requirements develop, có psutil 6.0.0. Server develop dùng port 8006; stack production có tên project `k5-day14-scaling`, publish loopback port 18085 vì host 8080 đang được ứng dụng khác dùng.

File tổng hợp: [results.json](reports/part5/results.json). Lần chạy bắt đầu 26/11/2026 15:54:16 GMT+7; các thời lượng bên dưới lấy từ monotonic clock trong script, không lấy ví dụ của README làm số đo.

### Exercise 5.1: Health check và readiness

- **Liveness `/health`:** cho biết process đang phục vụ; orchestrator có thể dùng probe đã cấu hình để quyết định phục hồi. Develop còn báo memory hệ thống bằng psutil, không phải riêng RAM của process hay container.
- **Readiness `/ready`:** cho biết instance có thể nhận tải; develop dùng cờ `_is_ready`, production kiểm tra `_redis.ping()` khi kết nối Redis lúc import thành công.
- **Kết quả develop:** GET /health = 200, body status ok, memory used_percent 9,2%; GET /ready = 200, ready true. `in_flight_requests = 1` ở /ready gồm cả request probe đang được middleware đếm, không phải bằng chứng có một user request khác.
- **Kết quả production qua Nginx:** GET /health = 200, storage redis, redis_connected true; GET /ready = 200.
- **Chưa thử readiness 503 khi Redis mất kết nối.** Đọc code thấy production sẽ raise 503 nếu USE_REDIS true rồi ping thất bại. Nếu Redis lỗi ngay lúc import, mẫu fallback in-memory và /ready vẫn có thể 200; chưa thể coi đây là kiểm tra dependency chặt chẽ cho production thật.

### Exercise 5.2: Graceful shutdown

AI khởi động nguyên bản `develop/app.py` với PORT=8006, gửi `POST /ask?question=hello` trong thread riêng. Sau khi gửi và chờ 0,5 giây, xác nhận request chưa xong và `/proc/<pid>/wchan` là `hrtimer_nanosleep` (mock đang sleep). Sau đó gửi **SIGTERM thật** tới đúng PID server do script tạo.

| Phép đo | Giá trị thực nhận |
|---|---|
| Request còn pending lúc gửi SIGTERM | true |
| HTTP response của request đó | 200, có answer mock |
| Thời gian từ gửi request tới nhận xong response | 3,027603 giây |
| Thời gian từ SIGTERM tới process thoát | 2,741570 giây |
| Exit code | 0 |

Log ghi `Shutting down`, request POST trả 200, `Waiting for application shutdown`, `Shutdown complete`, `Finished server process`. Bằng chứng: [develop-server.log](reports/part5/develop-server.log) và [health-shutdown.json](reports/part5/health-shutdown.json).

**Giải thích:** SIGTERM cho server cơ hội hoàn thành request và cleanup; SIGKILL không thể được ứng dụng bắt để cleanup. Uvicorn điều phối shutdown; cờ ready của mẫu được đổi trong lifespan shutdown, nên không tự khẳng định endpoint /ready sẽ còn phục vụ và trả 503 ngay tại thời điểm nhận SIGTERM. Mock dùng time.sleep trong async handler nên block event loop; phép thử một request không chứng minh xử lý tải đồng thời tốt. Đây là phép thử chức năng shutdown, không phải load benchmark.

### Exercise 5.3: Stateless design

App production không dùng RAM của từng instance làm kho session chính khi Redis kết nối được:

- `save_session` dùng Redis SETEX với key `session:<session_id>`, TTL 3600 giây.
- `load_session` đọc GET từ Redis; `append_to_history` ghi user/assistant vào session.
- Các request tiếp theo gửi cùng session_id; instance nào nhận cũng đọc được session chung.
- Giữ tối đa 20 message. Mock hiện chỉ dùng câu hỏi hiện tại để trả lời, không thực sự dùng lịch sử làm ngữ cảnh LLM.

State trong RAM riêng từng instance sẽ không có ở instance khác và mất khi process restart. Dùng Redis cho phép chia sẻ state, nhưng **độ bền còn phụ thuộc Redis**: Compose mẫu Part 5 không mount volume Redis hoặc cấu hình persistence đầy đủ, nên không khẳng định dữ liệu còn sau khi xóa container Redis. Read-modify-write JSON hiện chưa nguyên tử: request đồng thời cùng session có thể ghi đè lịch sử, phép thử này gửi tuần tự.

### Exercise 5.4: Load balancing

Sơ đồ stack thực chạy:

```text
Client -> 127.0.0.1:18085 -> Nginx:80 -> agent:8000 (3 container)
                                                   |
                                                   v
                                               Redis:6379
```

Nginx dùng upstream `agent:8000`; Docker DNS phân giải service name ra các replica. Nginx phân phối request qua các upstream, thêm header X-Served-By. Đây là scale ngang 3 container, khác với 2 worker trong một container của Part 2.

AI đã chạy trong `05-scaling-reliability/production/`:

```bash
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
```

`compose ps` xác nhận **3 agent healthy, Redis healthy, Nginx Up**, cổng 18085. Bằng chứng [compose-up.txt](reports/part5/compose-up.txt), [compose-ps.txt](reports/part5/compose-ps.txt), [compose-ps.json](reports/part5/compose-ps.json), [compose-logs.txt](reports/part5/compose-logs.txt).

### Exercise 5.5: Test stateless

Đã chạy script có sẵn `test_stateless.py` với BASE_URL trỏ tới cổng 18085; chỉ sửa script để đọc BASE_URL từ env, giữ mặc định cũ 8080. Không sửa logic bài kiểm tra hoặc app. Output [test-stateless.txt](reports/part5/test-stateless.txt) có 5 request, **3 instance khác nhau** và **10 message history**.

Vì script mẫu in câu thành công mà chưa assert đầy đủ, `scripts/run_part5.py` kiểm tra thêm bằng HTTP thực với session riêng:

- 5 POST /chat liên tiếp cùng session_id đều HTTP 200, storage redis.
- served_by xuất hiện cả `instance-36901c`, `instance-73ee8b`, `instance-7eb1e8`.
- GET history = 200; count đúng 10; đủ 5 câu user đúng thứ tự.
- Các response/header/history nguyên văn nằm trong `results.json`.

**Giới hạn:** script mẫu không tự kill instance, và lần này cũng chưa thực hiện thí nghiệm kill/failover; không nhận kết quả chia sẻ session là chứng minh chịu lỗi khi instance chết. Trường `turn` của mẫu trả 2–6 cho 5 lượt vì đã thêm câu hỏi hiện tại rồi đếm +1; khi kiểm tra tính đầy đủ, dùng history và số message, không dùng turn sai lệch đó.

### Tự đánh giá Part 5 / CP4

| Tiêu chí | Điểm tự đánh giá | Bằng chứng |
|---|---:|---|
| 5.1 Health/readiness | 2/2 | HTTP 200 thật ở hai endpoint, giải thích khác biệt và giới hạn |
| 5.2 Graceful shutdown | 2/2 | SIGTERM khi request pending, response 200, exit 0 |
| 5.3 Stateless | 2/2 | Code Redis session và HTTP xác nhận storage redis |
| 5.4 Load balancing | 1/1 | 3 agent healthy và cả 3 served_by xuất hiện |
| 5.5 Test stateless (theo CP4 K5) | 1/1 | Script có sẵn exit 0, kiểm tra độc lập đủ 10 message |

**Tự đánh giá 8/8 theo hướng dẫn K5**, không phải điểm chính thức. Chưa chấm Part 6.

Sau khi thu bằng chứng, đã lưu log rồi chạy `docker compose -p k5-day14-scaling down`, exit 0; file [compose-down.txt](reports/part5/compose-down.txt) ghi dọn stack. Muốn chạy lại từ gốc repo trong Ubuntu:

```bash
source ~/venvs/day14/bin/activate
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
cd ../..
python scripts/run_part5.py
cd 05-scaling-reliability/production
docker compose -p k5-day14-scaling down
```

Lần chạy lại sẽ ghi đè file report; phải cập nhật bài làm nếu số đo thay đổi.

## Part 6: Final Project — CP5

### Phạm vi và thiết kế đã triển khai

Làm trực tiếp trong `06-lab-complete/`, giữ nguyên script chấm và golden dataset. Chọn Render cho cấu hình cloud. Môi trường host Part 6 là Python Linux 3.11.18 trong `~/venvs/day14-part6`, vì requirements pin Pydantic 2.9.0; không đổi môi trường Python 3.14 của các bài trước.

| File | Phần đã hoàn thiện |
|---|---|
| app/config.py | Đọc PORT, ENVIRONMENT, AGENT_API_KEY, REDIS_URL, RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD, REDIS_KEY_PREFIX; kiểm tra giá trị số, không có API key mặc định |
| app/auth.py | Đọc X-API-Key, so sánh constant-time; thiếu/sai hoặc chưa cấu hình đều 401 |
| app/redis_client.py | Client lazy, timeout kết nối/read 1 giây; không ping lúc import; mất Redis không chặn startup |
| app/rate_limiter.py | Sliding window 60 giây, Lua nguyên tử trên sorted set, key là SHA-256 của API key; 429 kèm Retry-After |
| app/cost_guard.py | Budget tổng theo ngày UTC, tiền nguyên nano-USD; reserve trước gọi LLM, settle/release nguyên tử và idempotent bằng Lua |
| app/main.py | /health 200 độc lập Redis; /ready 503 khi Redis lỗi; /ask validation JSON, gắn auth/rate/budget; log JSON và request ID; lifespan cleanup |
| Dockerfile | Multi-stage python:3.11-slim, user non-root, HEALTHCHECK theo PORT, exec Uvicorn PID 1, 2 worker |
| docker-compose.yml | Agent + Redis, optional .env, port host 18006, Redis AOF + volume + noeviction, healthcheck và stop grace |
| .dockerignore, .env.example | Loại secret/cache/venv/Part 7 khỏi build context; đủ biến env, key để trống |
| render.yaml | Web Docker từ rootDir 06-lab-complete và Key Value Redis, /health, key generateValue, REDIS_URL lấy connectionString nội bộ |

**Vì sao handler /ask là def:** mock LLM dùng time.sleep. Handler đồng bộ được FastAPI đưa vào threadpool, không chặn event loop của worker như async handler gọi trực tiếp hàm blocking. Giữ signal handler của Uvicorn để drain request rồi lifespan mới đóng client Redis.

**Budget:** dự toán input token mock và output tối đa từ bảng mock có sẵn, reserve toàn bộ trước gọi; sau response chỉ ghi phần thực dùng. Giá/token là hằng giả lập của lab, không phải giá hay hóa đơn nhà cung cấp thật. Budget rất nhỏ có thể trả 402 ngay request đầu, tránh gọi rồi mới vượt ngân sách. Reservation thuộc key ngày cũ để request đi qua nửa đêm vẫn settle đúng ngày. Nếu process crash sau reserve, phần giữ chỗ tồn tại đến expiry: chọn fail closed, có thể giảm ngân sách khả dụng trong ngày nhưng không tự reset khi restart.

### Kiểm thử thực tế

1. **Baseline trước sửa:** script static nguyên bản ghi 0/12; [baseline-static.txt](reports/part6/baseline-static.txt).
2. **Test trước triển khai:** [tests-red.txt](reports/part6/tests-red.txt) ghi thất bại do thiếu route/auth/validation và các hàm TODO. Có 4 failures, 4 errors do chức năng/interface chưa có; không coi lỗi này là test đã pass.
3. **Sau triển khai:** unittest 9/9 pass trong WSL2; [tests-green.txt](reports/part6/tests-green.txt). Các test bao gồm HTTP auth/input/health/readiness, Redis outage thật qua client trỏ cổng không có server, tranh chấp rate/budget với Redis thật, trả lại reserve, settle không tính trùng, JSON escape dấu nháy/newline. Test dùng Redis cô lập, không dùng dữ liệu Redis cloud.
4. **Script chấm đầy đủ nguyên bản:** `python check_production_ready.py` exit 0, **PASS 12/12, 42/42 checks**. Có runtime hai worker, restart vẫn bị 429, Redis down /health 200 /ready 503, cost 402, log JSON, SIGTERM không cắt request, build/chạy Docker và stop exit 0.
5. **Compose thực tế:** scripts/run_part6_compose.py tạo key ngẫu nhiên trong RAM, chạy stack local, kiểm tra [200, 200, 401, 401, 200] tương ứng health/ready/ask thiếu key/ask sai key/ask đúng key. Key và Config.Env không được ghi ra report.

File bằng chứng: [production-check.txt](reports/part6/production-check.txt), [compose-results.json](reports/part6/compose-results.json), [compose-ps.txt](reports/part6/compose-ps.txt), [compose-logs.txt](reports/part6/compose-logs.txt).

| Số đo Compose thật | Kết quả |
|---|---:|
| Docker image size | 249.239.205 byte = 249,24 MB thập phân, khoảng 237,69 MiB |
| User | agent, UID 999 (non-root) |
| PID 1 | Uvicorn, port 8000, 2 workers |
| Stop exit code | 0 |
| Thời gian dừng agent qua Compose | 0,936957 giây |

Script chấm ghi kích thước làm tròn 238 MB nhưng phép chia thực tế dùng 1024², tức MiB; số byte Compose là dữ liệu chính xác hơn. Các thời lượng là của lần chạy đã lưu, không phải cam kết latency/SLO production.

### Checklist Deliverable từ output script chấm

```text
📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 42/42 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

**Phân biệt với CP6:** tiêu chí Public URL ready của script kiểm tra file cấu hình. **Chưa deploy lên Render, chưa có URL public, chưa đặt secret trên Render.** Chưa chốt đủ 60/60 Part 6 vì nhóm Deployment còn cần bằng chứng cloud thật. Render Blueprint đã chuẩn bị; free Key Value không đảm bảo persistence qua restart của dịch vụ theo tài liệu nền tảng, cần đối chiếu khi triển khai.

### Chạy lại trong Ubuntu

```bash
source ~/venvs/day14-part6/bin/activate
cd /mnt/e/ai_thuc_chien/day_14_thuc_hanh/K5-L3B-DAY14-VuXuanHieu-2A202603860-Deployment-Benchmark-Observability/06-lab-complete
python check_production_ready.py
```

Grader tự tạo/dọn Redis tạm nếu chưa cung cấp REDIS_URL. Integration unittest bổ sung cần Redis test riêng ở 127.0.0.1:18086/15 và `requirements-dev.txt`. Script Compose nằm ở `scripts/run_part6_compose.py`, dùng project k5-day14-part6, port host 18006, tự dọn container/network nhưng giữ volume Redis. Không chạy down -v nếu muốn giữ state local.

## AI log

### Part 1 — 26/11/2026 (GMT+7)

- **Yêu cầu gửi AI:** đọc tiêu chí, hỗ trợ hoàn thiện lab bắt đầu từ Part 1; không bịa số đo.
- **Nội dung AI hỗ trợ:** đọc README, RULES, CHECKPOINTS, SUBMISSION, RUBRIC, INSTRUCTOR_GUIDE và code Part 1; phân tích anti-patterns, so sánh hai bản, viết câu trả lời và script thu bằng chứng HTTP.
- **Thao tác do AI thực hiện trên máy:** tạo `.venv`, cài dependency pin của repo; chạy hai app nguyên bản, gửi HTTP request thật, lưu JSON/log; giữ nguyên code mẫu và script chấm. Lần chạy trong sandbox timeout; lần chạy ngoài sandbox có kết quả HTTP. Script thu bằng chứng được chỉnh để kiểm tra listener thay vì bind cổng, dùng cổng riêng cho hai app, dọn cây process trên Windows và in console bằng ASCII để tránh lỗi encoding. Lần chạy cuối exit code 0.
- **Bằng chứng hiện hành:** `reports/part1/http-results.json` và hai log server do lần chạy của học viên trong Ubuntu WSL2 cập nhật; lệnh `python scripts/run_part1.py` từ gốc repo sau khi kích hoạt `~/venvs/day14`. AI đã đọc lại file trên ổ E và đối chiếu với kết quả học viên gửi.
- **Giới hạn:** chưa thử SIGTERM khi có request đang chạy, chưa có benchmark. Không nhận các kết quả chưa chạy là đã đạt.
- **Học viên tự sửa/tự kiểm tra:** học viên đã cài Ubuntu WSL2 và công cụ, tự tạo/kích hoạt môi trường Python Linux, cài dependency, tự chạy `python scripts/run_part1.py` và gửi output lúc 14:59:53 GMT+7. Kết quả 8 HTTP check khớp file JSON trên ổ E. Chưa xác nhận học viên tự chỉnh code hay đã giải thích được toàn bộ nội dung; cần đọc và hiểu câu trả lời trước khi nộp.

### Part 2 — 26/11/2026 (GMT+7)

- **Yêu cầu/tiến độ:** học viên tiếp tục Docker sau Part 1, tự build image develop rồi gửi output chạy container và gọi API.
- **AI hỗ trợ:** đọc Dockerfile/app develop và Dockerfile production; giải thích cấu trúc Dockerfile, hướng dẫn chạy/test, tổng hợp câu trả lời Exercise 2.1 và bằng chứng 2.2; phân tích code multi-stage cho 2.3.
- **Học viên tự kiểm tra:** bật WSL Integration cho Ubuntu, thêm tài khoản vào nhóm docker, mở phiên Ubuntu mới, chạy hello-world thành công, build `my-agent:develop`, chạy `day14-develop`, kiểm tra docker ps, gọi /health và /ask đều 200, gửi server log.
- **Cập nhật Exercise 2.3:** học viên đã build image advanced, gửi bảng Docker và số byte inspect của hai image. AI tính mức giảm 85,62% từ số byte và cập nhật báo cáo.
- **Giới hạn:** bằng chứng Part 2 hiện lấy từ output học viên gửi, không ghi nhận là AI tự chạy. Chưa có kết quả chạy advanced/Compose; không điền số ước lượng.

- **Xử lý lỗi Compose Part 2:** học viên gửi lỗi publish host port 80 khi Nginx khởi động. AI đổi mapping host sang loopback 8080 và bỏ publish 443 chưa cấu hình TLS; chưa có kết quả chạy lại, không ghi nhận đã sửa thành công.

- **Chẩn đoán tiếp lỗi port Part 2:** lần đổi sang 8080 vẫn lỗi. AI kiểm tra trực tiếp Windows bằng Get-NetTCPConnection và netsh: cổng 80 thuộc dải excluded 80–80 và có listener PID 4; cổng 127.0.0.1:8080 thuộc PID 25660, process `chat24-api`. Thử TcpListener bind loopback 18080 thành công rồi đóng ngay. Đã đổi mapping hiện hành thành `127.0.0.1:18080:80`; chưa xác nhận Docker publish thành công, cần học viên chạy lại và gửi output. Không dừng ứng dụng đang sử dụng 8080.

- **Cập nhật Exercise 2.4:** học viên gửi POST /ask qua localhost:18080 trả HTTP 200, Server nginx, thời gian header 08:32:13 GMT ngày 26/11/2026. AI ghi response, sơ đồ 4 service và giới hạn mock chưa dùng Redis/Qdrant; cần bổ sung Compose ps và GET /health sau khi đổi port.

- **Hoàn tất bằng chứng Exercise 2.4:** học viên tự lưu ba file compose-ps.txt, nginx-health.txt, nginx-ask.txt trong reports/part2. AI đã đọc file và xác nhận 3 service healthy, Nginx Up, cả health và ask HTTP 200 qua Nginx; cập nhật đánh giá Part 2 là 8/8 (tự đánh giá). Không nhận uptime là latency và không coi mock response là chứng minh deployment cloud.

### Part 4 / CP3 — Exercise 4.1, 26/11/2026 (GMT+7)

- **AI hỗ trợ:** đọc app develop và các module auth/rate_limiter/cost_guard production; hướng dẫn chạy API key demo, dùng hai terminal và lưu ba tình huống HTTP; giải thích verify_api_key, hành vi 401/403/200 và rotate key.
- **Học viên tự kiểm tra:** tự khởi động app develop trên WSL2, mở terminal thứ hai và chạy curl, lưu response bằng tee vào reports/part4. AI đã đọc ba file thực tế, kiểm tra mã HTTP và JSON body.
- **Giới hạn:** mới hoàn thành kiểm tra API key; chưa thử JWT/rate limit/budget. Không coi key demo là secret thật hoặc nhận kết quả chưa chạy là đã đạt.

### Part 4 / CP3 — Exercise 4.2–4.4, 26/11/2026 (GMT+7)

- **Yêu cầu:** học viên hỏi AI chạy hộ; AI trực tiếp thực hiện các bước tiếp theo.
- **AI thực hiện:** kiểm tra server develop trên 8000, cài PyJWT trong ~/venvs/day14, tạo script thu bằng chứng và chạy trong Ubuntu WSL2. Production test dùng cổng riêng 8004; cost experiment dùng 8005 và budget mock 0,000001 USD/user/ngày. Chỉ đặt budget trong RAM của process thí nghiệm, không sửa app nguồn. Không lưu token/signing secret.
- **Kết quả:** JWT thiếu 401, login sai 401, login đúng 200, gọi có JWT 200, student vào admin 403. Vòng 20 request có 9 HTTP 200 và 11 HTTP 429 sau một /ask thành công trước đó. Cost experiment /ask lần 1 là 200, lần 2 là 402, usage ghi requests 1.
- **Nguồn:** reports/part4/jwt-rate-cost-results.json và hai server log; script exit code 0. Lần chạy được ghi run_at 2026-11-26T15:49:37.499938+07:00. Chi phí/token là giả lập, không phải hóa đơn LLM thật.
- **Học viên tự kiểm tra:** học viên tự làm 4.1; 4.2–4.4 do AI chạy. Chưa ghi nhận học viên tự chạy lại hoặc giải thích được JWT, sliding window và cost reserve. Học viên cần đọc và nắm phần giải thích trước khi nộp.

### Part 5 / CP4 — 26/11/2026 (GMT+7)

- **Yêu cầu:** tiếp tục phần kế tiếp sau CP3; AI trực tiếp chạy bài trong môi trường đã được học viên cho phép.
- **AI hỗ trợ/thực hiện:** đọc tiêu chí, app và script mẫu; cài requirements develop vào Python WSL2, đổi host port Compose 8080 thành loopback 18085 vì ứng dụng khác dùng 8080, bổ sung env BASE_URL cho test_stateless.py, tạo scripts/run_part5.py để thu bằng chứng. Khởi động 3 replica, chạy script mẫu và kiểm tra HTTP độc lập; thử SIGTERM thật khi request mock đang sleep; lưu report/log rồi dọn đúng stack lab.
- **Kết quả thực tế:** health/ready đều 200, pending request hoàn thành 200 sau SIGTERM, process exit 0; 3 agent healthy và đủ 10 message cho session 5 lượt qua 3 instance. Số thời gian và response lấy từ reports/part5/results.json, không lấy số mẫu.
- **Giới hạn:** chưa thử kill instance/failover hoặc Redis down; không chứng minh Redis bền vững sau xóa container. Phân tích được ghi về fallback in-memory, turn lệch, blocking mock và nguy cơ read-modify-write đồng thời. Không thay code app mẫu để che giới hạn.
- **Học viên tự kiểm tra:** phần này do AI chạy, chưa ghi nhận học viên tự chạy lại hay đã nắm toàn bộ lời giải. Cần đọc và giải thích được health/readiness, SIGTERM, stateless và bằng chứng history trước khi nộp.

### Part 6 / CP5 — 26/11/2026 (GMT+7)

- **Yêu cầu:** học viên yêu cầu thực hiện phần tiếp theo sau phương pháp Part 6 đã thống nhất; chọn cấu hình Render theo hướng triển khai đã trao đổi.
- **AI thực hiện:** đọc code TODO/hợp đồng/rubric/checker; lưu baseline 0/12, viết kế hoạch, tạo môi trường Python 3.11 Linux riêng bằng uv; cài đúng requirements; viết test trước rồi hoàn thiện config/auth/Redis/rate/cost/main, Docker/Compose/dockerignore/env/Render. Không sửa script chấm hay golden dataset.
- **Kết quả:** unittest 9/9, grader đầy đủ PASS12/12 42/42, Compose smoke có HTTP200/401 đúng kỳ vọng, image249239205 byte, nonroot UID999, Uvicorn PID1 và stop exit0 trong0,936957giây. Số liệu lấy từ output/file đã chạy thật. Toàn bộ chi phí LLM là giả lập.
- **Nguồn:** reports/part6/baseline-static.txt, tests-red.txt, tests-green.txt, production-check.txt, compose-results.json và log. JWT/API secret không ghi vào artifact.
- **Học viên tự sửa/tự kiểm tra:** Part 6 do AI triển khai và chạy, chưa ghi nhận học viên tự chạy lại hay giải thích được code. Học viên cần nắm Redis Lua/sliding window/reserve budget/JSON logging/lifespan trước khi nộp.
- **Giới hạn:** local PASS không chứng minh deploy cloud. Render chưa được tạo, chưa có URL/secret cloud; CP6 còn phải làm. Reservation crash fail closed đến TTL; mô hình giá/token chỉ phục vụ lab.

- **Review độc lập Part 6:** reviewer đọc app/tests/Docker/Compose/Render, không phát hiện critical/important ảnh hưởng hợp đồng lab. Minor ghi nhận: unexpected error có thể thiếu request JSON log/X-Request-ID và Uvicorn có thể ghi traceback; cần rà soát trước khi thêm provider thật. Reservation crash còn giữ đến TTL là tradeoff fail closed đã ghi. Không tuyên bố đã sửa hai giới hạn này.
- **Tài liệu:** cập nhật hướng dẫn chạy trong 06-lab-complete/README.md; tạo DEPLOYMENT.md trạng thái chưa deploy để chuẩn bị CP6. Không tạo URL giả, không push GitHub hoặc tạo tài nguyên cloud trong CP5.
