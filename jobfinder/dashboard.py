"""Local dashboard/tracker — review the honest shortlist and capture corrections.

Runs a tiny localhost HTTP server (Python stdlib, no extra dependency, bound to
127.0.0.1 — data never leaves your machine). It renders the scored results and
turns one-click corrections into persistent feedback (data/feedback.*), which the
scorer replays on the next run. This is where the feedback loop lives.

    python -m jobfinder dashboard           # opens http://127.0.0.1:8755
"""

from __future__ import annotations

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import feedback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "data", "results", "scored.jsonl")


def _load_jobs() -> list[dict]:
    if not os.path.exists(RESULTS):
        return []
    jobs = []
    for ln in open(RESULTS, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            try:
                jobs.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    def fit(j):
        try:
            return float(j.get("fit_score", 0))
        except (TypeError, ValueError):
            return 0.0
    jobs.sort(key=fit, reverse=True)
    return jobs


PAGE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Job Finder India — honest shortlist</title>
<style>
 :root{--bg:#0f1115;--card:#181b22;--mut:#8b93a7;--line:#262b36;--fg:#e7eaf0}
 *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);
   font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
 header{padding:20px 28px;border-bottom:1px solid var(--line)}
 h1{margin:0;font-size:19px} .sub{color:var(--mut);font-size:13px;margin-top:4px}
 .wrap{max-width:1000px;margin:0 auto;padding:22px 28px}
 .job{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
 .top{display:flex;gap:12px;align-items:flex-start}
 .score{font-size:22px;font-weight:700;min-width:46px}
 .badge{font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;letter-spacing:.3px}
 .APPLY{background:#0f3d24;color:#5fe39b} .STRETCH{background:#3d340f;color:#e7c45f}
 .DONT{background:#3d1414;color:#ff9b9b}
 .title{font-weight:600} .meta{color:var(--mut);font-size:13px;margin-top:2px}
 .reason{font-size:13.5px;margin:10px 0;color:#c7cdda}
 .quals{margin:8px 0;font-size:12.5px} .quals summary{cursor:pointer;color:#aab2c5}
 .qrow{padding:2px 0 2px 14px;color:#c7cdda} .qev{color:#8b93a7}
 .qmet{color:#5fe39b} .qpart{color:#e7c45f} .qmiss{color:#ff9b9b}
 a.link{color:#7aa2ff;text-decoration:none;font-size:13px} a.link:hover{text-decoration:underline}
 .vsrc{font-size:11px;color:var(--mut);border:1px solid var(--line);padding:1px 6px;border-radius:6px;margin-left:6px}
 .acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
 button{background:#222734;color:var(--fg);border:1px solid var(--line);border-radius:8px;
   padding:6px 10px;font-size:12.5px;cursor:pointer} button:hover{border-color:#3a4458}
 button.good:hover{border-color:#5fe39b;color:#5fe39b} button.bad:hover{border-color:#ff9b9b;color:#ff9b9b}
 .note{background:#0f1115;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:6px 8px;font-size:12.5px;flex:1;min-width:140px}
 .done{opacity:.5} .tag{font-size:12px;color:#5fe39b;margin-left:8px}
 .empty{color:var(--mut);padding:40px;text-align:center}
</style></head><body>
<header><h1>Job Finder India — honest shortlist</h1>
<div class=sub id=sub>loading…</div></header>
<div class=wrap id=list></div>
<script>
const ACTIONS=[["good_match","Good match","good"],["applied","Applied","good"],
 ["wouldnt_apply","Wouldn't apply","bad"],["wrong_location","Wrong location","bad"],
 ["wrong_level","Wrong level","bad"],["wrong_function","Wrong function","bad"],
 ["wrong_domain","Wrong domain","bad"]];
function badge(v){return v==="APPLY"?"APPLY":v==="STRETCH"?"STRETCH":"DONT"}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function qual(j){
 if(!j.qualifications||!j.qualifications.length) return '';
 const ic={met:'✓',partial:'~',missing:'✗'}, cl={met:'qmet',partial:'qpart',missing:'qmiss'};
 const s=j.qualifications_summary||{};
 const sum=`<b class=qmet>${s.met||0} met</b> · <b class=qpart>${s.partial||0} partial</b> · <b class=qmiss>${s.missing||0} missing</b>`;
 const rows=j.qualifications.map(q=>`<div class="qrow ${cl[q.status]||''}">${ic[q.status]||'•'} ${esc(q.requirement)}${(q.evidence&&q.status!=='met')?` <span class=qev>— ${esc(q.evidence)}</span>`:''}</div>`).join('');
 return `<details class=quals><summary>Qualifications match — ${sum}</summary>${rows}</details>`;
}
async function load(){
 const r=await fetch('/api/data'); const d=await r.json();
 const fb=d.stats||{}; const fbn=Object.values(fb).reduce((a,b)=>a+b,0);
 document.getElementById('sub').textContent=
   `${d.jobs.length} scored · ${d.jobs.filter(j=>j.verdict==='APPLY').length} APPLY · `+
   `${d.jobs.filter(j=>j.verdict==='STRETCH').length} STRETCH · `+
   `${d.jobs.filter(j=>(j.verdict||'').startsWith("DON")).length} DON'T · ${fbn} corrections saved`;
 const L=document.getElementById('list');
 if(!d.jobs.length){L.innerHTML='<div class=empty>No scored results yet. Run a search + scoring first.</div>';return}
 L.innerHTML='';
 for(const j of d.jobs){
   const v=(j.verdict||'').startsWith('DON')?'DON\\'T APPLY':j.verdict;
   const el=document.createElement('div'); el.className='job';
   const vlabel = j.link_verified? `<span class=vsrc>✓ ${esc(j.link_source||'verified')}</span>`:'';
   el.innerHTML=`<div class=top><div class=score>${(+j.fit_score).toFixed(1)}</div>
     <div style=flex:1>
       <span class="badge ${badge(j.verdict)}">${esc(v)}</span>
       <span class=title> ${esc(j.title)}</span>
       <div class=meta>${esc(j.company)} · ${esc(j.location||'')} ${vlabel}</div>
       <div class=reason>${esc(j.headline||'')}</div>
       ${qual(j)}
       ${j.url?`<a class=link href="${esc(j.url)}" target=_blank rel=noopener>open verified JD ↗</a>`:''}
       <div class=acts id="acts-${esc(j.job_id)}">
         <input class=note placeholder="why? (optional)" id="note-${esc(j.job_id)}">
         ${ACTIONS.map(a=>`<button class="${a[2]}" onclick="rec('${esc(j.job_id)}',${JSON.stringify(a[0])},this)">${a[1]}</button>`).join('')}
       </div>
     </div></div>`;
   el.dataset.j=JSON.stringify({job_id:j.job_id,company:j.company,title:j.title,url:j.url});
   L.appendChild(el);
 }
}
async function rec(id,action,btn){
 const card=btn.closest('.job'); const j=JSON.parse(card.dataset.j);
 const note=document.getElementById('note-'+id).value||'';
 await fetch('/api/feedback',{method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({...j,action,note})});
 card.classList.add('done');
 const acts=document.getElementById('acts-'+id);
 acts.innerHTML=`<span class=tag>✓ saved: ${action.replace('_',' ')} — will retune next run</span>`;
 load_stats();
}
async function load_stats(){const r=await fetch('/api/data');const d=await r.json();
 const fbn=Object.values(d.stats||{}).reduce((a,b)=>a+b,0);
 const s=document.getElementById('sub'); s.textContent=s.textContent.replace(/\\d+ corrections saved/,fbn+' corrections saved');}
load();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # quiet
        pass

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif self.path.startswith("/api/data"):
            self._send(200, json.dumps({"jobs": _load_jobs(), "stats": feedback.stats()}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self.path.startswith("/api/feedback"):
            return self._send(404, json.dumps({"error": "not found"}))
        n = int(self.headers.get("Content-Length", 0))
        try:
            d = json.loads(self.rfile.read(n) or b"{}")
            entry = feedback.record(d.get("job_id", ""), d.get("company", ""),
                                    d.get("title", ""), d.get("url", ""),
                                    d.get("action", ""), d.get("note", ""))
            self._send(200, json.dumps({"ok": True, "entry": entry}))
        except Exception as e:
            self._send(400, json.dumps({"ok": False, "error": str(e)}))


def serve(port: int = 8755, open_browser: bool = True) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"job-finder dashboard → {url}  (local only; Ctrl-C to stop)")
    if not os.path.exists(RESULTS):
        print(f"  note: no scored results at {RESULTS} yet — run a search+scoring first.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        srv.server_close()
    return 0
