"""Local results dashboard — the deterministic, model-independent review surface.

The agent-driven feedback review can be skipped by weak models; this replaces it.
Runs a tiny localhost HTTP server (Python stdlib, no extra dependency, bound to
127.0.0.1 — data never leaves your machine). It renders the run the same honest way
top.md does — ✅ APPLY/STRETCH first, then ⚠️ Couldn't-verify (with reason), then
Prescreen-filtered (rank + deterministic reason) — with a funnel + wall-clock +
free-tier quota strip on top. Each job's Applied / Interested / Not-suitable(+reason)
buttons write through the EXISTING feedback.record() store (the one preferences.yml
derives from and prescreen replays next run) — no new store, no duplicate logic.

    python -m jobfinder dashboard           # opens http://127.0.0.1:8755, Ctrl-C to stop
"""

from __future__ import annotations

import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import feedback
from .schema import normalize_record

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "data", "results")


def _p(name: str) -> str:
    return os.path.join(RESULTS_DIR, name)


def _read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def _fit(j: dict) -> float:
    try:
        return float(j.get("fit_score", 0))
    except (TypeError, ValueError):
        return 0.0


def _run_cfg() -> dict:
    try:
        import yaml
        return yaml.safe_load(open(os.path.join(ROOT, "config", "run.yml"), encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001 — dashboard is read-only; a missing/broken run.yml just means no quota line
        return {}


def _quota() -> dict:
    """Per-channel free-tier remaining this month (live, from the persisted counter)."""
    try:
        from .discovery import quota
    except Exception:  # noqa: BLE001
        return {}
    disc = (_run_cfg().get("discovery") or {})
    out = {}
    for ch, default_cap in (("adzuna", 250), ("jsearch", 200)):
        cap = int((disc.get(ch, {}) or {}).get("monthly_cap", default_cap))
        used = quota.used_this_month(ch)
        out[ch] = {"used": used, "remaining": max(0, cap - used), "cap": cap}
    return out


def _elapsed_secs() -> int | None:
    """Run wall-clock ≈ scored.jsonl mtime − run start (deterministic, no new store)."""
    try:
        from datetime import datetime, timezone
        from . import state
        started = state.read("run_timing").get("started_at")
        sp = _p("scored.jsonl")
        if not started or not os.path.exists(sp):
            return None
        end = datetime.fromtimestamp(os.path.getmtime(sp), tz=timezone.utc)
        return max(0, int((end - datetime.fromisoformat(started)).total_seconds()))
    except Exception:  # noqa: BLE001
        return None


def _scoring(done_ids: set) -> dict:
    """How many of the persisted score_these target already have a record — so a
    partial run (agent stopped early) never looks complete in the browser."""
    sp = _p("score_these.json")
    if not os.path.exists(sp):
        return {"target": 0, "scored": 0, "remaining": 0, "complete": True}
    try:
        d = json.load(open(sp, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"target": 0, "scored": 0, "remaining": 0, "complete": True}
    ids = list(d.get("ids", []))
    target = int(d.get("target", len(ids)))
    rem = [i for i in ids if i not in done_ids]
    return {"target": target, "scored": target - len(rem), "remaining": len(rem),
            "complete": bool(target) and not rem}


def _load_run() -> dict:
    """Assemble the whole run for the page, mirroring top.md's honest sections.
    Records are normalized with the SAME gate as the tracker, so a schema-off verdict
    (lowercase, string score, missing headline) is canonicalized or surfaced as
    malformed — never silently mis-bucketed as 'nothing worth applying'."""
    rows = [normalize_record(r) for r in _read_jsonl(_p("scored.jsonl"))]
    verdicts = sorted((r for r in rows if not r.get("unverifiable")), key=_fit, reverse=True)
    malformed = [r for r in rows if r.get("malformed")]
    couldnt = [r for r in rows if r.get("unverifiable") and not r.get("malformed")]
    scored_ids = {r.get("job_id") for r in rows}                     # verdicts + unverifiable both count
    fs_n = int((_run_cfg().get("scoring") or {}).get("full_score_top_n", 15))

    prescreen_filtered = []
    for rank, j in enumerate(_read_jsonl(_p("prescreened.jsonl")), 1):
        if (j.get("id") or j.get("job_id")) in scored_ids:
            continue
        prescreen_filtered.append({
            "rank": rank, "title": j.get("title"), "company": j.get("company"),
            "location": j.get("location"), "url": j.get("url"),
            "link_verified": j.get("link_verified"), "link_source": j.get("link_source"),
            "reason": f"passed prescreen; rank #{rank} > top-{fs_n} cutoff — not scored",
        })

    rep = {}
    if os.path.exists(_p("prescreen_report.json")):
        try:
            rep = json.load(open(_p("prescreen_report.json"), encoding="utf-8"))
        except Exception:  # noqa: BLE001
            rep = {}
    funnel = {"candidates": rep.get("input"), "prescreened": rep.get("kept"),
              "scored": len(verdicts), "truncated_from": rep.get("truncated_from")}

    return {"jobs": verdicts, "couldnt_verify": couldnt, "malformed": malformed,
            "prescreen_filtered": prescreen_filtered, "funnel": funnel, "quota": _quota(),
            "elapsed_secs": _elapsed_secs(), "scoring": _scoring(scored_ids),
            "stats": feedback.stats()}


PAGE = r"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Job Finder India — honest shortlist</title>
<style>
 :root{--bg:#0e1014;--card:#161a21;--card2:#1b212a;--line:#252b35;--fg:#e8ebf1;
   --mut:#9099ab;--met:#4ade80;--part:#fbbf24;--miss:#f87171;--blue:#7aa2ff}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);
   font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
 header{padding:22px 28px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;
   background:rgba(14,16,20,.92);backdrop-filter:blur(6px);z-index:5}
 h1{margin:0;font-size:18px;font-weight:600;letter-spacing:.2px}
 .sub{color:var(--mut);font-size:12.5px;margin-top:6px;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
 .funnel{color:var(--mut);font-size:12px;margin-top:8px;display:flex;gap:16px;flex-wrap:wrap}
 .funnel b{color:var(--fg)}
 .pill{padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600}
 .p-apply{background:#11331f;color:var(--met)} .p-stretch{background:#33290d;color:var(--part)}
 .p-dont{background:#331515;color:var(--miss)} .p-cv{background:#332a0d;color:var(--part)}
 .p-malf{background:#3a1520;color:var(--miss)} .p-inc{background:#3a1520;color:var(--miss)}
 .incbanner{background:#3a1520;border:1px solid #6a2436;color:#ffb4be;border-radius:12px;
   padding:12px 16px;margin:16px 0 4px;font-size:13.5px;font-weight:600;line-height:1.5}
 .wrap{max-width:860px;margin:0 auto;padding:20px 24px 70px}
 h2.sec{font-size:14px;font-weight:600;margin:28px 0 2px} h2.sec.malf{color:var(--miss)}
 .job{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:14px 0}
 .job.cv{border-color:#3a3416} .job.malf{border-color:#4a1e28}
 .malfnote{color:var(--miss);font-size:12.5px;margin:2px 0 8px}
 .malfmeta{color:var(--mut);font-size:11.5px;margin-top:4px}
 .row1{display:flex;gap:14px;align-items:center}
 .score{font-size:26px;font-weight:700;min-width:50px;text-align:center;line-height:1}
 .score small{display:block;font-size:10px;color:var(--mut);font-weight:500;margin-top:3px}
 .s-apply{color:var(--met)} .s-stretch{color:var(--part)} .s-dont{color:var(--miss)} .s-cv{color:var(--part);font-size:20px}
 .ttl{font-size:15px;font-weight:600} .meta{color:var(--mut);font-size:12.5px;margin-top:3px}
 .cvreason{color:var(--part);font-size:12.5px;margin-top:5px}
 .capnote{color:var(--part);font-size:12px;font-weight:600;margin:9px 0 2px;border:1px solid #4a3a16;
   background:#2a2410;border-radius:6px;padding:4px 9px;display:inline-block}
 .vsrc{border:1px solid var(--line);border-radius:6px;padding:0 6px;margin-left:4px;font-size:11px;color:var(--mut)}
 ul.why{margin:12px 0 4px;padding-left:18px} ul.why li{margin:3px 0;color:#cfd5e0}
 .quals{margin:12px 0 4px;background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:11px 13px}
 .qsum{font-size:12.5px;color:var(--mut);cursor:pointer;list-style:none;outline:none}
 .qsum::-webkit-details-marker{display:none}
 .qsum::before{content:"\25b8 ";color:var(--mut)} details[open] .qsum::before{content:"\25be "}
 details[open] .qsum{margin-bottom:8px} .hint{color:var(--mut);font-size:11px}
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
 table.pf{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:10px}
 table.pf th{text-align:left;color:var(--mut);font-weight:500;border-bottom:1px solid var(--line);padding:5px 8px}
 table.pf td{border-bottom:1px solid var(--line);padding:5px 8px;color:#cfd5e0}
 .empty{color:var(--mut);padding:50px;text-align:center}
</style></head><body>
<header><h1>Job Finder India <span style="color:var(--mut);font-weight:400">— honest shortlist</span></h1>
<div class=sub id=sub>loading…</div><div class=funnel id=funnel></div></header>
<div class=wrap><div id=list></div><div id=hidden></div></div>
<script>
const REASONS=[["wrong_level","Too senior"],["wrong_function","Wrong function"],
 ["wrong_location","Location"],["wrong_comp","Comp too low"],
 ["wrong_company","Company"],["wouldnt_apply","Other"]];
const esc=s=>(s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const vkey=v=>(v||"").startsWith("DON")?"dont":v==="APPLY"?"apply":"stretch";
const vlabel=v=>(v||"").startsWith("DON")?"DON'T APPLY":v;

function whyBullets(h){
 if(!h) return "";
 let t=h.replace(/^⚖️ Cap enforced: [\d.]+ → [\d.]+(?: \([^)]*\))?\.\s*/,"")  // shown separately as a badge
        .replace(/^\s*(APPLY|STRETCH|DON'?T APPLY)\s*[—\-]\s*/i,"");
 const parts=t.split(/;\s+|\s—\s/).map(x=>x.trim()).filter(Boolean);
 return "<ul class=why>"+parts.map(p=>`<li>${esc(p)}</li>`).join("")+"</ul>";
}
function qualsBlock(j){
 if(!j.qualifications||!j.qualifications.length) return "";
 const g={met:[],partial:[],missing:[]};
 j.qualifications.forEach(q=>(g[q.status]||g.missing).push(q));
 const s=j.qualifications_summary||{met:g.met.length,partial:g.partial.length,missing:g.missing.length};
 const sec=(k,label,cls)=>g[k].length?`<div class=qgrp><div class="qh ${cls}">${label} (${g[k].length})</div><ul>`+
   g[k].map(q=>`<li>${esc(q.requirement)}${(q.evidence&&k!=='met')?` <span class=ev>— ${esc(q.evidence)}</span>`:''}</li>`).join("")+`</ul></div>`:"";
 return `<details class=quals><summary class=qsum>Qualifications match — `+
   `<b class=cmet>${s.met} met</b> · <b class=cpart>${s.partial} partial</b> · <b class=cmiss>${s.missing} missing</b>`+
   `<span class=hint> · click to expand</span></summary>`+
   sec("met","✓ Met","cmet")+sec("partial","~ Partial","cpart")+sec("missing","✗ Missing","cmiss")+`</details>`;
}
function skillsLine(j){
 const s=j.skills_check; if(!s) return "";
 const seg=(arr,cls,ic)=>(arr&&arr.length)?`<span class=${cls}>${ic} ${esc(arr.join(", "))}</span>`:"";
 const segs=[seg(s.met,"cmet","✓"),seg(s.partial,"cpart","~"),seg(s.missing,"cmiss","✗")].filter(Boolean);
 return segs.length?`<div class=skills><span class=lbl>Skills (auto-checked):</span> ${segs.join(" &nbsp; ")}</div>`:"";
}
function updateHead(d){
 const fbn=Object.values(d.stats||{}).reduce((a,b)=>a+b,0);
 const n=v=>d.jobs.filter(j=>vkey(j.verdict)===v).length;
 document.getElementById("sub").innerHTML=
   `<span class="pill p-apply">${n("apply")} APPLY</span>`+
   `<span class="pill p-stretch">${n("stretch")} STRETCH</span>`+
   `<span class="pill p-dont">${d.jobs.filter(j=>vkey(j.verdict)==="dont").length} filtered out</span>`+
   (d.couldnt_verify.length?`<span class="pill p-cv">${d.couldnt_verify.length} couldn't verify</span>`:"")+
   ((d.malformed&&d.malformed.length)?`<span class="pill p-malf">${d.malformed.length} malformed</span>`:"")+
   ((d.scoring&&d.scoring.target&&!d.scoring.complete)?`<span class="pill p-inc">⚠ ${d.scoring.scored}/${d.scoring.target} scored</span>`:"")+
   `<span>${fbn} call${fbn==1?"":"s"} saved</span>`;
 const f=d.funnel||{}, q=d.quota||{}, parts=[];
 if(f.candidates!=null) parts.push(`<span>Funnel: <b>${f.candidates}</b> candidates → <b>${f.prescreened}</b> prescreened → <b>${f.scored}</b> scored</span>`);
 if(d.elapsed_secs!=null){const m=Math.round(d.elapsed_secs/60);parts.push(`<span>Run took ~<b>${m<1?"<1":m}m</b></span>`);}
 const qseg=Object.entries(q).map(([k,v])=>`${k} <b>${v.remaining}</b>/${v.cap}`).join(" · ");
 if(qseg) parts.push(`<span>Free-tier left: ${qseg}</span>`);
 document.getElementById("funnel").innerHTML=parts.join("");
}
async function post(url,j){return (await fetch(url,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(j)})).json();}

function mkbtn(cls,txt,fn){const b=document.createElement("button");b.className=cls;b.textContent=txt;b.addEventListener("click",fn);return b;}
function mountActions(card,j){
 const host=card.querySelector(".actionhost"); host.innerHTML="";
 const acts=document.createElement("div"); acts.className="acts";
 acts.innerHTML=`<span class=lbl>Your call:</span>`;
 const applied=mkbtn("act good","✓ Applied",()=>save(card,j,"applied"));
 const interested=mkbtn("act good","☆ Interested",()=>save(card,j,"interested"));
 const notsuit=mkbtn("act bad","✗ Not suitable",()=>{
   if(host.querySelector(".reasons")) return;
   const r=document.createElement("div"); r.className="reasons"; r.innerHTML=`<span class=lbl>Reason:</span>`;
   REASONS.forEach(([a,label])=>r.append(mkbtn("chip",label,()=>save(card,j,a))));
   host.append(r);
 });
 acts.append(applied,interested,notsuit); host.append(acts);
}
async function save(card,j,action){
 await post("/api/feedback",{job_id:j.job_id,company:j.company,title:j.title,url:j.url,action});
 const host=card.querySelector(".actionhost");
 const positive=action==="applied"||action==="interested";
 const txt=action==="applied"?"tracked as applied — won't be re-recommended"
   :action==="interested"?"marked interested — stays visible, tilts future scoring"
   :action==="wouldnt_apply"?"passed — won't be re-recommended"
   :`not suitable (${action.replace("wrong_","wrong ")}) — will retune scoring`;
 host.innerHTML=`<div class="saved ${positive?'':'neg'}">✓ ${txt}<span class=change>change</span></div>`;
 host.querySelector(".change").addEventListener("click",async()=>{await post("/api/undo",{job_id:j.job_id});mountActions(card,j);refreshHead();});
 refreshHead();
}
async function refreshHead(){updateHead(await (await fetch("/api/data")).json());}

function makeCard(j){
 const vk=vkey(j.verdict);
 const el=document.createElement("div"); el.className="job";
 const vsrc=j.link_verified?`<span class=vsrc>✓ ${esc(j.link_source||"verified")}</span>`:"";
 const cap=j.cap_enforced?`<div class=capnote>⚖️ cap enforced: ${(+j.cap_enforced.from).toFixed(1)} → ${(+j.cap_enforced.to).toFixed(1)}${j.cap_enforced.by?` — ${esc(j.cap_enforced.by)}`:""}</div>`:"";
 el.innerHTML=
   `<div class=row1>
      <div class="score s-${vk}">${Number.isFinite(+j.fit_score)?(+j.fit_score).toFixed(1):"?"}<small>${esc((j.score_range&&j.score_range[0]!=j.score_range[1])?j.score_range.join("–"):"")}</small></div>
      <div style="flex:1">
        <span class="pill p-${vk}">${vlabel(j.verdict)}</span>
        <span class=ttl> ${esc(j.title)}</span>
        <div class=meta>${esc(j.company)} · ${esc(j.location||"")} ${vsrc}</div>
      </div>
    </div>
    ${cap}${whyBullets(j.headline)}${qualsBlock(j)}${skillsLine(j)}
    ${j.url?`<a class=link href="${esc(j.url)}" target=_blank rel=noopener>open verified JD ↗</a>`:""}
    <div class=actionhost></div>`;
 mountActions(el,j);
 return el;
}
function makeCVCard(j){
 const el=document.createElement("div"); el.className="job cv";
 el.innerHTML=
   `<div class=row1>
      <div class="score s-cv">⚠<small>no JD</small></div>
      <div style="flex:1">
        <span class="pill p-cv">COULDN'T VERIFY</span>
        <span class=ttl> ${esc(j.title)}</span>
        <div class=meta>${esc(j.company)} · ${esc(j.location||"")}</div>
        <div class=cvreason>${esc(j.reason||"the tool couldn't read a real JD at this link")}</div>
      </div>
    </div>
    ${j.url?`<a class=link href="${esc(j.url)}" target=_blank rel=noopener>open link ↗</a>`:""}
    <div class=actionhost></div>`;
 mountActions(el,j);
 return el;
}
function makeMalfCard(j){
 const el=document.createElement("div"); el.className="job malf";
 const wv=(j.withheld_verdict!=null&&j.withheld_verdict!=="")?`raw verdict: ${esc(String(j.withheld_verdict))}`:"";
 const ws=(j.withheld_fit_score!=null&&j.withheld_fit_score!=="")?`raw score: ${esc(String(j.withheld_fit_score))}`:"";
 el.innerHTML=
   `<div class=row1>
      <div class="score" style="color:var(--miss);font-size:20px">⚠<small>malformed</small></div>
      <div style="flex:1">
        <span class="pill p-malf">MALFORMED</span>
        <span class=ttl> ${esc(j.title||"(no title)")}</span>
        <div class=meta>${esc(j.company||"")} · ${esc(j.location||"")}</div>
        <div class=malfnote>${esc(j.reason||"the model's verdict didn't match the schema")}</div>
        <div class=malfmeta>${[wv,ws].filter(Boolean).join(" · ")}</div>
      </div>
    </div>
    ${j.url?`<a class=link href="${esc(j.url)}" target=_blank rel=noopener>open link ↗</a>`:""}`;
 return el;
}
function pfTable(rows){
 return `<table class=pf><thead><tr><th>#</th><th>Title</th><th>Company</th><th>Location</th><th></th></tr></thead><tbody>`+
   rows.map(j=>`<tr><td>${j.rank}</td><td>${esc(j.title)}</td><td>${esc(j.company)}</td><td>${esc(j.location||"—")}</td>`+
     `<td>${j.url?`<a class=link href="${esc(j.url)}" target=_blank rel=noopener>open ↗</a>`:""}</td></tr>`).join("")+
   `</tbody></table><div class=hint style="margin-top:6px">Passed the deterministic prescreen `+
   `(title-family · seniority · function · location) but ranked below the full-score cutoff — not individually scored.</div>`;
}
async function load(){
 const d=await (await fetch("/api/data")).json(); updateHead(d);
 const L=document.getElementById("list"), H=document.getElementById("hidden");
 L.innerHTML=""; H.innerHTML="";
 const nMalf=(d.malformed&&d.malformed.length)||0;
 const incomplete=!!(d.scoring&&d.scoring.target&&!d.scoring.complete);
 if(!d.jobs.length && !d.couldnt_verify.length && !d.prescreen_filtered.length && !nMalf && !incomplete){
   L.innerHTML="<div class=empty>No scored results yet. Say <b>find me jobs</b> in your CLI to run discovery + scoring, then refresh.</div>";return;}
 if(incomplete){   // FIRST + LOUD — a partial run must never look complete in the browser
   const b=document.createElement("div"); b.className="incbanner";
   b.textContent=`⚠️ Scored ${d.scoring.scored} of ${d.scoring.target} — this run is incomplete (a smaller/limited model may have stopped early). Re-run to score the remaining ${d.scoring.remaining}.`;
   L.appendChild(b);
 }
 if(nMalf){   // LOUD, first — never let a schema-off run look like "nothing worth applying"
   const h=document.createElement("h2"); h.className="sec malf";
   h.textContent=`⚠️ ${nMalf} verdict${nMalf>1?"s were":" was"} malformed (model output didn't match the schema — likely a too-small model). Not scored.`;
   L.appendChild(h); d.malformed.forEach(j=>L.appendChild(makeMalfCard(j)));
 }
 const show=d.jobs.filter(j=>vkey(j.verdict)!=="dont");
 const dont=d.jobs.filter(j=>vkey(j.verdict)==="dont");
 if(show.length){const sh=document.createElement("h2");sh.className="sec";sh.textContent="✅ Worth applying — APPLY / STRETCH";L.appendChild(sh);show.forEach(j=>L.appendChild(makeCard(j)));}
 else if(d.jobs.length){const e=document.createElement("div");e.className="empty";e.textContent="No APPLY/STRETCH roles in this run — reveal the filtered-out roles below, or widen discovery.";L.appendChild(e);}
 if(d.couldnt_verify.length){
   const h=document.createElement("h2"); h.className="sec"; h.textContent=`⚠️ Couldn't verify — check manually (${d.couldnt_verify.length})`;
   L.appendChild(h); d.couldnt_verify.forEach(j=>L.appendChild(makeCVCard(j)));
 }
 if(dont.length){
   const t=document.createElement("button"); t.className="toggle";
   const lab=`▸ Show ${dont.length} filtered-out roles (DON'T APPLY) — for auditing`;
   t.textContent=lab; let open=false;
   t.addEventListener("click",()=>{open=!open;
     if(open){dont.forEach(j=>H.appendChild(makeCard(j)));t.textContent=`▾ Hide ${dont.length} filtered-out roles`;}
     else{H.innerHTML="";t.textContent=lab;}});
   L.appendChild(t);
 }
 if(d.prescreen_filtered.length){
   const box=document.createElement("div");
   const t=document.createElement("button"); t.className="toggle";
   const lab=`▸ Show ${d.prescreen_filtered.length} prescreen-filtered (passed the gate, ranked below the scoring cutoff)`;
   t.textContent=lab; let open=false;
   t.addEventListener("click",()=>{open=!open;
     if(open){box.innerHTML=pfTable(d.prescreen_filtered);t.textContent=`▾ Hide prescreen-filtered`;}
     else{box.innerHTML="";t.textContent=lab;}});
   L.appendChild(t); L.appendChild(box);
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
            self._send(200, json.dumps(_load_run()))
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
            except Exception as e:  # noqa: BLE001
                return self._send(400, json.dumps({"ok": False, "error": str(e)}))
        if not self.path.startswith("/api/feedback"):
            return self._send(404, json.dumps({"error": "not found"}))
        try:
            d = json.loads(body)
            entry = feedback.record(d.get("job_id", ""), d.get("company", ""),
                                    d.get("title", ""), d.get("url", ""),
                                    d.get("action", ""), d.get("note", ""))
            self._send(200, json.dumps({"ok": True, "entry": entry}))
        except Exception as e:  # noqa: BLE001
            self._send(400, json.dumps({"ok": False, "error": str(e)}))


def serve(port: int = 8755, open_browser: bool = True) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Job Finder India dashboard → {url}  (local only; Ctrl-C to stop)")
    if not os.path.exists(_p("scored.jsonl")):
        print("  note: no scored results yet — say 'find me jobs' in your CLI to run discovery + scoring.")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        srv.server_close()
    return 0
