import json
from pathlib import Path
from collections import Counter

def group_of(c):
    if c.startswith('rule_'):
        return 'F-rule'
    if c in ('visible_suite_passes', 'tests_not_modified'):
        return 'A-test'
    return 'B-docstring'

# Eval runs - separate tech vs rule
print('=== EVAL TASKS (rule breakdown) ===')
for cond in ['baseline', 'subagents', 'skills-auto']:
    for t in ['code-eval', 'data-eval', 'logs-eval']:
        p = Path(f'results/{cond}/{t}/run.json')
        if not p.exists():
            continue
        r = json.loads(p.read_text(encoding='utf-8'))
        rule_pass = sum(1 for c in r['checks'] if c['name'].startswith('rule_') and c['passed'])
        rule_tot = sum(1 for c in r['checks'] if c['name'].startswith('rule_'))
        tech_pass = sum(1 for c in r['checks'] if not c['name'].startswith('rule_') and c['passed'])
        tech_tot = sum(1 for c in r['checks'] if not c['name'].startswith('rule_'))
        print(f'  {cond:11} {t:10}: score={r["score"]:.2f}  passed={r["passed"]}/{r["total"]}  tech={tech_pass}/{tech_tot}  rule={rule_pass}/{rule_tot}  tokens={r["tokens"]["total"]}')

# Subagent calls and skills read
print()
print('=== SUBAGENT_CALLS / SKILLS_READ ===')
for cond in ['baseline', 'subagents', 'skills-auto']:
    for t in ['code-learn','data-learn','logs-learn','code-eval','data-eval','logs-eval']:
        p = Path(f'results/{cond}/{t}/run.json')
        if not p.exists():
            continue
        r = json.loads(p.read_text(encoding='utf-8'))
        sa = r.get('subagent_calls', 0)
        sr = r.get('skills_read', 0)
        sm = r.get('skills_modified', False)
        err = r.get('error')
        flag = '*' if err else ' '
        mflag = 'M' if sm else ' '
        print(f'  {flag}{mflag} {cond:11} {t:10}: subagent_calls={sa:>2}  skills_read={sr:>2}  err={err}')

# Skills content
print()
print('=== SKILL FILES (after freeze) ===')
import os
for s in sorted(os.listdir('skills')):
    p = Path(f'skills/{s}')
    sz = p.stat().st_size
    with open(p, encoding='utf-8') as f:
        head = f.read(300).replace('\n', '\\n')
    print(f'  {s}: {sz}B  -- {head[:200]}')

# Skills from curator perspective - check if description is set
print()
print('=== SKILL DESCRIPTIONS ===')
for s in sorted(os.listdir('skills')):
    p = Path(f'skills/{s}')
    with open(p, encoding='utf-8') as f:
        text = f.read()
    has_desc = 'description' in text.lower()
    has_yaml = text.startswith('---')
    print(f'  {s}: has_description={has_desc}  yaml_frontmatter={has_yaml}  len={len(text)}')