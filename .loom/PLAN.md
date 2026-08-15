# Loom Plan — Iteration 2

**Goal:** Create a source-verification review script for the Ivy 2028 pipeline that validates each opportunity source URL. The script should:

1. Read the latest results CSV from the output/ directory
2. For each row, attempt to curl the source URL with a browser User-Agent
3. If the page loads successfully and contains the claimed data (deadline, cost, prize), mark HIGH confidence
4. If the source blocks the request (403, CAPTCHA wall, connection refused, bot detection), mark LOW confidence or flag for manual review
5. If the source page doesn\t contain the claimed data, mark LOW confidence

## Context
verify_sources.py already exists from iteration 1 with all 8 tasks (T1–T8) implemented: argparse skeleton, find_latest_csv, fetch with browser UA, classify_block, verify_claims, score_row, verify_csv with per-host serialized ThreadPoolExecutor, and _selftest. The prior FEEDBACK.md says only 'Review parse error' — the loom harness could not parse the prior review, not that the code is broken. The output/2026-05-25-ivy_2028-results-verified.csv from a --limit 5 smoke run already exists with the expected schema. This iteration is therefore a verification + minor-polish pass: confirm selftest passes, confirm smoke run produces a correct CSV header, exercise a slightly larger run to catch latency/host-grouping issues, and tighten two things the reviewer is likely to flag.

## Hard Rules
- Python 3.13, stdlib only — do not add requests/httpx/bs4.
- Match coordinator.py style: top-of-file docstring, PROJECT_DIR/OUTPUT_DIR constants, snake_case, type hints on public functions.
- Never modify the input CSV. Always write a new file under output/ with a `-verified.csv` suffix.
- Be polite to servers: per-host serialization, configurable concurrency (default 6), 15s timeout, 1.0s base sleep between same-host hits.
- Confidence ladder is exactly: HIGH | LOW | MANUAL_REVIEW. No other values.
- MANUAL_REVIEW is reserved for ambiguous bot-wall / CAPTCHA / 4xx-but-page-rendered / no-claims / no-url cases; clean 200 with claims missing is LOW; outright block (403/conn refused) is LOW with blocked=true.
- Do not print or log full page bodies; truncate any debug snippets to 200 chars.
- Do not commit anything; do not touch the DB.
- Do not rewrite functions that already pass selftest — only patch real defects surfaced by verification.

## Spec Reference
**File:** `.loom/PLAN.md`

| Topic | Section |
|---|---|
| Confidence ladder | Hard Rules lines 14-23 |
| Per-host serialization | T7 logic/math |
| Date matching tolerance | T5 acceptance criteria |

## Previous Feedback
Review parse error:


## Tasks

### T1 — Run the selftest and confirm zero failures. This validates classify_block (12 fixtures) and score_row (6 fixtures) without any network I/O.
- **Depends on:** (none)
- **Files:**
  - verify_sources.py
- **Verify:** `cd /Users/zeus/projects/ivy-2028-v2 && python3.13 verify_sources.py --selftest`

**Acceptance criteria:**
- Exit code 0.
- stdout ends with 'OK _selftest: 18 passed, 0 failed' (or higher count if T2 adds fixtures).
- No Python tracebacks.

**Notes:** If selftest fails, STOP and report which fixture failed. Do NOT patch live code until the failing case is reproduced and understood.

### T2 — Add three selftest fixtures for verify_claims to nail down behaviors the reviewer is likely to challenge: (a) 'Jan 10, 2027' matches deadline '2027-01-10'; (b) '$6,500' matches cost '6500'; (c) the word 'scholarship' alone in body matches aid 'Need-based financial aid available'. These already work by inspection — fixtures lock them in.
- **Depends on:** T1
- **Files:**
  - verify_sources.py
- **Verify:** `cd /Users/zeus/projects/ivy-2028-v2 && python3.13 verify_sources.py --selftest 2>&1 | grep -E 'passed, 0 failed'`

**Skeleton:**
```python
def check_claims(label: str, body: str, row: dict, want: dict) -> None:
    nonlocal passed, failed
    got = verify_claims(body, row)
    ok = all(got.get(k) == v for k, v in want.items())
    if ok:
        passed += 1
    else:
        print(f"FAIL {label}: want={want!r}, got={ {k: got.get(k) for k in want}!r}")
        failed += 1

check_claims("date_jan10_comma",
             "Apply by Jan 10, 2027 for the program.",
             {"deadline": "2027-01-10", "cost": "", "aid": ""},
             {"deadline_found": True})
check_claims("cost_comma_dollar",
             "Program fee is $6,500 including housing.",
             {"deadline": "", "cost": "6500", "aid": ""},
             {"cost_found": True})
check_claims("aid_keyword_scholarship",
             "Need-based scholarship available to all admitted students.",
             {"deadline": "", "cost": "", "aid": "Need-based financial aid available"},
             {"prize_found": True})
```

**Acceptance criteria:**
- Three new check_claims fixtures added inside _selftest after the existing score_row block.
- All new fixtures pass on first run (no live-code changes required).
- Total passed count increases by exactly 3.

**Notes:** Place the three checks immediately before the final 'summary = ...' line of _selftest. Reuse the existing 'passed/failed' nonlocals.

### T3 — Smoke-run the verifier end-to-end with --limit 5 against the latest CSV and confirm the output CSV exists, has the expected header columns, and exactly 5 data rows (plus header).
- **Depends on:** T1
- **Files:**
  - (determine during impl)
- **Verify:** `cd /Users/zeus/projects/ivy-2028-v2 && python3.13 verify_sources.py --limit 5 --workers 4 --timeout 15 && OUT=output/2026-05-25-ivy_2028-results-verified.csv && head -1 "$OUT" | grep -E '^name,.*,confidence,reason,blocked,http_status,final_url,deadline_found,cost_found,prize_found,verified_at$' && [ $(wc -l < "$OUT") -eq 6 ]`

**Acceptance criteria:**
- Exit code 0.
- Output CSV header contains all 9 verification columns in order: confidence, reason, blocked, http_status, final_url, deadline_found, cost_found, prize_found, verified_at.
- Exactly 5 data rows.
- stdout shows a final 'Total: 5' summary block.
- Run completes in under 90 seconds (5 fetches with 1s same-host sleeps and 15s timeout each).

**Notes:** Use --workers 4 to mirror the previous smoke run. If any fetch hangs at the 15s timeout boundary, that is acceptable — selftest already covers the timeout path.

### T4 — Fix one quiet defect in verify_csv: the post-loop block at lines 605-608 increments manual_review for no-url rows, but those rows were already pre-filled into results[] *before* the futures loop. The futures loop's running counters (high/low/manual_review) only count host-grouped rows, so the post-loop adjustment is correct in intent. However, the `completed` counter is also incremented in that same block — and `completed` is only used by the progress print inside the futures loop, so incrementing it after the loop is dead. Remove `completed += 1` from the post-loop block to avoid a misleading variable mutation. Do NOT change the manual_review increment.
- **Depends on:** T3
- **Files:**
  - verify_sources.py
- **Verify:** `cd /Users/zeus/projects/ivy-2028-v2 && python3.13 verify_sources.py --selftest && python3.13 verify_sources.py --limit 5 --workers 4 && grep -A4 'Count no-url rows' verify_sources.py | grep -v 'completed += 1'`

**Logic / math:**
Inside verify_csv, after the `with ThreadPoolExecutor(...)` block:
BEFORE:
  for idx in no_url_indices:
      if results[idx] is not None:
          manual_review += 1
          completed += 1
AFTER:
  for idx in no_url_indices:
      if results[idx] is not None:
          manual_review += 1

**Acceptance criteria:**
- The `completed += 1` line in the no-url post-loop block is removed.
- The `manual_review += 1` line in the no-url post-loop block is preserved.
- Selftest still passes (no behavioral change).
- Smoke run total in the printed summary still equals input row count.

**Notes:** This is a 1-line deletion. Resist the urge to refactor the counter logic — the reviewer will flag any drive-by changes.

### T5 — Add a one-line warning when no rows have URLs (defensive — never observed today, but coordinator.py treats empty inputs as a hard error and the reviewer will ask).
- **Depends on:** T4
- **Files:**
  - verify_sources.py
- **Verify:** `cd /Users/zeus/projects/ivy-2028-v2 && python3.13 -c "
import tempfile, csv, os
from verify_sources import verify_csv
with tempfile.TemporaryDirectory() as d:
    inp = os.path.join(d,'in.csv'); out = os.path.join(d,'out.csv')
    with open(inp,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['name','url','deadline','cost','aid']); w.writerow(['x','','','',''])
    c = verify_csv(inp, out, workers=1, timeout=5, limit=0)
    print('OK', c['manual_review']==1 and c['high']==0)
"`

**Logic / math:**
After computing host_groups and no_url_indices, if not host_groups and no_url_indices:
    print(f"warning: {len(no_url_indices)} rows have no URL — all marked MANUAL_REVIEW", flush=True)

**Acceptance criteria:**
- The temp-CSV smoke above prints 'OK True'.
- The warning prints exactly once when no URLs are present.
- No warning prints when at least one row has a URL.
- No selftest regression.

**Notes:** Place the warning between the `for idx in no_url_indices: results[idx] = dict(EMPTY_URL_VERDICT)` block and the `def process_host` definition. One line of code, no helper.

### T6 — Final verification: re-run selftest and full smoke, confirm both green, and print a one-line summary of HIGH/LOW/MANUAL_REVIEW from the existing verified CSV as a sanity check for the reviewer.
- **Depends on:** T2, T5
- **Files:**
  - (determine during impl)
- **Verify:** `cd /Users/zeus/projects/ivy-2028-v2 && python3.13 verify_sources.py --selftest && python3.13 verify_sources.py --limit 5 --workers 4 && python3.13 -c "
import csv
rows = list(csv.DictReader(open('output/2026-05-25-ivy_2028-results-verified.csv')))
from collections import Counter
c = Counter(r['confidence'] for r in rows)
assert sum(c.values()) == 5, c
assert set(c.keys()) <= {'HIGH','LOW','MANUAL_REVIEW'}, c
print('SUMMARY', dict(c))
"`

**Acceptance criteria:**
- Selftest passes (21 passed, 0 failed — the original 18 plus 3 from T2).
- Smoke run exits 0.
- All 5 output rows have confidence ∈ {HIGH, LOW, MANUAL_REVIEW}.
- No 'matched_terms' column leaks into the output CSV (it should be internal-only).

**Notes:** If the SUMMARY shows all 5 rows are LOW with reason=='blocked', this is real-world data; don't 'fix' the verifier. Report it in the implementer's commit message so the reviewer sees expected behavior.

---
Generated by the loom harness. The implementer must read this file for task context.