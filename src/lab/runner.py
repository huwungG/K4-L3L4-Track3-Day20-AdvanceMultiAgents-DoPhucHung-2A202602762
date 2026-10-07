"""GUIDE Phần 1 - Chạy một tác vụ (task) và ghi kết quả.   >>> SINH VIÊN CÀI ĐẶT run_task <<<

Pseudo-code: guides/pseudocode/03_runner.md
Kiểm tra:    pytest tests/test_03_runner.py
Chạy thật:   python -m lab.runner --condition baseline --tasks learn
"""
import argparse
import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import AIMessage, ToolMessage

from .agent import build_agent
from .grading import grade                                                      # có sẵn
from .tasks import ROOT, get_task, hash_dir, list_tasks, prepare_sandbox         # có sẵn

# Ba điều kiện thí nghiệm (condition). `skills_dir` là thư mục skill nguồn (tính từ thư mục gốc của lab).
CONDITIONS = {
    "baseline": {"mode": "single", "skills_dir": None},
    "subagents": {"mode": "subagents", "skills_dir": None},
    "skills-auto": {"mode": "single", "skills_dir": "skills/auto"},
}


def render_trace(messages) -> str:
    """CÓ SẴN, KHÔNG SỬA. Chuyển danh sách message của luồng chính thành Markdown (vết - trace).

    Lưu ý: chỉ gồm luồng chính. Việc subagent làm bên trong KHÔNG hiện trong vết;
    chỉ thấy lệnh gọi `task` và báo cáo cuối của subagent.
    """
    home = str(Path.home())

    def clean(text) -> str:
        return str(text).replace(home, "~")[:1500]

    parts = []
    for m in messages:
        if isinstance(m, AIMessage):
            if m.content:
                parts.append(f"### Assistant\n{clean(m.content)}")
            for tc in m.tool_calls:
                parts.append(f"### Tool call: {tc['name']}\n{clean(json.dumps(tc['args'], ensure_ascii=False))}")
        elif isinstance(m, ToolMessage):
            parts.append(f"### Tool result\n{clean(m.content)}")
        else:
            parts.append(f"### {m.type.capitalize()}\n{clean(m.content)}")
    return "\n\n".join(parts)


def _summarise_usage(usage: UsageMetadataCallbackHandler) -> dict:
    """Cộng token trên mọi mô hình mà callback ghi nhận (kể cả subagent)."""
    in_t = out_t = total_t = 0
    for meta in usage.usage_metadata.values():
        # UsageMetadata là TypedDict: input_tokens / output_tokens / total_tokens
        in_t += int(meta.get("input_tokens", 0) or 0)
        out_t += int(meta.get("output_tokens", 0) or 0)
        total_t += int(meta.get("total_tokens", 0) or 0)
    return {"input": in_t, "output": out_t, "total": total_t}


def _skill_name_from_read_path(file_path: str) -> str | None:
    """Trích tên skill từ file_path của read_file, nếu file nằm dưới skills/.

    Chấp nhận cả dạng ảo ("/skills/<name>/SKILL.md") và tương đối ("skills/<name>/SKILL.md");
    trả về None nếu đường dẫn không thuộc skills/ hoặc không có tên skill theo sau.
    """
    p = str(file_path).replace("\\", "/").lstrip("/")
    if "skills/" not in p:
        return None
    # lấy phần đầu tiên sau "skills/"
    after = p.split("skills/", 1)[1]
    parts = [seg for seg in after.split("/") if seg]
    if not parts or parts[0] in ("", "."):
        return None
    return parts[0]


def run_task(task_id: str, condition: str, results_dir="results", model=None, recursion_limit: int = 60) -> dict:
    """Chạy MỘT tác vụ dưới MỘT điều kiện, chấm điểm, ghi kết quả, và trả về bản ghi (record).

    Ghi vào: <results_dir>/<condition>/<task_id>/run.json và trace.md  (trace.md = render_trace(messages)).
    Bản ghi `run.json` phải có các khóa:
      task, condition, role, score, passed, total, checks,
      tokens {input, output, total}       - cộng dồn mọi lần gọi LLM, kể cả subagent (dùng UsageMetadataCallbackHandler)
      tool_calls                          - số tool call trong các AIMessage của luồng chính (không gồm việc bên trong subagent)
      subagent_calls                      - số tool call có tên "task" (giao việc cho subagent)
      skills_read                         - số skill KHÁC NHAU đã được đọc: với mỗi tool call "read_file" có file_path chứa
                                            "skills/", lấy tên thư mục ngay sau "skills/" rồi đếm các tên khác nhau
                                            (đọc lại cùng một skill chỉ tính một lần)
      skills_modified (bool)              - thư mục skills trong sandbox bị đổi trong lúc chạy (so hash_dir trước/sau)
      skills_sha256                       - hash_dir(sandbox/"skills") TRƯỚC khi chạy (để đối chiếu với skill đã đóng băng)
      timestamp                           - thời điểm bắt đầu, UTC, dạng ISO-8601
      seconds, final_message, error (None nếu không lỗi)
    Lỗi khi chạy tác tử KHÔNG được làm chương trình dừng: ghi vào `error` và vẫn chấm điểm.
    Sandbox là thư mục tạm NGOÀI kho mã nguồn và phải được xóa sau khi chạy.
    """
    cfg = CONDITIONS[condition]
    task = get_task(task_id)
    skills_dir = (ROOT / cfg["skills_dir"]) if cfg["skills_dir"] else None
    out = Path(results_dir) / condition / task_id
    out.mkdir(parents=True, exist_ok=True)

    # Sandbox phải nằm ngoài kho mã nguồn: tạo ở thư mục tạm của hệ thống và xóa ở CUỐI CÙNG.
    sandbox = Path(tempfile.mkdtemp(prefix=f"lab_sb_{task_id}_"))

    record: dict = {
        "task": task_id,
        "condition": condition,
        "role": task.role,
        "error": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "final_message": "",
    }

    try:
        prepare_sandbox(task, sandbox, skills_dir)
        hash_truoc = hash_dir(sandbox / "skills")
        record["skills_sha256"] = hash_truoc

        agent = build_agent(
            sandbox,
            mode=cfg["mode"],
            use_skills=(skills_dir is not None),
            model=model,
        )
        usage = UsageMetadataCallbackHandler()
        t0 = time.time()

        messages: list = []
        final_text = ""
        # Lưu trạng thái mỗi bước; nếu recursion_limit chặn, ta vẫn giữ được phần vết cuối cùng.
        # stream_mode="values" phát ra state mỗi node; node cuối chứa toàn bộ messages đã có.
        try:
            for step in agent.stream(
                {"messages": [{"role": "user", "content": task.instruction}]},
                config={"callbacks": [usage], "recursion_limit": recursion_limit},
                stream_mode="values",
            ):
                if isinstance(step, dict) and "messages" in step:
                    messages = step["messages"]
        except Exception as exc:  # noqa: BLE001
            record["error"] = f"{type(exc).__name__}: {exc}"

        if messages:
            final_text = str(getattr(messages[-1], "content", "") or "")

        record["seconds"] = round(time.time() - t0, 1)
        record["tokens"] = _summarise_usage(usage)
        record["final_message"] = final_text

        # Các số đếm chỉ trên LUỒNG CHÍNH (AIMessage.tool_calls)
        all_calls = [tc for m in messages if isinstance(m, AIMessage) for tc in (m.tool_calls or [])]
        record["tool_calls"] = len(all_calls)
        record["subagent_calls"] = sum(1 for tc in all_calls if tc.get("name") == "task")

        skill_names: set[str] = set()
        for tc in all_calls:
            if tc.get("name") == "read_file":
                name = _skill_name_from_read_path(tc.get("args", {}).get("file_path", ""))
                if name:
                    skill_names.add(name)
        record["skills_read"] = len(skill_names)

        record["skills_modified"] = (hash_dir(sandbox / "skills") != hash_truoc)

        # Chấm trên workspace đã bị tác tử sửa (nằm trong sandbox)
        g = grade(task, sandbox / "workspace")
        record["score"] = g.get("score", 0.0)
        record["passed"] = g.get("passed", 0)
        record["total"] = g.get("total", 0)
        record["checks"] = g.get("checks", [])
        if g.get("error"):
            # giữ lỗi grading ở key phụ (không phải lỗi của tác tử)
            record["grading_error"] = g["error"]

        (out / "trace.md").write_text(render_trace(messages), encoding="utf-8")

    finally:
        # Dọn sandbox bất kể kết quả
        shutil.rmtree(sandbox, ignore_errors=True)

    (out / "run.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def main(argv=None):
    """CÓ SẴN, KHÔNG SỬA. Giao diện dòng lệnh (CLI): --condition, --tasks (id... | all | learn | eval), --results, --recursion-limit.

    In mỗi lần chạy một dòng: điều kiện, id, passed/total, token, số tool call, số giây, lỗi (nếu có).
    """
    ap = argparse.ArgumentParser(description="Run tasks under one condition.")
    ap.add_argument("--condition", required=True, choices=sorted(CONDITIONS))
    ap.add_argument("--tasks", nargs="+", default=["all"], help="task ids, or 'all', 'learn', 'eval'")
    ap.add_argument("--results", default="results")
    ap.add_argument("--recursion-limit", type=int, default=60)
    args = ap.parse_args(argv)
    if args.tasks == ["all"]:
        ids = [t.id for t in list_tasks()]
    elif args.tasks in (["learn"], ["eval"]):
        ids = [t.id for t in list_tasks(args.tasks[0])]
    else:
        ids = args.tasks
    for tid in ids:
        try:
            r = run_task(tid, args.condition, args.results, recursion_limit=args.recursion_limit)
        except Exception as exc:  # noqa: BLE001
            print(f"{args.condition:13s} {tid:11s} CRASH {type(exc).__name__}: {exc}", flush=True)
            continue
        print(f"{args.condition:13s} {tid:11s} score={r['passed']}/{r['total']} tokens={r['tokens']['total']} "
              f"calls={r['tool_calls']} {r['seconds']}s" + (f" ERROR={r['error']}" if r["error"] else ""), flush=True)


if __name__ == "__main__":
    main()