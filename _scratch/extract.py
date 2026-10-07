import json
from pathlib import Path
from collections import Counter

def group_of(c):
    if c.startswith('rule_'):
        return 'F-rule'
    if c in ('visible_suite_passes', 'tests_not_modified'):
        return 'A-test'
    return 'B-docstring'

for cond in ['baseline', 'subagents', 'skills-auto']:
    print(f'### {cond}')
    for t in ['code-learn', 'data-learn', 'logs-learn']:
        p = Path(f'results/{cond}/{t}/run.json')
        if not p.exists():
            continue
        r = json.loads(p.read_text(encoding='utf-8'))
        grp_counter = Counter()
        fails = []
        for c in r['checks']:
            if not c['passed']:
                grp_counter[group_of(c['name'])] += 1
                fails.append((c['name'], group_of(c['name']), c['detail'][:90]))
        s = r['score']
        pas = r['passed']
        tot = r['total']
        print(f'  {t}: score={s:.2f}  passed={pas}/{tot}  groups={dict(grp_counter)}')
        for c, g, d in fails:
            print(f'    [{g}] {c}: {d}')