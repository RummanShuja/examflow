"""Self-contained, offline HTML report; no servers or external assets."""
from collections import Counter
from html import escape
from pathlib import Path
from string import Template
import json

from .common import minutes


def percent(value):
    return "n/a" if value is None else f"{value*100:.2f}%"


def render(conn, root, metrics, validation, evaluation, reproducibility, assignments):
    root = Path(root)
    def e(value):
        return escape(str(value), quote=True)
    exams = {r["exam_id"]: dict(r) for r in conn.execute("SELECT * FROM Exam")}
    reqs = {r["exam_id"]: dict(r) for r in conn.execute("SELECT * FROM ExamRequirement")}
    rows = []
    for a in sorted(assignments, key=lambda x: (x["starts_at"], x["room_id"], x["exam_id"])):
        req = reqs[a["exam_id"]]
        search = " ".join((a["exam_id"], a["room_id"], exams[a["exam_id"]]["title"], *a["invigilator_ids"]))
        rows.append(f'<tr data-search="{e(search.lower())}"><td><strong>{e(a["exam_id"])}</strong><small>{e(exams[a["exam_id"]]["title"])}</small></td>'
                    f'<td>{e(a["starts_at"][:10])}<small>{e(a["starts_at"][11:16])} - {e(a["ends_at"][11:16])} IST</small></td>'
                    f'<td>{e(a["room_id"])}</td><td>{req["enrolled_count"]}</td><td>{minutes(a["starts_at"],a["ends_at"])} min'
                    f'<small>Extra time: {req["max_extra_percent"]}%</small></td><td title="{e(", ".join(a["invigilator_ids"]))}">{len(a["invigilator_ids"])} staff</td></tr>')
    exceptions = []
    for o in conn.execute("SELECT * FROM ExamOutcome WHERE run_id=? AND status='UNASSIGNED' ORDER BY exam_id", (metrics["run_id"],)):
        evidence = json.loads(o["evidence_json"])
        exceptions.append(f'<article class="exception"><span class="badge amber">{e(o["reason_code"])}</span><h3>{e(o["exam_id"])}</h3>'
                          f'<p>{e(evidence["explanation"])}</p><details><summary>Decision evidence</summary><pre>{e(json.dumps(evidence,indent=2))}</pre></details></article>')
    evaluation_rows = []
    for rule, r in evaluation["per_rule"].items():
        evaluation_rows.append(f'<tr><td>{e(rule)}</td><td>{r["tp"]}</td><td>{r["fp"]}</td><td>{r["fn"]}</td><td>{percent(r["precision"])}</td><td>{percent(r["recall"])}</td></tr>')
    daily = Counter(a["starts_at"][:10] for a in assignments)
    bars = "".join(f'<div class="barrow"><span>{e(day)}</span><div class="track"><div style="width:{n/max(daily.values())*100:.2f}%"></div></div><b>{n}</b></div>' for day, n in sorted(daily.items()))
    totals = metrics["source_counts"]
    good = validation["passed"] and evaluation["passed"] and reproducibility["passed"]
    statuses = f'<span class="badge {"green" if good else "amber"}">{"All checks passed" if good else "Review check results"}</span>'
    template = Template('''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ExamFlow | Scheduling report</title>
<style>
:root{--ink:#152a36;--muted:#5a6f76;--paper:#f5f7f4;--card:white;--line:#dae4df;--teal:#147d71;--navy:#163641;--amber:#8b5204}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
a{color:var(--teal);text-underline-offset:3px}header{background:var(--navy);color:white;padding:34px max(24px,calc((100vw - 1200px)/2)) 42px}nav{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}.brand{font-size:21px;font-weight:760;letter-spacing:-.6px}.brand span{color:#88dbb6}nav div{display:flex;gap:20px;flex-wrap:wrap}nav a{color:#c9ddd7;text-decoration:none;font-size:13px}h1{font-size:clamp(32px,5vw,50px);line-height:1.12;letter-spacing:-1.6px;margin:38px 0 16px;max-width:800px}header p{color:#bbd0d0;max-width:770px}main{max-width:1248px;margin:0 auto;padding:28px 24px 60px}section{scroll-margin-top:20px;margin-bottom:32px}h2{font-size:23px;letter-spacing:-.6px;margin:0 0 8px}h3{font-size:17px;margin:10px 0}.eyebrow{text-transform:uppercase;font-size:11px;font-weight:700;letter-spacing:2px;color:#95d5c1}.subtle,small{color:var(--muted)}.grid{display:grid;gap:16px;grid-template-columns:repeat(4,minmax(0,1fr))}.card,.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px}.card label{font-size:12px;color:var(--muted);display:block}.value{font-size:35px;line-height:1.35;font-weight:730;letter-spacing:-1px}.card small{font-size:12px;display:block}.split{display:grid;grid-template-columns:1.1fr 1fr;gap:20px;margin-top:20px}.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.3px}.green{background:#e4f6ec;color:#126340}.amber{background:#fff0d4;color:var(--amber)}.header-meta{display:flex;align-items:center;gap:16px;flex-wrap:wrap;color:#cee4db;font-size:12px;margin-top:24px}.barrow{display:flex;align-items:center;gap:12px;font-size:12px;margin:16px 0}.barrow span{width:88px}.barrow b{width:28px;text-align:right}.track{height:12px;flex:1;background:#edf3f0;border-radius:10px;overflow:hidden}.track div{height:100%;background:var(--teal);border-radius:10px}.metric{margin:16px 0}.metric-top{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px}.note{font-size:12px;color:var(--muted);margin-bottom:0}.toolbar{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap;margin:20px 0}input{font:inherit;padding:10px 13px;border:1px solid #bbcec6;border-radius:8px;min-width:290px;max-width:100%;background:white;color:var(--ink)}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:12px;background:white}table{border-collapse:collapse;width:100%;font-size:12px;white-space:nowrap}th{text-align:left;color:var(--muted);background:#edf2ef;padding:12px 16px;font-size:11px;text-transform:uppercase;letter-spacing:.5px}td{padding:13px 16px;border-top:1px solid #e6ece8;vertical-align:top}td small{display:block;font-size:11px}tbody tr:hover{background:#f7faf8}.exception{border-left:4px solid #d1982c;background:#fff;padding:22px;border-radius:0 12px 12px 0;margin-top:16px}.exception p{max-width:850px;font-size:13px}summary{cursor:pointer;color:var(--teal);font-size:12px}pre{overflow:auto;white-space:pre-wrap;font-size:12px;background:#f0f4f1;padding:14px;border-radius:8px}ul{padding-left:20px}.links{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;margin:16px 0}.checks{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}.checks span{background:#e6f3ec;color:#185b42;padding:8px 12px;border-radius:8px;font-size:12px}.actors{font-size:13px}.actors p{margin:10px 0}footer{border-top:1px solid var(--line);padding-top:22px;font-size:12px;color:var(--muted)}button{font:inherit;font-size:12px;padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:white;cursor:pointer}
@media(max-width:850px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.split{grid-template-columns:1fr}header{padding:26px 24px 32px}}@media(max-width:460px){main{padding:20px 16px}.grid{gap:10px}.card{padding:16px}.value{font-size:29px}input{min-width:0;width:100%}}@media print{header{background:white;color:var(--ink);padding:0}nav,button,input{display:none}header p,.header-meta{color:var(--muted)}main{padding:0}.table-wrap{overflow:visible}section{break-inside:avoid}.card,.panel{box-shadow:none}h1{font-size:30px;margin-top:20px}}
</style></head><body>
<header><nav><a class="brand" href="#overview" style="color:white">exam<span>flow</span></a><div><a href="#schedule">Timetable</a><a href="#exceptions">Exceptions</a><a href="#verification">Verification</a><a href="#outputs">Outputs</a></div></nav>
<div class="eyebrow" style="margin-top:38px">Academic operations / November 2026</div><h1>A timetable with every<br>decision accounted for.</h1><p>Enrollment, equipment, access needs and staffing, reconciled in one traceable run. Synthetic data. All times Asia/Kolkata (IST); intervals include the start and exclude the end.</p>
<div class="header-meta">$status <span>$run</span><span>Seed 20261022 (see manifest for configuration)</span><span>$sources</span></div></header>
<main><section id="overview"><div class="grid">
<div class="card"><label>EXAMS SCHEDULED</label><div class="value">$scheduled<span style="font-size:18px;color:var(--muted)"> / $eligible</span></div><small>$rate of planned exams</small></div>
<div class="card"><label>REQUIRES ATTENTION</label><div class="value">$unassigned</div><small>$cancelled cancelled exam excluded</small></div>
<div class="card"><label>HARD VIOLATIONS</label><div class="value">$violations</div><small>Independent source + timetable audit</small></div>
<div class="card"><label>ACCOMMODATION COVERAGE</label><div class="value">$accommodation</div><small>Approved support on scheduled exams</small></div></div>
<div class="split"><div class="panel"><h3>Examinations by day</h3><p class="note">Greedy first-feasible placements; no optimality or workload-balance guarantee.</p>$bars</div>
<div class="panel"><h3>Resource use</h3>$utilization<p class="note">Denominators cover all available resources across the full ten-weekday horizon, including idle periods. Room closures, retired rooms and effective capacities are applied.</p><p class="note">Occupied-room seat fill: <strong>$fill</strong>. Whole-exam extra-time policy consumes $extra additional room-minutes.</p></div></div></section>
<section id="schedule"><h2>Accepted timetable</h2><p class="subtle">One room per exam. Hover over staff counts for the allocated identifiers.</p><div class="toolbar"><label for="search" class="subtle">Find an exam or resource</label><input id="search" type="search" placeholder="Exam, course, room or invigilator" autocomplete="off"><span class="subtle" id="count">$scheduled exams</span></div>
<div class="table-wrap"><table id="timetable"><thead><tr><th>Exam / course</th><th>Date / interval</th><th>Room</th><th>Learners</th><th>Duration</th><th>Invigilators</th></tr></thead><tbody>$rows</tbody></table></div></section>
<section id="exceptions"><h2>Exceptions with reasons</h2><p class="subtle">The accepted schedule stays valid. Every planned exam has an assignment or an explicit unassigned outcome.</p>$exceptions</section>
<section id="verification"><h2>Verification you can inspect</h2><div class="checks"><span>Source integrity: $source_check</span><span>Room + staff totals: $usage_check</span><span>Two independent builds: $repro_check</span><span>$graph</span></div>
<p class="subtle">Fixture evaluation: $tp true positives, $fp false positives, $fn false negatives. Eight hand-crafted cases cover five failures, a clean control, adjacent intervals and exact capacity. These results demonstrate regression coverage, not general detection accuracy. “n/a” means the fixture set has no relevant denominator.</p>
<div class="table-wrap"><table><thead><tr><th>Rule</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th><th>Recall</th></tr></thead><tbody>$evaluation_rows</tbody></table></div>
<div class="links"><a href="validation_summary.json">Validation details</a><a href="evaluation.json">Fixture predictions</a><a href="reproducibility.json">Per-table reproducibility</a><a href="metrics.json">Metric values + denominators</a></div></section>
<section id="outputs"><h2>From decisions to action</h2><div class="split"><div class="panel actors"><h3>Who uses this</h3><p><strong>Learner:</strong> retrieve enrolled exams with the student CLI lookup.</p><p><strong>Instructor:</strong> review course timing and extended durations.</p><p><strong>Academic administrator:</strong> inspect assignments and resolve exceptions.</p><p><strong>Support staff:</strong> verify accessible rooms and approved support.</p><p><strong>Platform administrator:</strong> rerun, audit events, validate and export.</p></div><div class="panel"><h3>Portable outputs</h3><div class="links"><a href="assignments.csv">Timetable CSV</a><a href="assignments.json">Timetable JSON</a><a href="unassigned.csv">Unassigned CSV</a><a href="invigilator_allocations.csv">Staff allocations</a><a href="room_usage.csv">Room use</a><a href="invigilator_usage.csv">Staff use</a><a href="exports/database_seed.sql">SQL seed</a><a href="source_manifest.json">Source manifest</a><a href="checksums.json">Checksums</a><a href="fixtures/ground_truth.json">Evaluation ground truth</a></div><p class="note">Read docs/WALKTHROUGH.md for algorithm choices and limitations. Database: examflow.sqlite3, beside this report. Source fixtures and answers are stored separately.</p></div></div></section>
<footer>ExamFlow · Project by Rumman Shuja · Python + SQLite · traceable scheduling decisions. <button onclick="window.print()" style="float:right">Print report</button></footer>
</main><script>
const input=document.getElementById('search');const tableRows=Array.from(document.querySelectorAll('#timetable tbody tr'));input.addEventListener('input',()=>{const q=input.value.trim().toLowerCase();let count=0;tableRows.forEach(row=>{const show=row.dataset.search.includes(q);row.hidden=!show;if(show)count++;});document.getElementById('count').textContent=count+' exams';});
</script></body></html>''')
    utilization = ""
    for label, value in (("Room time", metrics["room_time"]["utilization"]), ("Student seat time", metrics["seat_time"]["utilization"]), ("Invigilator time", metrics["invigilator_time"]["utilization"])):
        utilization += f'<div class="metric"><div class="metric-top"><span>{label}</span><b>{percent(value)}</b></div><div class="track"><div style="width:{min(100,(value or 0)*100):.2f}%"></div></div></div>'
    values = dict(status=statuses, run=e(metrics["run_id"]), sources=e(f'{totals["Student"]:,} learners / {totals["Room"]} rooms / {totals["Invigilator"]} invigilators'),
                  scheduled=metrics["scheduled"], eligible=metrics["eligible"], rate=percent(metrics["scheduling_rate"]),
                  unassigned=metrics["unassigned"], cancelled=metrics["cancelled"], violations=validation["violation_count"],
                  accommodation=percent(metrics["accommodations"]["coverage_scheduled"]), bars=bars, utilization=utilization,
                  fill=percent(metrics["seat_time"]["occupied_room_fill"]), extra=metrics["accommodations"]["extra_room_minutes"],
                  rows="\n".join(rows), exceptions="\n".join(exceptions) or '<div class="panel">No unassigned exams.</div>',
                  source_check="passed" if validation["source"]["passed"] else "failed", usage_check="passed" if validation["usage_reconciliation"]["passed"] else "failed",
                  repro_check="matched" if reproducibility["passed"] else "failed", graph=f'{metrics["conflict_graph"]["vertices"]} vertices / {metrics["conflict_graph"]["edges"]:,} conflict edges',
                  tp=evaluation["micro"]["tp"], fp=evaluation["micro"]["fp"], fn=evaluation["micro"]["fn"], evaluation_rows="\n".join(evaluation_rows))
    seed = json.loads(conn.execute("SELECT config_json FROM Dataset").fetchone()[0])["seed"]
    html = template.substitute(values).replace("Seed 20261022 (", f"Seed {seed} (")
    (root / "report.html").write_text(html, encoding="utf-8")
