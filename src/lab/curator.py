"""GUIDE Phần 3 - Người tuyển chọn skill (skill curator): tự viết skill từ các lần chạy thất bại.   >>> SINH VIÊN CÀI ĐẶT curate_skills <<<

Pseudo-code: guides/pseudocode/04_curator.md
Kiểm tra:    pytest tests/test_04_curator.py
Chạy thật:   python -m lab.curator
"""
import json
import re
from pathlib import Path

from .model import make_model
from .tasks import ROOT as _ROOT, eval_markers   # có sẵn: định danh của tác vụ đánh giá, tính lúc chạy

# ---- CÓ SẴN, KHÔNG SỬA: kiểm tra và tách khối skill (phần dễ sai và liên quan bảo mật) ----------------
SAFE_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_skill(text: str, expected_name: str | None = None) -> list[str]:
    """Kiểm tra nội dung một SKILL.md. Trả về danh sách vấn đề (rỗng = hợp lệ).

    Quy tắc: có khối YAML frontmatter; `name` chữ thường/số/gạch ngang (tối đa 64 ký tự) và bằng `expected_name`
    nếu được truyền; có `description` (tối đa 1024 ký tự); phần thân tối đa 80 dòng; không chứa chuỗi nào của
    `eval_markers()`. Quy tắc về `name` cũng là biện pháp bảo mật: tên khối do LLM sinh ra được dùng để tạo
    đường dẫn, nên `../evil` không được lọt qua.
    """
    problems = []
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text.strip() + "\n", re.S)
    if not m:
        return ["missing YAML frontmatter"]
    front, body = m.groups()
    name = re.search(r"^name:\s*(.+)$", front, re.M)
    desc = re.search(r"^description:\s*(.+)$", front, re.M)
    n = name.group(1).strip() if name else ""
    if not SAFE_NAME.fullmatch(n) or len(n) > 64:
        problems.append("invalid name")
    elif expected_name is not None and n != expected_name:
        problems.append("name differs from the block name")
    if not desc or len(desc.group(1).strip()) > 1024:
        problems.append("missing or too long description")
    if len(body.strip().splitlines()) > 80:
        problems.append("body longer than 80 lines")
    low = text.lower()
    for marker in eval_markers():
        if marker in low:
            problems.append(f"mentions evaluation material: {marker}")
    return problems


def parse_skill_blocks(reply: str) -> list[tuple[str, str]]:
    """Tách câu trả lời của LLM thành danh sách (name, nội dung SKILL.md).

    Khuôn dạng: `=== SKILL: <name> ===` ... `=== END ===`. Một khối kết thúc ở điểm nào đến trước trong ba điểm:
    `=== END ===`, tiêu đề `=== SKILL:` kế tiếp, hoặc cuối văn bản (LLM đôi khi quên dòng END).
    """
    pattern = re.compile(r"^=== SKILL: (\S+) ===[ \t]*\n(.*?)(?=^=== END ===|^=== SKILL: |\Z)", re.S | re.M)
    return [(name, text.strip()) for name, text in pattern.findall(str(reply))]
# --------------------------------------------------------------------------------------------------


PROMPT_TEMPLATE = """You write SKILL.md files for a Python engineering / data-analysis agent.

Below are the FAILED CHECKS of recent LEARNING-task runs. For each failure you see the check name
and the reviewer's `detail` (which states the rule that was violated). You also see the tail of the
trace (the agent's last actions).

Find the PROCESS mistakes that are COMMON across runs (not task-specific answers) and write at most
{max_skills} short skills that help an agent AVOID those mistakes on NEW tasks of the same kind.

Rules:
- Each skill must be GENERAL: do NOT name a specific task id, do NOT name files that only exist
  in one task, do NOT reveal the expected answer or any specific numbers from the runs.
- Each skill has YAML frontmatter with `name` (lowercase letters/digits/dashes) and
  `description` (one sentence: WHEN to use this skill), followed by at most 40 lines of
  imperative guidance (a checklist works well).
- Output format, exact characters:
=== SKILL: <name> ===
---
name: <name>
description: <when to use>
---
<body>
=== END ===

Failed-check runs (learning tasks only):
{runs}
"""


def _format_run(run: dict, trace_text: str | None) -> str:
    """Chuyển một bản ghi run.json thành khối văn bản ngắn cho prompt."""
    failed = [
        {"name": c.get("name", "?"), "detail": c.get("detail", "")}
        for c in run.get("checks", [])
        if not c.get("passed")
    ]
    trace_tail = (trace_text or "")[-6000:]
    return (
        f"\n## TASK: {run.get('task')}\n"
        f"FAILED CHECKS:\n{json.dumps(failed, ensure_ascii=False, indent=2)}\n"
        f"TRACE TAIL (last ~6KB):\n{trace_tail}\n"
    )


def curate_skills(results_dir="results", source_condition="baseline", out_dir=None, model=None, max_skills: int = 3) -> list[Path]:
    """Đọc các lần chạy của TÁC VỤ HỌC (role == "learn") trong `source_condition`, nhờ LLM viết skill, ghi file.

    Các bước: nạp run.json + trace.md -> (nếu không có check nào thất bại: in cảnh báo và trả về [] mà KHÔNG gọi LLM)
    -> dựng prompt -> model.invoke(prompt) -> parse_skill_blocks -> validate_skill(text, expected_name=name)
    -> ghi `<out_dir>/<name>/SKILL.md`. Mặc định `out_dir` = <gốc lab>/skills/auto (dùng `ROOT` từ lab.tasks).
    Giữ tối đa `max_skills` skill hợp lệ; skill không hợp lệ bị bỏ qua.
    Prompt chứa, với mỗi check thất bại, TÊN và trường `detail` (lời nhận xét của bot đánh giá: phát biểu quy tắc bị vi phạm)
    cùng phần cuối của vết (trace). Với tác vụ học, `detail` chỉ phát biểu quy tắc, không chứa đáp án.
    Tuyệt đối KHÔNG đưa dữ liệu của tác vụ đánh giá (role == "eval") vào prompt.
    model mặc định: make_model() (lab.model).
    Trả về: danh sách đường dẫn SKILL.md đã ghi.
    """
    if out_dir is None:
        out_dir = _ROOT / "skills" / "auto"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results_dir = Path(results_dir)
    src_dir = results_dir / source_condition
    if not src_dir.exists():
        print(f"[curator] source directory not found: {src_dir}")
        return []

    runs_for_prompt: list[str] = []
    for run_path in sorted(src_dir.glob("*/run.json")):
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if run.get("role") != "learn":
            # KHÔNG đưa dữ liệu của tác vụ đánh giá vào prompt
            continue
        checks = run.get("checks", [])
        if all(c.get("passed", True) for c in checks):
            continue  # lần chạy này không có gì để rút kinh nghiệm
        trace_path = run_path.parent / "trace.md"
        trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
        runs_for_prompt.append(_format_run(run, trace_text))

    if not runs_for_prompt:
        print("[curator] no failed-check learning runs to investigate; nothing to write.")
        return []

    prompt = PROMPT_TEMPLATE.format(max_skills=max_skills, runs="\n".join(runs_for_prompt))

    if model is None:
        model = make_model()
    reply = model.invoke(prompt).content

    written: list[Path] = []
    for name, text in parse_skill_blocks(reply):
        if len(written) >= max_skills:
            break
        problems = validate_skill(text, expected_name=name)
        if problems:
            # bỏ qua skill không hợp lệ (không sửa tay nội dung)
            continue
        target = out_dir / name
        target.mkdir(parents=True, exist_ok=True)
        path = target / "SKILL.md"
        path.write_text(text.strip() + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in curate_skills():
        print("wrote", p)