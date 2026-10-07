import json
from pathlib import Path
from collections import Counter

# Build comparison table
cond_task = {}
for cond in ['baseline', 'subagents', 'skills-auto']:
    for t in ['code-learn', 'data-learn', 'logs-learn', 'code-eval', 'data-eval', 'logs-eval']:
        p = Path(f'results/{cond}/{t}/run.json')
        if not p.exists():
            continue
        r = json.loads(p.read_text(encoding='utf-8'))
        cond_task[(cond, t)] = r

# Means
for role in ['learn', 'eval']:
    print(f'\n=== {role} ===')
    print(f'{"condition":12}  {"score":>7}  {"tokens":>9}  {"subagent":>9}  {"skills_read":>12}')
    for cond in ['baseline', 'subagents', 'skills-auto']:
        scores = []
        toks = []
        sa_total = 0
        sr_total = 0
        n = 0
        for t in [f'code-{role}', f'data-{role}', f'logs-{role}']:
            if (cond, t) in cond_task:
                r = cond_task[(cond, t)]
                scores.append(r['score'])
                toks.append(r['tokens']['total'])
                sa_total += r.get('subagent_calls', 0)
                sr_total += r.get('skills_read', 0)
                n += 1
        if n:
            print(f'{cond:12}  {sum(scores)/n:>7.2f}  {sum(toks)/n:>9,.0f}  {sa_total/n:>9.1f}  {sr_total/n:>12.1f}')

# Per-task table
print('\n=== PER-TASK ===')
print(f'{"task":12}  {"baseline":>10}  {"subagents":>10}  {"skills-auto":>10}')
for role in ['learn', 'eval']:
    for t in [f'code-{role}', f'data-{role}', f'logs-{role}']:
        row = [t]
        for cond in ['baseline', 'subagents', 'skills-auto']:
            if (cond, t) in cond_task:
                row.append(f'{cond_task[(cond, t)]["passed"]}/{cond_task[(cond, t)]["total"]}')
            else:
                row.append('-')
        print(f'  {row[0]:10}  {row[1]:>10}  {row[2]:>10}  {row[3]:>10}')

# errored runs - how many had GraphRecursionError per condition
print('\n=== ERRORED (no score counted) ===')
for cond in ['baseline', 'subagents', 'skills-auto']:
    n_err = sum(1 for (c, t), r in cond_task.items() if c == cond and r.get('error'))
    n_total = sum(1 for (c, t), r in cond_task.items() if c == cond)
    print(f'  {cond:11}: {n_err}/{n_total} errored')

# 3.4 vs 4.4 skills-auto noise check (skills-auto-dev vs skills-auto on code/data/logs-learn)
print('\n=== NOISE: skills-auto-dev (Phan 3.4) vs skills-auto (Phan 4.4) on learning tasks ===')
for t in ['code-learn', 'data-learn', 'logs-learn']:
    p_dev = Path(f'results/skills-auto-dev/{t}/run.json')
    p_new = Path(f'results/skills-auto/{t}/run.json')
    if p_dev.exists() and p_new.exists():
        rd = json.loads(p_dev.read_text(encoding='utf-8'))
        rn = json.loads(p_new.read_text(encoding='utf-8'))
        print(f'  {t}: dev score={rd["score"]:.2f} ({rd["passed"]}/{rd["total"]}) vs new score={rn["score"]:.2f} ({rn["passed"]}/{rn["total"]})')