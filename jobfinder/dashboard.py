"""Local dashboard/tracker — review the honest shortlist and capture corrections.

Runs a tiny localhost HTTP server (Python stdlib, no extra dependency, bound to
127.0.0.1 — data never leaves your machine). It shows the APPLY/STRETCH shortlist
(DON'T-APPLY hidden behind a toggle), and turns one-click calls — Applied, or
Wouldn't apply (+reason) — into persistent feedback (data/feedback.*) that the
scorer replays next run. Latest choice per job wins; every call is undoable.

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
 :root{--bg:#0e1014;--card:#161a21;--card2:#1b212a;--line:#252b35;--fg:#e8ebf1;
   --mut:#9099ab;--met:#4ade80;--part:#fbbf24;--miss:#f87171;--blue:#7aa2ff}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);
   font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 header{padding:22px 28px 18px;border-bottom:1px solid var(--line);position:sticky;top:0;
   background:rgba(14,16,20,.92);backdrop-filter:blur(6px);z-index:5}
 h1{margin:0;font-size:18px;font-weight:600;letter-spacing:.2px}
 .sub{color:var(--mut);font-size:12.5px;margin-top:5px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
 .pill{padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600}
 .p-apply{background:#11331f;color:var(--met)} .p-stretch{background:#33290d;color:var(--part)}
 .p-dont{background:#331515;color:var(--miss)}
 .wrap{max-width:860px;margin:0 auto;padding:20px 24px 70px}
 .job{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:14px 0}
 .row1{display:flex;gap:14px;align-items:center}
 .score{font-size:26px;font-weight:700;min-width:50px;text-align:center;line-height:1}
 .score small{display:block;font-size:10px;color:var(--mut);font-weight:500;margin-top:3px}
 .s-apply{color:var(--met)} .s-stretch{color:var(--part)} .s-dont{color:var(--miss)}
 .ttl{font-size:15px;font-weight:600} .meta{color:var(--mut);font-size:12.5px;margin-top:3px}
 .vsrc{border:1px solid var(--line);border-radius:6px;padding:0 6px;margin-left:4px;font-size:11px;color:var(--mut)}
 ul.why{margin:12px 0 4px;padding-left:18px} ul.why li{margin:3px 0;color:#cfd5e0}
 .quals{margin:12px 0 4px;background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
 .qsum{font-size:12.5px;color:var(--mut);margin-bottom:8px}
 .cmet{color:var(--met)} .cpart{color:var(--part)} .cmiss{color:var(--miss)}
 .qgrp{margin:6px 0} .qh{font-size:12px;font-weight:600;margin-bottom:2px}
 .qgrp ul{margin:0 0 4px;padding-left:20px} .qgrp li{margin:2px 0;font-size:12.5px;color:#cfd5e0}
 .qgrp .ev{color:var(--mut)}
 .skills{font-size:12px;color:var(--mut);margin:8px 0 2px}
 a.link{color:var(--blue);text-decoration:none;font-size:12.5px;display:inline-block;margin:6px 0 2px}
 a.link:hover{text-decoration:underline}
 .acts,.reasons{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:12px}
 .acts{border-top:1px solid var(--line);padding-top:12px}
 .reasons{margin-top:8px}
 .lbl{font-size:11.5px;color:var(--mut);margin-right:2px}
 button.act{background:var(--card2);color:var(--fg);border:1px solid var(--line);
   border-radius:8px;padding:6px 12px;font-size:12.5px;cursor:pointer;transition:all .12s}
 button.act.good:hover,button.act.good.on{border-color:var(--met);color:var(--met)}
 button.act.bad:hover,button.act.bad.on{border-color:var(--miss);color:var(--miss)}
 button.chip{background:var(--bg);color:var(--mut);border:1px solid var(--line);
   border-radius:999px;padding:4px 11px;font-size:12px;cursor:pointer}
 button.chip:hover{border-color:var(--miss);color:var(--miss)}
 .saved{font-size:12.5px;color:var(--met);margin-top:12px;border-top:1px solid var(--line);padding-top:12px}
 .saved.neg{color:var(--miss)} .change{color:var(--blue);cursor:pointer;margin-left:10px;font-size:12px}
 .change:hover{text-decoration:underline}
 .toggle{background:none;border:1px dashed var(--line);color:var(--mut);border-radius:8px;
   padding:8px 14px;font-size:12.5px;cursor:pointer;margin:18px 0 4px;width:100%}
 .toggle:hover{border-color:var(--mut);color:var(--fg)}
 .empty{color:var(--mut);padding:50px;text-align:center}
</style></head><body>
<header><h1>Job Finder India <span style="color:var(--mut);font-weight:400">— honest shortlist</span></h1>
<div class=sub id=sub>loading…</div></header>
<div class=wrap><div id=list></div><div id=hidden></div></div>
<script>
const REASONS=[["wrong_location","Wrong location"],["wrong_level","Wrong level"],
 ["wrong_function","Wrong function"],["wrong_domain","Wrong domain"],
 ["wrong_comp","Comp too low"],["wouldnt_apply","Just passing"]];
const esc=s=>(s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const vkey=v=>(v||"").startsWith("DON")?"dont":v==="APPLY"?"apply":"stretch";
const vlabel=v=>(v||"").startsWith("DON")?"DON'T APPLY":v;

function whyBullets(h){
 if(!h) return "";
 let t=h.replace(/^\\s*(APPLY|STRETCH|DON'?T APPLY)\\s*[\\u2014\\-]\\s*/i,"");
 const parts=t.split(/;\\s+|\\s\\u2014\\s/).map(x=>x.trim()).filter(Boolean);
 return "<ul class=why>"+parts.map(p=>`<li>${esc(p)}</li>`).join("")+"</ul>";
}
function qualsBlock(j){
 if(!j.qualifications||!j.qualifications.length) return "";
 const g={met:[],partial:[],missing:[]};
 j.qualifications.forEach(q=>(g[q.status]||g.missing).push(q));
 const s=j.qualifications_summary||{met:g.met.length,partial:g.partial.length,missing:g.missing.length};
 const sec=(k,label,cls)=>g[k].length?`<div class=qgrp><div class="qh ${cls}">${label} (${g[k].length})</div><ul>`+
   g[k].map(q=>`<li>${esc(q.requirement)}${(q.evidence&&k!=='met')?` <span class=ev>— ${esc(q.evidence)}</span>`:''}</li>`).join("")+`</ul></div>`:"";
 return `<div class=quals><div class=qsum>Qualifications match — `+
   `<b class=cmet>${s.met} met</b> · <b class=cpart>${s.partial} partial</b> · <b class=cmiss>${s.missing} missing</b></div>`+
   sec("met","✓ Met","cmet")+sec("partial","~ Partial","cpart")+sec("missing","✗ Missing","cmiss")+`</div>`;
}
function skillsLine(j){
 const s=j.skills_check; if(!s) return "";
 const seg=(arr,cls,ic)=>(arr&&arr.length)?`<span class=${cls}>${ic} ${esc(arr.join(", "))}</span>`:"";
 const segs=[seg(s.met,"cmet","✓"),seg(s.partial,"cpart","~"),seg(s.missing,"cmiss","✗")].filter(Boolean);
 return segs.length?`<div class=skills><span class=lbl>Skills (auto-checked):</span> ${segs.join(" &nbsp; ")}</div>`:"";
}
function updateSub(d){
 const fbn=Object.values(d.stats||{}).reduce((a,b)=>a+b,0);
 const n=v=>d.jobs.filter(j=>vkey(j.verdict)===v).length;
 document.getElementById("sub").innerHTML=
   `<span class="pill p-apply">${n("apply")} APPLY</span>`+
   `<span class="pill p-stretch">${n("stretch")} STRETCH</span>`+
   `<span class="pill p-dont">${n("dont")} filtered out</span>`+
   `<span>${fbn} call${fbn==1?"":"s"} saved</span>`;
}
async function post(url,j){return (await fetch(url,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(j)})).json();}

function mountActions(card,j){
 const host=card.querySelector(".actionhost"); host.innerHTML="";
 const acts=document.createElement("div"); acts.className="acts";
 acts.innerHTML=`<span class=lbl>Your call:</span>`;
 const applied=document.createElement("button"); applied.className="act good"; applied.textContent="✓ Applied";
 const wont=document.createElement("button"); wont.className="act bad"; wont.textContent="✗ Wouldn't apply";
 acts.append(applied,wont); host.append(acts);
 applied.addEventListener("click",()=>save(card,j,"applied"));
 wont.addEventListener("click",()=>{
   if(host.querySelector(".reasons")) return;
   const r=document.createElement("div"); r.className="reasons"; r.innerHTML=`<span class=lbl>Reason:</span>`;
   REASONS.forEach(([a,label])=>{const c=document.createElement("button");c.className="chip";c.textContent=label;
     c.addEventListener("click",()=>save(card,j,a)); r.append(c);});
   host.append(r);
 });
}
async function save(card,j,action){
 await post("/api/feedback",{job_id:j.job_id,company:j.company,title:j.title,url:j.url,action});
 const host=card.querySelector(".actionhost");
 const positive=action==="applied";
 const txt=action==="applied"?"tracked as applied — won't be re-recommended"
   :action==="wouldnt_apply"?"passed — won't be re-recommended"
   :`won't apply (${action.replace("wrong_","wrong ")}) — will retune scoring`;
 host.innerHTML=`<div class="saved ${positive?'':'neg'}">✓ ${txt}<span class=change>change</span></div>`;
 host.querySelector(".change").addEventListener("click",async()=>{await post("/api/undo",{job_id:j.job_id});mountActions(card,j);refreshSub();});
 refreshSub();
}
async function refreshSub(){updateSub(await (await fetch("/api/data")).json());}

function makeCard(j){
 const vk=vkey(j.verdict);
 const el=document.createElement("div"); el.className="job";
 const vsrc=j.link_verified?`<span class=vsrc>✓ ${esc(j.link_source||"verified")}</span>`:"";
 el.innerHTML=
   `<div class=row1>
      <div class="score s-${vk}">${(+j.fit_score).toFixed(1)}<small>${esc((j.score_range&&j.score_range[0]!=j.score_range[1])?j.score_range.join("–"):"")}</small></div>
      <div style="flex:1">
        <span class="pill p-${vk}">${vlabel(j.verdict)}</span>
        <span class=ttl> ${esc(j.title)}</span>
        <div class=meta>${esc(j.company)} · ${esc(j.location||"")} ${vsrc}</div>
      </div>
    </div>
    ${whyBullets(j.headline)}${qualsBlock(j)}${skillsLine(j)}
    ${j.url?`<a class=link href="${esc(j.url)}" target=_blank rel=noopener>open verified JD ↗</a>`:""}
    <div class=actionhost></div>`;
 mountActions(el,j);
 return el;
}
async function load(){
 const d=await (await fetch("/api/data")).json(); updateSub(d);
 const L=document.getElementById("list"), H=document.getElementById("hidden");
 L.innerHTML=""; H.innerHTML="";
 if(!d.jobs.length){L.innerHTML="<div class=empty>No scored results yet. Run a search + scoring first.</div>";return;}
 const show=d.jobs.filter(j=>vkey(j.verdict)!=="dont");
 const dont=d.jobs.filter(j=>vkey(j.verdict)==="dont");
 if(!show.length) L.innerHTML="<div class=empty>No APPLY/STRETCH roles in this run. Widen discovery, or reveal the filtered-out roles below.</div>";
 show.forEach(j=>L.appendChild(makeCard(j)));
 if(dont.length){
   const t=document.createElement("button"); t.className="toggle";
   t.textContent=`▸ Show ${dont.length} filtered-out roles (DON'T APPLY) — for auditing`;
   let open=false;
   t.addEventListener("click",()=>{open=!open;
     if(open){dont.forEach(j=>H.appendChild(makeCard(j)));t.textContent=`▾ Hide ${dont.length} filtered-out roles`;}
     else{H.innerHTML="";t.textContent=`▸ Show ${dont.length} filtered-out roles (DON'T APPLY) — for auditing`;}});
   L.appendChild(t);
 }
}
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
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n) or b"{}"
        if self.path.startswith("/api/undo"):
            try:
                d = json.loads(body)
                removed = feedback.undo(d.get("job_id", ""))
                return self._send(200, json.dumps({"ok": True, "removed": removed}))
            except Exception as e:
                return self._send(400, json.dumps({"ok": False, "error": str(e)}))
        if not self.path.startswith("/api/feedback"):
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            d = json.loads(body)
            entry = feedback.record(d.get("job_id", ""), d.get("company", ""),
                                    d.get("title", ""), d.get("url", ""),
                                    d.get("action", ""), d.get("note", ""))
            self._send(200, json.dumps({"ok": True, "entry": entry}))
        except Exception as e:
            self._send(400, json.dumps({"ok": False, "error": str(e)}))


def serve(port: int = 8755, open_browser: bool = True) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Job Finder India dashboard → {url}  (local only; Ctrl-C to stop)")
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
