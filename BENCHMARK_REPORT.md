# Benchmark & Observability Report — Day 14

**Họ tên:** Vũ Xuân Hiếu — 2A202603860

**Ngày chạy:** 26/11/2026 (GMT+7)
**Môi trường:** Ubuntu WSL2, Python Linux 3.11.18, cùng máy chạy client và agent. Tài nguyên Docker Desktop đo được ở mục 4.1. Tất cả LLM/token/cost là mock; không phải hiệu năng hay hóa đơn của model thật.

## 1. SLO của agent

| SLI | SLO | Lý do |
|---|---|---|
| p95 /ask | ≤500 ms | Theo ngưỡng mặc định load_test.py; kiểm tra trải nghiệm phần lớn request |
| Error rate /ask | ≤2% | Theo load_test.py; chấp nhận lỗi mock nhưng không che lỗi khi tải cao |
| Accuracy golden dataset | ≥80% ban đầu; final v2 đạt100% không regression | Chặn giảm chất lượng và hoàn thành yêu cầu K5 23/23 |

Đây là ngưỡng mục tiêu lab, không được suy ra là SLO phù hợp cho mọi sản phẩm. Latency load_test.py chỉ tính request HTTP200; RPS và error rate tính toàn bộ request, bao gồm lỗi kết nối nếu có.

## 2. Benchmark hiệu năng — develop

### 2.1 Concurrency vs latency (v2)

Mỗi mức300 request, warm-up không tính, MOCK_ERROR_RATE=0.01, MOCK_SLOW_RATE=0.03, mock-llm-small. Chạy trước khi sửa KB; câu hỏi load_test.py không chứa hai chủ đề KB đã sửa. Client/agent cùng máy, kết quả chịu ảnh hưởng tài nguyên và chi phí client/logging/WSL, không phải benchmark hạ tầng độc lập.

| Concurrency | RPS | p50 ms | p95 ms | p99 ms | Error rate | SLO |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4.32 | 194.4 | 224.1 | 1690.9 | 0.67% | PASS |
| 10 | 39.39 | 194.1 | 224.3 | 1666.8 | 0.67% | PASS |
| 50 | 80.97 | 368.7 | 1355.3 | 1903.5 | 0.33% | FAIL |
| 100 | 19.24 | 4071.2 | 9320.0 | 13262.4 | 2.67% | FAIL |

RPS tăng từ concurrency1 lên10 và50 nhưng không tuyến tính; ở100 giảm mạnh trong khi p95 tăng. Kết quả cho thấy áp lực tải phía client/server dùng chung máy, không đủ bằng chứng để quy riêng cho LLM hay CPU. Cần quan sát CPU, event loop, I/O log và connection pool để kết luận nút thắt. Giữ nguyên kết quả FAIL, không chạy lại để lựa số đẹp.

### 2.2 Tail latency

300 request mỗi mức, concurrency20; khởi động lại agent cho từng MOCK_SLOW_RATE, giữ MOCK_ERROR_RATE=0.01.

| MOCK_SLOW_RATE | avg ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| 0 | 205.9 | 245.9 | 268.1 |
| 0.03 | 259.1 | 255.3 | 1711.9 |
| 0.1 | 355.8 | 1683.2 | 1715.6 |

Tăng tỉ lệ slow làm tail latency tăng; ở0.1, hơn5% request có thể chậm nên p95 cũng chịu ảnh hưởng lớn. Average pha loãng nhóm chậm với nhiều request nhanh; p95/p99 thể hiện trải nghiệm nhóm đuôi. Tỉ lệ được inject theo xác suất, mẫu300 có dao động, không đồng nhất cấu hình0.03 với đúng9 request slow trong mọi lần chạy.

## 3. Benchmark chất lượng

Eval dùng MOCK_ERROR_RATE=0, MOCK_SLOW_RATE=0 cho cả ba phiên bản để tách lỗi tri thức khỏi lỗi upstream. Không thay golden_dataset.jsonl, ngưỡng keyword0.6 giữ nguyên. V1 và v2 trước sửa được lưu trước khi chỉnh KB; v2 đã tắt/bật lại sau sửa. Eval latency có mẫu nhỏ23, không dùng để kết luận latency production.

| Chỉ số | v1 | v2 trước sửa | v2 sau sửa |
|---|---:|---:|---:|
| Accuracy | 4.35% | 91.30% | 100.00% |
| Avg tokens/câu | 57.1 | 108.8 | 114.4 |
| Tổng cost USD mock | 0.000405 | 0.000757 | 0.000797 |
| Cost/câu đúng USD mock | 0.00040455 | 3.607e-05 | 3.466e-05 |
| Quality gate | FAIL | PASS | PASS |

| ID sai trước sửa | Keyword thiếu | Cách sửa |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Bổ sung entry JWT: token chứa thông tin, kiểm tra chữ ký/hạn dùng; payload không mã hóa mặc định |
| scaling-03 | cpu, memory, custom metrics | Bổ sung entry HPA giải thích autoscale replica theo CPU/memory/custom metrics |

Đã chép thay đổi KB sang cả production để stack có cùng kiến thức. V2 sau sửa **23/23**, score trung bình1.0, không regression. V2 tốn thêm token do retrieval nhưng cost/câu đúng giảm nhiều so với v1; chọn model/phiên bản bằng chất lượng đáp ứng nhu cầu và chi phí trên câu đúng thay vì chỉ cost/câu.

**Quality gate CI:** chạy `python eval/run_eval.py --url <agent-test> --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json`. Exit0 khi đạt accuracy và không regression; exit1 khiến job CI thất bại, branch protection yêu cầu job đó pass trước merge. Không dùng `continue-on-error: true` hoặc bỏ qua exit code. Đã chạy đối chứng v1 với baseline v2: exit1 và regression được ghi trong reports/eval_v1_regression.json. Đây là thực nghiệm local về gate, chưa tuyên bố đã cấu hình branch protection/GitHub Actions trên GitHub.

Bằng chứng root reports/: load_v2_c1/c10/c50/c100.json, load_v2_slow_0/0.03/0.1.json, eval_v1.json, eval_v2.json, eval_v2_fixed.json. Lệnh/exit code ở reports/part7/commands.jsonl, log và môi trường ở reports/part7/. Các giá trị trong bảng lấy trực tiếp từ JSON này.

## 4. Observability stack — production

### 4.1 Kiến trúc, cấu hình và ảnh

Locust -> Nginx -> agent replica; Prometheus scrape từng agent mỗi5giây qua Docker DNS, Grafana query Prometheus, OTel gửi OTLP tới Jaeger. Một worker mỗi container để metric không bị phân mảnh giữa worker. Docker Desktop29.9.3, x86_64,12CPU, MemTotal16.608.137.216byte (khoảng15,47GiB); mỗi agent giới hạn0,5CPU/256MB theo Compose. Tài nguyên thực: reports/part7/docker-resources.json.

Các URL local đã đổi tránh xung đột và chỉ bind loopback: agent18087, Grafana13000, Prometheus19090, Jaeger16686, Locust18089, OTLP14318. Auth dùng key demo day14-lab-key theo đề, không dùng key Render. Không gửi tải hoặc chaos tới dịch vụ cloud.

- [x] [Grafana khi đang có tải](screenshots/grafana-dashboard.png):3instance, error khoảng20%, p95 khoảng1,90s trong thí nghiệmAB.
- [x] [Jaeger trace chậm](screenshots/jaeger-slow-trace.png):timeline và span chat mock-llm-large.
- [x] [Jaeger trace lỗi](screenshots/jaeger-error-trace.png):HTTP503, event exception và message upstream mock.
- [x] [Prometheus Alerts](screenshots/prometheus-alert-firing.png):AgentHighErrorRate, AgentHighLatencyP95 và LLMCostBurnRateHigh cùng firing.

Ảnh lấy từ UI thật bằng browser, JPEG gốc được giữ và chuyển định dạng PNG, không thay nội dung hay vẽ lại số liệu. Prometheus API snapshot reports/part7/alerts-screenshot-state.json xác nhận3firing; không tính pending là firing. Số trên dashboard thay đổi theo thời gian, không bắt buộc trùng thống kê CSV cả cửa sổ benchmark.

### 4.2 Đọc dashboard — Exercise7.4

1. Snapshot Prometheus trước khi chuyển sang fault injection cho p95=292,51ms, avg=228,15ms (reports/part7/dashboard-readings.json); khoảng cách cho thấy phân phối có đuôi chậm, còn p99 nhìn rõ hơn. Ảnh Grafana sau đó là thời điểm chaos, p95 khoảng1,90s, không trộn hai thời điểm thành cùng một phép đo.
2. RPS theo3instance trong snapshot1phút là19,69 /20,11 /18,95req/s, khá gần nhau, phù hợp phân phối tải qua Nginx. Snapshot được thu gần lúc chuyển cấu hình, trường instances_up có thể phản ánh thế hệ target mới trong khi rate1phút còn dữ liệu thế hệ trước; bằng chứng số replica benchmark là compose ps/agent IDs và ảnh steady3instance, không dùng riêng snapshot chuyển tiếp đó để đếm replica.
3. Input tokens/s khoảng4.539,36, output khoảng2.389,64 trong snapshot. Input có system prompt, câu hỏi và retrieved context; output chỉ là đoạn trả lời, nên input lớn hơn. Token/cost vẫn là mô phỏng.
4. Gọi agent qua Nginx tại /metrics trả404, đã lưu reports/part7/metrics-public-check.json. /metrics dành cho Prometheus scrape nội bộ, không public qua gateway.

### 4.3 Alerts và chaos — kết quả thực nghiệm

Các thí nghiệm nối tiếp nhau trên cùng Prometheus nên cửa sổ1m/5m và trạng thái firing có thể kéo sang bước sau. Chỉ tính thời gian phát sinh mới nếu alert chưa firing ở đầu bước; không coi lần đầu nhìn thấy một alert đã firing là thời gian phản ứng của thay đổi mới. Poll5giây nên thời gian ghi nhận có độ phân giải khoảng5giây, còn bao gồm thời gian apply config/startup như trường timing_origin trong JSON.

AB là **thí nghiệm kết hợp**, bật error0.2 và slow0.3 cùng lúc; không dùng nó để kết luận hiệu ứng riêng của mỗi biến trên throughput. Hai điều kiện alert lỗi và latency được quan sát riêng.

| Thí nghiệm | Quan sát alert | Thời gian ghi nhận và giới hạn |
|---|---|---|
| A — error rate 0.2, chạy chung B | AgentHighErrorRate chuyển firing | 93,744 giây từ trước khi apply Compose; chưa firing ở đầu bước |
| B — slow rate 0.3, chạy chung A | AgentHighLatencyP95 chuyển firing | 153,880 giây từ trước khi apply Compose; chưa firing ở đầu bước |
| C — mock-llm-large | LLMCostBurnRateHigh vẫn firing | Đã firing trước thay đổi; lần đầu quan sát ở 8,479 giây **không phải** thời gian phản ứng mới. Không suy ra hệ số tăng cost rate từ cửa sổ lịch sử này |
| D — pause một agent | AgentInstanceDown được quan sát firing | 30,017 giây sau pause. Snapshot đầu đã có target pending do đổi thế hệ container/DNS, nên không nhận đây là phép đo độ trễ phát hiện pause độc lập |
| E — chuyển agent v1 | Trong cửa sổ 80 giây, chỉ quan sát LLMCostBurnRateHigh firing | Alert cost đã firing từ trước; lần quan sát đầu 11,916 giây không phản ánh lỗi chất lượng v1. Không có alert chất lượng mới |

Nguồn: reports/part7/chaos_AB.json, chaos_C.json, chaos_D.json, chaos_E.json; mỗi file giữ cấu hình, initial_firing, toàn bộ snapshot và exit code Locust. Tất cả pha đều dùng 30 user; AB 190 giây, C 160 giây, D/E 80 giây. Hai alert mới ở AB và ảnh có ba alert firing đáp ứng yêu cầu quan sát ít nhất hai alert. Cost lớn/small có đơn giá mock khác nhau, nhưng thời gian alert C bị lịch sử đo chi phối; muốn đo riêng phải đợi cửa sổ sạch trước khi đổi model.

Promtool với alert_rules_test.yml nguyên bản: **SUCCESS**, log reports/part7/promtool.txt. Không giảm ngưỡng hoặc for để làm đẹp thời gian firing.

**Thí nghiệm E:** đổi v1 làm retrieval/quality giảm, nhưng các alert hiện tại chỉ theo lỗi HTTP/latency/availability/cost. Không có rule accuracy; cần golden dataset eval/quality gate, canary chất lượng và phản hồi người dùng để phát hiện. Không kết luận dashboard xanh là câu trả lời đúng. Alert cũ còn firing do cửa sổ đo không chứng minh quality detection.

### 4.4 Debug bằng trace — Exercise7.5

- Trace chậm: `fbf52198aa4466503b8a991cdf2c719f`, tổng **2002.959ms**.
- Bước lá tốn thời gian nhất: **chat mock-llm-large**, **1985.922ms**, khoảng**99.15%** tổng thời gian. Wrapper agent.run bao gồm các span con, không cộng thời gian wrapper thêm lần nữa.
- Chọn trace chậm có log còn giữ và LLM-call latency lớn nhất trong các candidate từ log; không nhận đây là trace chậm nhất toàn bộ mọi request đã từng chạy.
- Dòng log JSON trùng trace_id:

```json
{"ts": "2026-11-26T10:45:48.447132+00:00", "level": "INFO", "service": "observable-agent", "instance": "90e0c064d358", "event": "llm_call", "trace_id": "fbf52198aa4466503b8a991cdf2c719f", "span_id": "454ac03285c5ce62", "request_id": "bc84c726b7e2", "model": "mock-llm-large", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 0.000788, "llm_ms": 1984.6}
```

- Trace lỗi: `a95370b20feed9bcc5f3df3f894d385e`, tổng**197.438ms**, có span LLM statusERROR và event exception mô tả mock upstream503. Log trùng trace_id:

```json
{"ts": "2026-11-26T10:46:42.595217+00:00", "level": "INFO", "service": "observable-agent", "instance": "90e0c064d358", "event": "llm_error", "trace_id": "a95370b20feed9bcc5f3df3f894d385e", "span_id": "c025809e754b16e3", "request_id": "280abdb578da", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

Dữ liệu raw OTLP v3 ở reports/part7/jaeger-slow-trace-v3.json và jaeger-error-trace-v3.json; summary cùng log ở selected-traces-for-report.json. API cũ /api/traces của bản đang chạy trả404, nên dùng GET /api/v3/traces/<id> theo [tài liệu Jaeger](https://www.jaegertracing.io/docs/2.23/architecture/apis/), ID lấy từ log thật. Thời lượng tính từ timestamp nano giây, không ước lượng từ hình UI đã làm tròn.

## 5. Benchmark scaling — Locust headless

100users, spawn10/s,120giây mỗi mức, v2/mock-small, error0.01, slow0.03, wait giữa task0,5–2giây như locustfile. **Bảng dùng riêng dòng POST /ask**, không trộn health với hỏi agent. CSV vẫn giữ đủ các dòng.

| Instance | RPS /ask | p50 ms | p95 ms | p99 ms | Failures / requests |
|---|---:|---:|---:|---:|---|
| 1 | 59.91 | 190 | 320 | 1700 | 73 / 7139 |
| 3 | 59.88 | 190 | 240 | 1700 | 74 / 7127 |

RPS gần như không đổi (~59,9req/s); p95 giảm320→240ms (25%), p99 vẫn1.700ms. Với100user và think time0,5–2s, tải được giới hạn bởi số user/vòng chờ; tăng agent không tự tăng số request được tạo. Tail1500ms của mock vẫn có ở mỗi replica, nên scale không loại bỏ nó. Chỉ từ số này không đủ kết luận CPU hoặc network là nút thắt duy nhất; cần kết hợp metrics, traces và thử tải khác.

Đã kiểm tra số agent thực sự bằng compose ps và container IDs sau mỗi mức:1và3. Locust run dùng **--no-deps** để không kéo dependency về replicas mặc định2. Lần đầu phát hiện sai số replica2 đã dừng, giữ riêng reports/part7/invalid-scale-attempt và loại khỏi bảng. Không dùng kết quả sai nhãn làm1/3benchmark. Exit1 của Locust có thể do các lỗi503 mock đã ghi trong CSV, không tự đổi thành PASS.

## 6. Kết luận và giới hạn

1. Cần đo latency bằng percentile và đánh giá cả lỗi; average hoặc dashboard xanh không đủ.
2. Quality gate bắt được regression v1/v2; sửa knowledge base cần đối chiếu golden dataset nguyên bản và không làm mất những câu đã đúng.
3. Metrics phát hiện triệu chứng; trace chỉ bước chậm; log cùng trace_id giúp đối chiếu một request cụ thể. Alert có for tránh spike nhưng cần đo độ trễ phát hiện thật.

Nếu triển khai thật, bổ sung metric lỗi/latency ở Nginx hoặc synthetic probe bên ngoài để thấy504 không đến được agent, queue depth/CPU/memory, chi phí theo tenant đã ẩn danh, và eval liên tục. Label route/status/model có cardinality thấp; không gắn user_id/question/trace_id vào label metric. Trace có thể sampling khi tải lớn nhưng sẽ có nguy cơ bỏ lỡ lỗi hiếm; ưu tiên giữ trace lỗi/chậm qua sampling thích hợp.

Prometheus pull thuận tiện service discovery và quản lý scrape; với dịch vụ scale-to-zero cần kiến trúc telemetry phù hợp, không nhận một cấu hình scrape lab là đủ cho serverless. for0s dễ alert vì spike, for30m có thể phát hiện quá muộn; chọn theo SLO và thời gian xử lý sự cố.

**Độ tin cậy phép đo:** client/server dùng chung máy WSL/Docker; mock có randomness, không có CI confidence interval hoặc repeated-run study. Mỗi số là kết quả đúng lần chạy được lưu. Giá/token/cost là giả lập, không phải phí cloud hoặc LLM thực. Chaos chỉ trên stack local riêng, không phá Render.

**Đối chiếu rubric Part 7 (tự đánh giá):** load/SLO 4/4, eval/quality gate 5/5, observability 4/4, tracing 3/3, alerts/chaos 4/4 — tổng dự kiến 20/20 theo bộ bằng chứng đã nộp. Đây không phải điểm chính thức; Lab Coach kiểm tra số liệu, chạy lại công cụ và đánh giá câu trả lời của học viên. Các kết quả SLO FAIL và giới hạn thí nghiệm đã được giữ trong báo cáo.

**Kiểm tra hồ sơ:** `scripts/verify_part7_evidence.py` đối chiếu JSON/CSV, 7 PNG, trace/log, quality gate và firing snapshot; kết quả ở reports/part7/evidence-verification.txt. Helper này cần Pillow trong môi trường kiểm tra ảnh. Script chấm/golden/load/eval/alert rules khớp commit đề 83e677f, ghi tại protected-files-check.txt. Stack local đã dọn sau khi lưu minh chứng, xem cleanup-result.json; muốn xem dashboard trực tiếp cần bật Compose lại theo cổng ở mục 4.1.
