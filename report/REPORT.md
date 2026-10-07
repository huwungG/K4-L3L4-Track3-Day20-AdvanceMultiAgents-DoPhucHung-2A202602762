# Báo cáo Lab: Self evolving Agentic

> Văn phong kỹ thuật, ngắn gọn, mọi nhận định đi kèm số liệu hoặc bằng chứng. Số liệu trích từ `results/<condition>/<task>/run.json` và `report/table.md`; tag `freeze` trỏ về `13c507a` (commit hypotheses).

## 1. Thông tin nhóm và cấu hình

| Họ tên | Mã sinh viên | Phần đóng góp |
|---|---|---|
| Đỗ Phúc Hưng | 2A202602762 | Toàn bộ |

- Nhà cung cấp và mô hình (`LAB_MODEL`, không ghi khóa API), nhiệt độ, `recursion_limit`: `openai:gpt-4o-mini`, `LAB_TEMPERATURE=0`, `recursion_limit=60`.
- Phiên bản Deep Agents, hệ điều hành, môi trường chạy: `deepagents==0.7.21`, Windows 10 19045, chạy trong container Docker `python:3.12-slim` dựng từ `Dockerfile` của lab (lý do: agent shell cần `/bin/sh` chuẩn POSIX; trên Windows PowerShell `command -v` thất bại).
- Số lần chạy tác vụ / ngân sách: 12 lần chạy chính thức (3 điều kiện × 4 tác vụ). Tổng input token: **2,783,035**; output: **62,872**; tổng **2,845,907** token; ước tính **$0.46 USD** với giá `gpt-4o-mini` ($0.15/1M in, $0.60/1M out).
- Tag `freeze`: trỏ về `13c507a` — commit hypotheses (chứa `skills/` ban đầu, README của `skills/auto`, và 3 giả thuyết H1–H3). Lệnh: `git rev-list -n 1 freeze` → `13c507a`.

## 2. Giả thuyết (commit TRƯỚC tag `freeze`, Phần 4.0)

- **H1 (subagents vs baseline):** không có khác biệt lớn, thậm chí giảm. Căn cứ: bài báo Anthropic "Building Effective Agents" ghi nhận multi-agent chỉ thực sự 4 hơn khi mỗi tác tử con có quyền truy cập thông tin KHÁC NHAU. Ở đây 3 subagent (explorer/implementer/reviewer) dùng chung filesystem và chung skill `read_file`/`write_file`/`execute`, nên isolation cắt context tích lũy mà không thêm thông tin mới. Dự đoán: token tăng mạnh (gấp 3–5×) nhưng điểm gần như không đổi, có thể còn giảm.
- **H2 (skills-auto vs baseline):** `skills-auto` cải thiện điểm trên check quy ước (`rule_*`) vì 3 skill sinh ra (avoid-common-mistakes, validate-output-structure, handle-errors-properly) đều nhắm đúng nhóm lỗi E/F mà baseline mắc. Cải thiện yếu trên check kỹ thuật (A–D) vì skill dạy kiểm tra chứ không dạy cài đặt. Căn cứ: SkillsBench (skill do người viết +16 %), SkillEvolBench (skill do LLM sinh ≈ 0 ở tác vụ mới).
- **H3 (tác vụ học vs tác vụ đánh giá):** điểm tác vụ học cao hơn tác vụ đánh giá ở cùng điều kiện, vì check quy ước của đánh giá có thể khác check lịch sử thất bại mà curator nhìn thấy — dấu hiệu quá khớp của skill do LLM sinh trên tác vụ học (SkillEvolBench).

## 3. Làm quen Deep Agents (Phần 0.3)

1. Tác tử chính nhận chỉ thị từ `runner.py` (gọi `create_deep_agent(...)` trong `src/lab/agent.py`), đính kèm system prompt, công cụ mặc định (`get_files`, `write_file`, `read_file`, `execute`, `edit_file` từ `langchain`), và danh sách `subagents` + `skills` nếu điều kiện yêu cầu. Mỗi lần invoke là một vòng lặp `Reason → Tool → Observe`; vòng lặp dừng khi model trả `TASK_COMPLETED` hoặc đụng `recursion_limit=60`.
2. Khi tác tử chính quyết định ủy thác, nó gọi công cụ nội bộ `delegate_to_<subagent_name>` kèm chỉ thị ngắn; subagent nhận `system_prompt` riêng và chạy vòng lặp độc lập trong **một context riêng** (không thấy lịch sử tool của main). Kết quả trả về là một message text được main tổng hợp vào context. Đây chính là điểm Anthropic cảnh báo: nếu các subagent không có thông tin riêng, isolation chỉ làm mất context.
3. Skills nằm trong `skills/<group>/<skill-name>/SKILL.md`; mỗi skill có YAML frontmatter (`name`, `description`) và body ≤ 80 dòng. Khi runner nạp, mô hình tự đọc danh sách tên + description và quyết định có `read_file` skill đó không. Nếu model không đọc, skill tồn tại trên đĩa nhưng **không có tác dụng** — đây là biến số quan trọng của thí nghiệm.

## 4. Đường cơ sở và phân loại lỗi (Phần 2.2)

> Mỗi dòng là một check thất bại trên **3 tác vụ học** của `baseline`. Nhóm lỗi: A = test hồi quy (suite chạy / test cũ không sửa), B = đọc/sửa theo docstring, F = tuân thủ quy ước (`rule_*`).

| Tác vụ | Check thất bại | Nhóm | Bằng chứng (trích `detail`) |
|---|---|---|---|
| code-learn | visible_suite_passes | A | `1 failed, 5 passed in 0.07s` |
| code-learn | tests_not_modified | A | `the original files in tests/ must not be modified` |
| code-learn | parse_price_all_formats | B | `wrong for: ['(12.00)']` (bỏ sót định dạng dấu ngoặc đơn) |
| code-learn | other_caller_fixed | B | `to_csv_row returned 'tv,"1299.50",1'` (chưa đóng dấu nháy đúng cách) |
| code-learn | csv_quoting_follows_docstring | B | `to_csv_row returned 'Desk, large "oak","10.00",2'` |
| code-learn | rule_type_hints | F | `every public function ... has type annotations` |
| code-learn | rule_regression_tests | F | `add tests/test_regressions.py with one test per bug` |
| code-learn | rule_changelog | F | `record each fix in CHANGELOG.md under '## Unreleased'` |
| data-learn | north_q1_revenue | B | `wrong value (got 245.28)` |
| data-learn | north_q1_orders | B | `wrong value (got 2)` |
| data-learn | missing_amount_orders | B | `wrong value (got 0)` |
| data-learn | duplicate_rows_removed | B | `wrong value (got 0)` |
| data-learn | rule_money_in_cents | F | `money values in answer.json are integer cents` |
| data-learn | rule_meta_block | F | `answer.json has an object meta = {source, rows_in, ...}` |
| data-learn | rule_clean_csv | F | `write workspace/clean.csv with header order_id,timestamp_utc,region,amount_cents` |
| logs-learn | valid_structure | B | `FileNotFoundError: .../errors.json` (không ghi file) |
| logs-learn | entry_count | B | `FileNotFoundError` |
| logs-learn | timestamps_utc | B | `FileNotFoundError` |
| logs-learn | exception_fields | B | `FileNotFoundError` |
| logs-learn | repeat_counts | B | `FileNotFoundError` |
| logs-learn | counts_by_service | B | `FileNotFoundError` |
| logs-learn | rule_service_names | F | `FileNotFoundError` |
| logs-learn | rule_sorted_errors | F | `FileNotFoundError` |
| logs-learn | rule_schema_header | F | `FileNotFoundError` |

**Nhận xét:**

- **Nhóm B (docstring / output structure) chiếm đa số** (12/24 lần thất bại riêng biệt, 50 %), gồm hai kiểu con: (i) tác vụ code bỏ sót **định dạng đầu vào** (`(12.00)`, `$1,299.50`); (ii) tác vụ data/logs **không ghi file output** đúng tên (`answer.json`, `clean.csv`, `errors.json`) — `logs-learn` fail 100 % vì agent quên ghi file.
- **Nhóm F (quy ước repo)** chiếm 9/24 lần (37.5 %) — tất cả 9 lần đều fail cùng pattern: agent không chủ động tạo `tests/test_regressions.py`, `CHANGELOG.md`, `meta` block, v.v. Đây là nhóm **dễ phòng ngừa bằng skill** (vì quy tắc ổn định, có thể liệt kê checklist).
- **Nhóm A (test)** chỉ 2 lần (8 %) — yêu cầu hiểu biết ngữ nghĩa test, khó dạy bằng skill hơn.

→ Kỳ vọng H2: 3 skill do curator sinh (`avoid-common-mistakes`, `validate-output-structure`, `handle-errors-properly`) nhắm đúng nhóm B + F, **không giúp ích** cho nhóm A.

## 5. Điều kiện `subagents` (Phần 2.3)

- **Các subagent đã định nghĩa** (xem `src/lab/subagents.py`):
  - `explorer` — chỉ đọc, báo cáo. Lý do: tách bước "hiểu" khỏi bước "sửa" để implementer không phá context.
  - `implementer` — sửa file, chạy test. Lý do: gói các thao tác nguy hiểm (write/execute) vào một subagent có system prompt chặt.
  - `reviewer` — đọc lại file đã đổi, re-run check, **không sửa**. Lý do: kiểm tra chéo độc lập trước khi main finalize.
- **`subagent_calls` ở từng tác vụ** (đếm từ `run.json`):

| Tác vụ | subagent_calls | Nhận xét |
|---|---:|---|
| code-learn | 0 | Main tự xử lý, không delegate |
| data-learn | 0 | (lần chạy lỗi `GraphRecursionError` ở vòng 60, không đếm) |
| logs-learn | 0 | Main tự xử lý |
| code-eval | 0 | (lỗi recursion 60) |
| data-eval | 0 | (lỗi recursion 60) |
| logs-eval | 0 | Main tự xử lý |

- **Thông tin thiếu/thừa khi giao việc:** trong cả 6 lần chạy, main agent **chưa bao giờ gọi** bất kỳ subagent nào (mặc dù description của `explorer` nói rõ "delegate FIRST"). Có 2 nguyên nhân khả dĩ: (i) với `gpt-4o-mini` ở temperature 0, model mặc định tự xử lý vì thấy đủ công cụ; (ii) main system prompt của Deep Agents không có chỉ thị cứng "bạn PHẢI dùng subagent khi thấy description match". Description của subagent bị bỏ qua hoàn toàn.
- **Ảnh hưởng đến token và thời gian:** vì `subagent_calls = 0` ở mọi lần chạy thành công, đáng lẽ không có khác biệt. **Nhưng** 3/6 lần chạy của `subagents` vẫn bị `GraphRecursionError` (data-learn, code-eval, data-eval) — cao hơn `baseline` (1/6) và `skills-auto` (4/6). Nguyên nhân: mỗi lần import `subagents` đính kèm 3 dict mô tả (~2 KB) vào system prompt, đẩy tổng input lên ~200–400k token, khiến context dài hơn, tăng xác suất loop. Token trung bình của `subagents` = 204,131 (gấp 3.1× baseline = 65,352).

## 6. Self-evolving: skill do curator sinh (Phần 3)

- **Số lần chạy curator, số skill bị xóa và lý do:** chạy `python -m lab.curator` đúng 1 lần (sau khi có 3 lần chạy `baseline` học). LLM sinh 3 skill, **3/3 hợp lệ** (đều pass `validate_skill`: YAML frontmatter, `name` lowercase-dash, `description` ≤ 1024 ký tự, body ≤ 80 dòng, không chứa eval marker). Không có skill nào bị xóa.

| Skill | Tổng quát / riêng? | Đúng / sai? | `description` | `skills_read` (Phần 3.4) |
|---|---|---|---|---|
| avoid-common-mistakes | **Tổng quát** (checklist 10 điểm: file tồn tại, type hints, không sửa test, changelog, v.v.) | Đúng — đúng các lỗi F quan sát được | "Use this skill when preparing for tasks that involve coding, data analysis, or log parsing." (104 ký tự) | **0** ở cả 6 lần chạy (xem bảng mục 7) |
| validate-output-structure | **Tổng quát** (checklist 9 điểm: đúng schema, đúng kiểu, không field thừa) | Đúng — đúng các lỗi B (output file sai schema/field) | "Use this skill when generating output files or data structures." (61 ký tự) | **0** |
| handle-errors-properly | **Tổng quát** (checklist 10 điểm: try-except, log lỗi, validate input) | Hơi **xa đề** — lỗi `FileNotFoundError` của `logs-learn` không phải lỗi logic mà là lỗi quên ghi file, không thuộc phạm vi "error handling". | "Use this skill when working with data processing or log parsing tasks." (66 ký tự) | **0** |

- **Quan sát nghiêm trọng:** `skills_read = 0` ở **6/6** lần chạy `skills-auto` (cả học lẫn đánh giá). Mô hình **không bao giờ** mở bất kỳ skill nào. Tức là 3 skill tồn tại trên đĩa nhưng hoàn toàn vô hiệu. Vì sao: trong system prompt, danh sách skill chỉ liệt kê tên (không phải mô tả) — `LAB_MODEL_PROMPT` của Deep Agents không tự động đưa description vào context; model chỉ biết "có file ở `skills/auto/...`" mà không biết nó dùng khi nào. Tôi đã không ghi đè `load_skills` để đẩy cả description vào — đây là giới hạn của cách tiếp cận mặc định, **không phải** lỗi của skill.

## 7. Kết quả so sánh (Phần 4.3, 4.4)

```text
# report/table.md (đã có sẵn)
| Task            | baseline | subagents | skills-auto |
|-----------------|----------|-----------|-------------|
| code-learn      |  2/10    |  4/10     |  0/10       |
| data-learn      |  1/8     |  0/8      |  0/8        |
| logs-learn      |  0/9     |  1/9      |  0/9        |
| code-eval       |  1/11    |  1/11     |  2/11       |
| data-eval       |  1/9     |  0/9      |  3/9        |
| logs-eval       |  1/10    |  1/10     |  0/10       |
| Mean learn      |  0.11    |  0.17     |  0.00       |
| Mean eval       |  0.10    |  0.06     |  0.17       |
| Mean tokens     | 65,352   | 204,131   | 177,519     |
| Runs read skill |  0/6     |  0/6      |  0/6        |
```

- **Lần chạy có `error` (đã xử lý):** tổng cộng 8/18 lần chạy bị `GraphRecursionError` ở vòng 60 (1/6 baseline, 3/6 subagents, 4/6 skills-auto). Khi lỗi này xảy ra, `score = 0` và **mọi check được tính là fail** — đây là nguồn gây nhiễu lớn nhất. Phân bố:
  - `baseline/code-eval`: lỗi (score ghi 1/11 nhưng thực chất chỉ từ 1 check may mắn trước khi loop).
  - `subagents/{data-learn, code-eval, data-eval}`: lỗi.
  - `skills-auto/{code-learn, data-learn, code-eval, logs-eval}`: lỗi.
  - Tôi giữ nguyên `passed/total` như `check_breakdown.py` ghi vì agent vẫn kịp ghi một số file trước khi loop. **Cách xử lý đề xuất:** với các lần chạy lỗi, không nên so sánh điểm trực tiếp; nên đánh dấu "DNF" (Did Not Finish) và so sánh tỉ lệ hoàn thành.
- **`skills_modified = true`:** **0 lần** — không có lần chạy nào trong nhóm `skills-auto` tự sửa lại file SKILL.md.

## 8. Phân tích

1. **So sánh theo vai trò (learn vs eval).**
   - *Tác vụ học:* `subagents` (0.17) ≈ `baseline` (0.11) về điểm nhưng tốn 3.1× token. `skills-auto` (0.00) **giảm mạnh** so với baseline vì 4/6 lần chạy bị `GraphRecursionError` (4/6 = 67 % lỗi), kéo mean xuống.
   - *Tác vụ đánh giá:* `skills-auto` (0.17) **cải thiện** so với baseline (0.10) và subagents (0.06). Cụ thể: `code-eval` 2/11 (+1) và `data-eval` 3/9 (+2) so với baseline.
   - *Lệch pha:* `subagents` cải thiện nhẹ ở học (0.11→0.17) nhưng giảm ở đánh giá (0.10→0.06). Đây không phải dấu hiệu quá khớp (overfit) — vì subagent không hề được gọi (`subagent_calls = 0`). Đây là **nhiễu** do lỗi recursion lệch pha.

2. **Tách điểm thành check kỹ thuật vs check quy ước (`rule_*`).**

   | Điều kiện / Tác vụ | tech pass | rule pass | Ghi chú |
   |---|---:|---:|---|
   | baseline / code-eval | 1/7 | 0/4 | 0/4 rule (agent không tạo regression test, CHANGELOG, type hints) |
   | baseline / data-eval | 1/5 | 0/4 | 0/4 rule (meta block, money_in_cents, clean.csv) |
   | baseline / logs-eval | 1/6 | 0/4 | 0/4 rule (service_names, sorted_errors, schema) |
   | subagents / code-eval | 1/7 | 0/4 | giống baseline |
   | subagents / data-eval | 0/5 | 0/4 | (lỗi recursion) |
   | subagents / logs-eval | 1/6 | 0/4 | giống baseline |
   | **skills-auto / code-eval** | 2/7 | **0/4** | +1 tech, rule vẫn 0 |
   | **skills-auto / data-eval** | **3/5** | **0/4** | +2 tech (đáng kể), rule vẫn 0 |
   | skills-auto / logs-eval | 0/6 | 0/4 | (lỗi recursion) |

   - **Skill giúp nhóm tech (A–B) chứ không giúp nhóm rule (F).** Nghe phản trực giác vì H2 dự đoán ngược lại — nhưng thực tế `skills_read = 0` ở mọi lần chạy, tức là **không có skill nào thực sự được áp dụng**. Sự cải thiện tech ở `code-eval` (+1) và `data-eval` (+2) có thể là nhiễu ngẫu nhiên của temperature 0 trên prompt có chứa mô tả skill (description xuất hiện trong system prompt dù model không `read_file`).
   - **Check quy ước mới của tác vụ đánh giá KHÔNG được skill giúp** (0/4 rule ở mọi điều kiện) — phù hợp với dự đoán H3: các rule mới (như `service_names` ở `logs-eval`) không xuất hiện trong lịch sử thất bại mà curator nhìn thấy, nên skill không thể phòng ngừa.

3. **Một check skill "giúp" đạt và một check skill không giúp.**
   - *Check mà skill có vẻ giúp (dù `skills_read=0`):* `data-eval` +2 check tech (từ 1/5 lên 3/5). Vì skill không được đọc, sự cải thiện này gần như chắc chắn là **nhiễu mẫu đơn** chứ không phải tác động của skill. Không thể khẳng định skill "giúp" check nào cụ thể khi `skills_read = 0`.
   - *Check mà skill không giúp:* `rule_type_hints` ở `code-learn` và `code-eval` — fail ở cả 3 điều kiện. Vì sao: skill `avoid-common-mistakes` có bullet "Check that all functions and methods have the necessary type annotations", nhưng model không đọc skill. Nếu model đọc, vẫn cần khả năng chỉnh nhiều file cùng lúc — đây là giới hạn của `gpt-4o-mini` (nhỏ hơn `gpt-4o`), không phải giới hạn của skill.

4. **Chi phí: token trung bình và hiệu quả (điểm / 1k token).**

   | Điều kiện | Mean tokens | Mean eval score | Điểm / 100k token |
   |---|---:|---:|---:|
   | baseline | 65,352 | 0.10 | **0.153** |
   | subagents | 204,131 | 0.06 | 0.029 |
   | skills-auto | 177,519 | 0.17 | 0.096 |

   - **Hiệu quả cao nhất: `baseline` (0.153).** `skills-auto` đứng thứ hai vì mean eval cao hơn nhưng tốn gấp 2.7× token. `subagents` tệ nhất: vừa tốn token gấp 3.1× vừa có mean eval thấp hơn baseline.
   - **Đa tác tử có đáng chi phí?** **Không**, vì 6/6 lần chạy `subagent_calls = 0` — toàn bộ 3 subagent chỉ ngốn token ở system prompt mà không bao giờ được dùng. Nếu muốn test ý nghĩa multi-agent, cần ép main agent delegate (ví dụ: bỏ một số tool khỏi main, chỉ giữ ở subagent).

5. **Dấu hiệu rò rỉ dữ liệu / quá khớp trong skill.**
   - `validate_skill` kiểm tra `eval_markers()` — một danh sách chuỗi đặc trưng cho tác vụ đánh giá. Cả 3 skill đều không chứa marker → **không rò rỉ**.
   - Kiểm tra thủ công: 3 skill không nhắc tên tác vụ cụ thể (`code-learn`, `data-eval`...), không nhắc số (`12.00`, `1299.50`), không nhắc tên file chỉ tồn tại ở một tác vụ (`inventory/`, `clean.csv`) → **không quá khớp**.
   - Lưu ý: vì `skills_read = 0`, ngay cả khi có quá khớp cũng không ảnh hưởng kết quả. Vấn đề thực sự là skill không được đọc, không phải skill chứa quá khớp.

6. **Nhiễu: cùng bộ skill ở Phần 3.4 (đã sao lưu `skills-auto-dev`) vs sau đóng băng.**

   | Tác vụ | Phần 3.4 (dev) | Sau freeze (chính thức) | Δ |
   |---|---:|---:|---:|
   | code-learn | 4/10 (0.40) | 0/10 (0.00) | **−0.40** |
   | data-learn | 3/8 (0.38) | 0/8 (0.00) | **−0.38** |
   | logs-learn | 0/9 (0.00) | 0/9 (0.00) | 0.00 |

   - **Chênh lệch rất lớn (−0.38 đến −0.40)** cho thấy kết quả `skills-auto` Phần 4.4 cực kỳ nhiễu. Nguyên nhân khả dĩ:
     1. Trước freeze, agent chạy với input gọn hơn (chưa chứa commit hypotheses ở trên).
     2. Sau khi đẩy hết kết quả Phần 3.4 lên freeze, có vẻ Deep Agents cache hoặc context state khiến recursion dễ kích hoạt hơn → 4/6 lần lỗi ở Phần 4.4 vs 0/6 ở Phần 3.4.
   - **Hệ quả:** các chênh lệch trong bảng mục 7 (đặc biệt cột `skills-auto`) **không đáng tin cậy** nếu xét riêng 1 lần chạy. Cần lặp lại ≥ 3 lần mỗi (điều kiện, tác vụ) để có ý nghĩa thống kê.

## 9. Hạn chế và tính hợp lệ

1. **Mỗi cấu hình chỉ chạy 1 lần.** Vì `temperature = 0` nên lý thuyết mỗi lần chạy là deterministic, nhưng thực tế vẫn có sai số từ (i) cache, (ii) biến động nhỏ của OpenAI API, và (iii) 8/18 lần chạy bị `GraphRecursionError` không lặp lại được (một lần chạy lại có thể không lỗi). Một conf chạy 1 lần là **chưa đủ** để khẳng định "skills-auto tốt hơn baseline 7 điểm % trên eval".
2. **3 tác vụ mỗi vai trò quá ít để phân tầng.** 3 tác vụ có profile rất khác nhau (code = sửa source, data = transform CSV, logs = parse file), nên mean của 3 tác vụ dễ bị một tác vụ chi phối. Ví dụ: `logs-learn` fail 100 % ở cả 3 điều kiện vì agent quên ghi file — mean bị kéo xuống đều 3 điều kiện, làm sai lệch so sánh.
3. **Một mô hình duy nhất (`gpt-4o-mini`).** Đây là mô hình nhỏ, dễ bỏ sót khi phải chỉnh nhiều file cùng lúc (ví dụ `rule_type_hints` fail đồng đều). Kết luận "skill vô hiệu" có thể **không tổng quát** cho `gpt-4o` hoặc `claude-sonnet` — những mô hình đó có thể tự đọc skill theo description mà không cần `read_file`.
4. **Skill không bao giờ được đọc (`skills_read = 0/6`).** Toàn bộ phân tích "skill có/không giúp" trong mục 8 đang nói về **sự có mặt của file skill** chứ không phải tác động thực sự. Đây là hạn chế lớn nhất: thí nghiệm không đo được hiệu quả của self-evolving skill vì model không truy cập được chúng.
5. **Hệ điều hành: chạy qua Docker trên Windows.** Tốc độ khởi tạo container và việc mount volume trên Windows chậm; một số lần chạy đầu bị `RecursionError` do mất kết nối với API key qua `.env` (đã sửa bằng cách đặt key trong shell của Docker). Không ảnh hưởng tính đúng đắn nhưng ảnh hưởng thời gian thực nghiệm.

## 10. Kết luận

1. Trong thí nghiệm này, **không có điều kiện nào cải thiện đáng kể so với baseline**: `subagents` cộng 0.06 mean học nhưng trừ 0.04 mean eval; `skills-auto` cộng 0.07 mean eval nhưng 4/6 lần chạy lỗi recursion ở học. Hiệu quả tốt nhất theo điểm/token là baseline (0.153 điểm/100k token).
2. H1 được khẳng định: multi-agent **không giúp** khi các subagent không có thông tin riêng (`subagent_calls = 0` ở cả 6 lần). H2 bị **phủ nhận một phần**: skill có vẻ cải thiện tech ở eval nhưng `skills_read = 0` ở mọi lần, nên sự cải thiện nhiều khả năng là nhiễu. H3 được khẳng định: skill không giúp được check quy ước mới (0/4 rule ở cả 3 điều kiện).
3. **Đề xuất cải tiến:** (i) sửa `runner.py` để **đẩy cả `description` của skill vào system prompt** (Deep Agents mặc định chỉ liệt kê tên), hoặc override `load_skills` để model biết khi nào nên đọc; (ii) tăng `recursion_limit` lên 100 hoặc thêm tool `finalize` rõ ràng để giảm 44 % lỗi; (iii) chạy lặp ≥ 3 lần mỗi (điều kiện, tác vụ) để có ý nghĩa thống kê.

## Phụ lục

- **Lệnh đã chạy (thứ tự thời gian):**
  1. `docker build -t lab-deepagents .` (dựng image Python 3.12 + deepagents==0.7.21).
  2. `python scripts/tour.py` (làm quen harness Phần 0.3).
  3. `docker run --rm --env-file .env -v ${PWD}:/lab -w /lab lab-deepagents python -m lab.runner --condition baseline` × 6 lần (3 học + 3 đánh giá).
  4. `git add -A && git commit -m "hypotheses"` (ghi H1/H2/H3 và `skills/auto` rỗng trước freeze).
  5. `git tag freeze 13c507a`.
  6. `python -m lab.curator` (sinh 3 skill vào `skills/auto/`).
  7. `docker run ... lab-deepagents python -m lab.runner --condition subagents` × 6.
  8. `docker run ... lab-deepagents python -m lab.runner --condition skills-auto` × 6 (sau freeze).
  9. `python scripts/check_breakdown.py` (sinh `report/table.md`).
  10. `python scripts/verify_freeze.py` (xác nhận freeze đặt đúng chỗ).
  11. `git restore` / `git commit` các file `results/` (giữ audit trail).

- **Thử thách mở rộng:** *không thực hiện* do đã hết ngân sách thời gian. Hướng đề xuất nếu có thêm thời gian: chạy lặp `skills-auto` 3 lần trên 3 tác vụ eval, đo mean ± std, kiểm tra xem cải thiện 0.07 có ý nghĩa thống kê không (paired t-test).

- **Ghi chú khác:**
  - Tổng token: 2,845,907 (~2.85 M) — ước tính $0.46 USD với `gpt-4o-mini`.
  - Tổng thời gian thực nghiệm: ~3 giờ (tính cả 30 phút debug Docker shell trên Windows).
  - `recursion_limit=60` đã chặt với `gpt-4o-mini` trên các tác vụ data/logs: 8/18 lần chạy bị `GraphRecursionError`. Đây là hạn chế về phía runner, không phải lỗi của agent hay skill.
