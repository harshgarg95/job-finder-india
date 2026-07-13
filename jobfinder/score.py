"""Scoring orchestration — build the prompt, drive the user's AI CLI, rank.

This is the product path: it concatenates the rubric + the candidate's resume and
profile + one job, hands it to whichever AI CLI the user has (headless, via
cli_adapter), parses the JSON verdict, and ranks. No scoring key lives here.

Volume safety: this function scores ONLY the already-bounded set it is handed
(run.py runs prescreen_set first, capped at run.yml's `max_llm_jobs`). It does
NOT re-discover or re-expand — so the number of LLM calls is bounded by
construction (jobs × scoring.samples).

Honesty plumbing: per-job failures are recorded and the run continues, but if
*every* job fails to score, that is reported as a breakage — never silently
turned into an empty/garbage ranking.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import yaml

from . import cli_adapter
from .discovery import job_fetcher
from .resume import load_resume
from .schema import JobPosting

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(ROOT, "prompts")
DATA = os.path.join(ROOT, "data")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(resume_text: str, profile: dict, job: JobPosting, lessons: str = "",
                 candidate_skills: list[str] | None = None) -> str:
    """Assemble the full scoring prompt for one job. `lessons` is the feedback
    digest (prior user corrections); `candidate_skills` is the normalized skill
    list extracted from the resume (our 'structured profile')."""
    rubric = _read(os.path.join(PROMPTS, "_rubric.md"))
    procedure = _read(os.path.join(PROMPTS, "score-job.md"))
    prof_yaml = yaml.safe_dump({k: v for k, v in profile.items() if not k.startswith("_")},
                               sort_keys=False, allow_unicode=True)
    lessons_block = f"\n---\n{lessons}\n" if lessons else ""
    skills_block = ""
    if candidate_skills:
        skills_block = ("\n---\n## CANDIDATE SKILLS (normalized from the resume)\n"
                        "Use this canonical list to match the JD's required skills consistently "
                        "(a sibling skill = partial, not missing):\n" + ", ".join(candidate_skills) + "\n")
    return f"""{rubric}

---
{procedure}

---
## CANDIDATE RESUME
{resume_text}

---
## CANDIDATE PROFILE (config/profile.yml)
```yaml
{prof_yaml}
```
{skills_block}{lessons_block}
---
## JOB TO SCORE
{job.scoring_view()}

---
Now emit exactly one JSON object scoring THIS job per the schema. Output only the
JSON object.
"""


def _fit_of(v: dict) -> float:
    try:
        return float(v.get("fit_score", 0))
    except (TypeError, ValueError):
        return 0.0


def score_and_rank(resume_path: str, jobs: list[JobPosting], profile: dict, out_dir: str,
                   cli: str | None = None, run_cfg: dict | None = None,
                   funnel: dict | None = None) -> int:
    from . import feedback
    from . import skills as skills_mod
    from . import verify
    from . import location

    run_cfg = run_cfg or {}
    scoring_cfg = run_cfg.get("scoring", {}) or {}
    top_n = int(scoring_cfg.get("top_n", 10))
    samples = int(scoring_cfg.get("samples", 3))
    timeout = int(scoring_cfg.get("timeout_seconds", 300))
    full_score_top_n = int(scoring_cfg.get("full_score_top_n", 15))   # FIX B — cap full-scored jobs

    resume_text = load_resume(resume_path)
    candidate_skills = skills_mod.extract(resume_text)   # normalized once (structured profile)
    if candidate_skills:
        print(f"  normalized {len(candidate_skills)} resume skills: {', '.join(candidate_skills[:12])}"
              + (" …" if len(candidate_skills) > 12 else ""))
    os.makedirs(out_dir, exist_ok=True)
    failures = []
    total_cost = 0.0

    # Crash-safe checkpoint + resume: scored.jsonl is written per-job and re-read
    # on a re-run, so a long scoring pass interrupted by a timeout / rate limit /
    # Ctrl-C RESUMES instead of starting over. Only entries for jobs in the
    # CURRENT set are kept (stale results from an older set are dropped).
    scored_path = os.path.join(out_dir, "scored.jsonl")
    current_ids = {j.id for j in jobs}
    done: dict[str, dict] = {}
    if os.path.exists(scored_path):
        for ln in open(scored_path, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                e = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if e.get("job_id") in current_ids and (isinstance(e.get("fit_score"), (int, float))
                                                    or e.get("unverifiable")):
                done[e["job_id"]] = e
    with open(scored_path, "w", encoding="utf-8") as f:   # rewrite clean (drop stale)
        for e in done.values():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if done:
        print(f"  resume: {len(done)} job(s) in this set already scored — skipping them")
    ckpt = open(scored_path, "a", encoding="utf-8")

    # Feedback loop: drop jobs the user already rejected, and replay corrections.
    fb = feedback.load()
    suppress = feedback.suppressed_ids(fb)
    lessons = feedback.lessons_digest(fb)
    if suppress:
        before = len(jobs)
        jobs = [j for j in jobs if j.id not in suppress]
        print(f"  feedback: suppressed {before - len(jobs)} job(s) you previously rejected")
    if lessons:
        print(f"  feedback: replaying {len(fb)} prior correction(s) into scoring")

    # FIX B — full-score only the strongest by prescreen rank (jobs is already ranked).
    # The rest are reported as "prescreen-filtered (not individually scored)".
    prescreened_all = [j.to_dict() for j in jobs]
    score_set = jobs[:full_score_top_n] if full_score_top_n else list(jobs)

    print(f"\n── Full-scoring the top {len(score_set)} of {len(jobs)} prescreened jobs via your AI CLI "
          f"({cli or os.environ.get('JOBFINDER_CLI') or 'auto-detect'}), {samples} sample(s) each ──")
    enriched = 0
    for i, job in enumerate(score_set, 1):
        if job.id in done:                 # resume: already scored, skip (and skip enrich)
            continue
        # Deep-fetch the full JD if we only have a thin snippet (so the scorer
        # sees buried gating requirements, not a summary). Bounded set → bounded fetches.
        if job_fetcher.enrich(job):
            enriched += 1
        # FIX A — verifiability gate: never score a job we couldn't actually read
        # (empty/too-thin JD, or a non-job link). Route it to "Couldn't verify".
        vstatus, vreason = verify.classify(job.url, job.description)
        if vstatus != "ok":
            rec = {"job_id": job.id, "title": job.title, "company": job.company,
                   "url": job.url, "location": job.location, "source": job.source,
                   "link_source": job.link_source, "unverifiable": True,
                   "verify_status": vstatus, "reason": vreason}
            done[job.id] = rec
            ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ckpt.flush()
            continue
        # CHANGE 1 — location re-gate: for a coarse channel location, derive the city
        # from the JD and re-run the onsite gate; gate out an onsite-elsewhere role (or
        # an onsite role whose city can't be verified) instead of scoring it as "India".
        lstatus, lreason, lcity = location.regate(job, profile)
        if lstatus != "ok":
            rec = {"job_id": job.id, "title": job.title, "company": job.company,
                   "url": job.url, "location": job.location, "source": job.source,
                   "link_source": job.link_source, "unverifiable": True,
                   "verify_status": lstatus, "reason": lreason, "derived_city": lcity}
            done[job.id] = rec
            ckpt.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ckpt.flush()
            continue
        prompt = build_prompt(resume_text, profile, job, lessons, candidate_skills)
        # Self-consistency: score N times, keep the MOST CONSERVATIVE (lowest)
        # result. Single-pass LLM scores vary; honest scoring errs low.
        outs, last_err = [], None

        def _note_failover(frm, to, why, _seen=set()):
            if (frm, to) not in _seen:
                _seen.add((frm, to))
                print(f"   ⚠ CLI '{frm}' unavailable ({why[:60]}) → failing over to '{to}'")

        for _ in range(max(1, samples)):
            try:
                v = cli_adapter.score(prompt, cli=cli, timeout=timeout, on_failover=_note_failover)
                outs.append(v)
            except Exception as e:
                last_err = e
        for v in outs:
            c = v.get("_cost_usd")
            if isinstance(c, (int, float)):
                total_cost += c

        valid = [v for v in outs if isinstance(v.get("fit_score"), (int, float))]
        if not valid:
            failures.append({"title": job.title, "company": job.company,
                             "error": str(last_err) if last_err else "no numeric fit_score returned"})
        else:
            verdict = min(valid, key=_fit_of)           # conservative pick (valid samples only)
            fits = [_fit_of(v) for v in valid]
            verdict["score_samples"] = len(outs)
            verdict["score_range"] = [min(fits), max(fits)]
            verdict["job_cost_usd"] = round(sum((v.get("_cost_usd") or 0) for v in outs), 4)
            verdict.setdefault("company", job.company)
            verdict.setdefault("title", job.title)
            verdict["url"] = job.url
            verdict["job_id"] = job.id
            verdict["location"] = job.location
            verdict["link_source"] = job.link_source
            verdict["link_verified"] = job.link_verified
            verdict["source"] = job.source
            # Deterministic skills cross-check (our taxonomy, no LLM): a second,
            # consistent opinion on which JD skills the resume met/partial/missing.
            chk = {"met": [], "partial": [], "missing": []}
            for s in skills_mod.extract(job.description):
                st = skills_mod.match(s, candidate_skills)
                if st in chk:
                    chk[st].append(s)
            verdict["skills_check"] = chk
            done[job.id] = verdict
            ckpt.write(json.dumps(verdict, ensure_ascii=False) + "\n")
            ckpt.flush()                   # crash-safe: each job persisted immediately
        if i % 10 == 0:
            print(f"   scored {len(done)}/{len(score_set)} (failures: {len(failures)}, cost so far: ${total_cost:.2f})")

    ckpt.close()
    scored = list(done.values())
    if enriched:
        print(f"   (deep-fetched the full JD for {enriched} thin-snippet listings)")
    if not scored:
        print(f"\n✗ Scoring produced 0 results from {len(jobs)} jobs — BREAKAGE, not an honest empty.")
        for f in failures[:3]:
            print(f"   ⚠ {f['title']}: {f['error']}")
        return 2

    scored.sort(key=lambda v: (-float(v.get("fit_score", 0)), len(v.get("caps_applied") or [])))
    _update_tracker(scored)
    from . import state as _state
    started_at = _state.read("run_timing").get("started_at")
    _write_outputs(scored, failures, out_dir, top_n, total_cost=total_cost, funnel=funnel,
                   prescreened=prescreened_all, full_score_top_n=full_score_top_n,
                   started_at=started_at)
    return 0


def _update_tracker(scored: list[dict]) -> None:
    """Register EVERY scored job in the markdown tracker — the single source of
    truth. Merges across runs by job_id (latest score wins) via a jsonl store,
    then renders data/tracker.md. User Layer (never leaves the machine)."""
    scored = [v for v in scored if not v.get("unverifiable")]   # tracker = scored jobs only
    os.makedirs(DATA, exist_ok=True)
    store = os.path.join(DATA, "tracker.jsonl")
    md = os.path.join(DATA, "tracker.md")

    by_id: dict[str, dict] = {}
    if os.path.exists(store):
        for ln in open(store, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    e = json.loads(ln)
                    by_id[e.get("job_id")] = e
                except json.JSONDecodeError:
                    continue

    today = datetime.now(timezone.utc).date().isoformat()
    for v in scored:
        jid = v.get("job_id")
        qs = v.get("qualifications_summary") or {}
        prev = by_id.get(jid) or {}
        by_id[jid] = {
            "job_id": jid,
            "first_seen": prev.get("first_seen", today),
            "last_scored": today,
            "company": v.get("company", ""), "title": v.get("title", ""),
            "location": v.get("location", ""), "url": v.get("url", ""),
            "source": v.get("source", ""),
            "fit_score": v.get("fit_score"), "verdict": v.get("verdict", ""),
            "headline": v.get("headline", ""),
            "met": qs.get("met"), "partial": qs.get("partial"), "missing": qs.get("missing"),
            "scored_by": v.get("_scored_by", ""),
        }

    with open(store, "w", encoding="utf-8") as f:
        for e in by_id.values():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    rows = sorted(by_id.values(),
                  key=lambda e: (-(e.get("fit_score") or 0), e.get("company", "")))
    lines = [
        "# Job tracker — every scored job (single source of truth)", "",
        f"_{len(rows)} jobs tracked · updated {today} · User Layer — never leaves your machine._", "",
        "| Score | Verdict | Title | Company | Location | Quals m/p/x | Last scored | Link |",
        "|------:|---------|-------|---------|----------|:-----------:|-------------|------|",
    ]
    for e in rows:
        sc = e.get("fit_score")
        sc = f"{float(sc):.1f}" if isinstance(sc, (int, float)) else "—"
        q = f"{e.get('met','-')}/{e.get('partial','-')}/{e.get('missing','-')}"
        title = (e.get("title", "") or "")[:46].replace("|", "/")
        comp = (e.get("company", "") or "")[:18].replace("|", "/")
        loc = (e.get("location", "") or "")[:18].replace("|", "/")
        url = e.get("url", "") or ""
        link = f"[link]({url})" if url else ""
        lines.append(f"| {sc} | {e.get('verdict','')} | {title} | {comp} | {loc} | {q} | "
                     f"{e.get('last_scored','')} | {link} |")
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  tracker: {len(rows)} job(s) registered in data/tracker.md (single source of truth)")


def _write_outputs(scored: list[dict], failures: list[dict], out_dir: str, top_n: int,
                   total_cost: float = 0.0, funnel: dict | None = None,
                   prescreened: list[dict] | None = None,
                   full_score_top_n: int | None = None,
                   started_at: str | None = None) -> None:
    with open(os.path.join(out_dir, "scored.jsonl"), "w", encoding="utf-8") as f:
        for v in scored:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    # ── Verifiability gate (FIX A): a job the tool couldn't read (empty JD, or a
    #    non-job link) MUST NOT appear as APPLY/STRETCH, whatever its score. Move such
    #    records to the "Couldn't verify" bucket. The mode also avoids scoring them;
    #    this re-enforces the link check at render (belt-and-suspenders). ──
    from . import verify
    couldnt = [v for v in scored if v.get("unverifiable")]
    _kept = []
    for v in (x for x in scored if not x.get("unverifiable")):
        st, reason = verify.classify(v.get("url", ""), None)   # URL-only re-check at render
        if st == "non_job_link":
            couldnt.append({**v, "unverifiable": True, "reason": reason,
                            "withheld_score": v.get("fit_score")})
        else:
            _kept.append(v)

    # Distribution counts only the kept, verified verdicts.
    dist = {"APPLY": 0, "STRETCH": 0, "DON'T APPLY": 0}
    for v in _kept:
        vd = v.get("verdict", "DON'T APPLY")
        dist[vd] = dist.get(vd, 0) + 1
    n_apply, n_stretch, n_no = dist["APPLY"], dist["STRETCH"], dist["DON'T APPLY"]
    n_scored = n_apply + n_stretch + n_no

    def _provider(v: dict) -> str:
        # "employer-ats:greenhouse" / "ats:greenhouse" -> "greenhouse"; "apify:naukri" -> "naukri"
        s = v.get("link_source") or v.get("source") or ""
        return s.split(":")[-1].strip() if s else ""

    def _link(v: dict) -> str:
        url = (v.get("url") or "").strip()
        prov = _provider(v)
        if not url:
            return f"— ({prov})" if prov else "—"
        return f"[open]({url})" + (f" · {prov}" if prov else "")

    def _clean(s) -> str:
        return (str(s or "")).replace("|", "/").replace("\n", " ").strip()

    lines = ["# Honest results — fit first", ""]
    if funnel:
        lines.append(f"**Funnel:** raw {funnel.get('raw','?')} → candidates {funnel.get('candidates','?')} "
                     f"→ prescreened {funnel.get('prescreened','?')} → full-scored {n_scored}")
        if funnel.get("truncated_from"):
            lines.append(f"> Prescreen kept {funnel['truncated_from']} jobs; capped to "
                         f"{funnel.get('prescreened')} (run.yml `max_llm_jobs`) — not silent.")
        lines.append("")
    fail_note = f" · {len(failures)} failed to score" if failures else ""
    cost_note = f" · est. cost ${total_cost:.2f}" if total_cost else " · cost: n/a (local/free CLI)"
    lines.append(f"Full-scored {n_scored} jobs — "
                 f"{n_apply} APPLY · {n_stretch} STRETCH · {n_no} DON'T APPLY{fail_note}{cost_note}")
    lines.append("")

    apply_stretch = [v for v in _kept if v.get("verdict") in ("APPLY", "STRETCH")]
    filtered = [v for v in _kept if v.get("verdict") not in ("APPLY", "STRETCH")]

    def _detail(i, v):
        """Full, UNTRUNCATED reasoning + resume-line ↔ JD-requirement citations."""
        sen, fn = v.get("seniority") or {}, v.get("function") or {}
        dom, comp, leg = v.get("domain") or {}, v.get("comp_logistics") or {}, v.get("legitimacy") or {}
        quals, qsum = v.get("qualifications") or [], v.get("qualifications_summary") or {}
        rng, ns = v.get("score_range"), v.get("score_samples")
        L = ["", f"### {i}. {v.get('title','')} — {v.get('company','')}"]
        meta = f"**{float(v.get('fit_score',0)):.1f} · {v.get('verdict','')}**"
        if isinstance(rng, list) and len(rng) == 2:
            meta += f"  ·  {ns} sample(s), range {rng[0]}–{rng[1]}"
        if v.get("_scored_by"):
            meta += f"  ·  scored by {v.get('_scored_by')}"
        L.append(meta)
        if v.get("location"):
            L.append(f"- **Location:** {v.get('location')}")
        L.append(f"- **Link:** {_link(v)}")
        L.append(f"- **Verdict reason:** {v.get('headline','')}")
        if sen.get("evidence") or sen.get("assessment"):
            L.append(f"- **Seniority** ({sen.get('assessment','?')}): {sen.get('evidence','')}")
        if fn.get("evidence") or fn.get("assessment"):
            L.append(f"- **Function** ({fn.get('assessment','?')}): {fn.get('evidence','')}")
        if quals:
            L.append(f"- **Qualifications** (met {qsum.get('met','?')} / "
                     f"partial {qsum.get('partial','?')} / missing {qsum.get('missing','?')}):")
            for q in quals:
                req = (q.get("requirement", "") or "").strip()
                ev = (q.get("evidence", "") or "").strip()
                L.append(f"    - **[{q.get('status','?')}]** {req}{(' — ' + ev) if ev else ''}")
        if dom.get("assessment"):
            L.append(f"- **Domain** ({dom.get('assessment')}): {dom.get('note','')}")
        if comp.get("assessment"):
            L.append(f"- **Comp & logistics** ({comp.get('assessment')}): {comp.get('note','')}")
        if leg.get("tier"):
            sig = leg.get("signals") or []
            sig = "; ".join(sig) if isinstance(sig, list) else str(sig)
            L.append(f"- **Legitimacy** ({leg.get('tier')} — separate read, does not move the score): {sig}")
        if v.get("caps_applied"):
            L.append(f"- **Caps applied:** {', '.join(v.get('caps_applied'))}")
        return L

    # ── Lead with FIT: APPLY / STRETCH, full detail + citations ──────────────
    lines.append(f"## ✅ Worth applying — APPLY / STRETCH ({len(apply_stretch)})")
    if apply_stretch:
        for i, v in enumerate(apply_stretch[:top_n], 1):
            lines += _detail(i, v)
        if len(apply_stretch) > top_n:
            lines += ["", f"> +{len(apply_stretch) - top_n} more APPLY/STRETCH in data/results/scored.jsonl."]
    else:
        lines += ["", "_Nothing cleared the 4.0 apply bar this run. The closest near-misses are in "
                  "'Filtered out' below — shown honestly, not promoted to fill space._"]

    # ── ⚠️ Couldn't verify — the tool couldn't read a real JD, or the link isn't a
    #    specific posting. NOT recommended, NOT scored (any provisional score withheld). ──
    lines += ["", f"## ⚠️ Couldn't verify — check manually ({len(couldnt)})"]
    if couldnt:
        lines += ["", "_These couldn't be confirmed: an empty/too-thin JD, or a link that's a bare "
                  "domain / careers-list page rather than a specific posting. They are **not** scored and "
                  "**not** recommended — open each and check it yourself._",
                  "", "| Why unverifiable | Title | Company | Link |",
                  "|------------------|-------|---------|------|"]
        for v in couldnt:
            why = _clean(v.get("reason") or "could not verify")[:80]
            if v.get("withheld_score") is not None:
                why += f" · provisional {float(v['withheld_score']):.1f} withheld"
            lines.append(f"| {why} | {_clean(v.get('title'))} | {_clean(v.get('company'))} | {_link(v)} |")

    # ── Secondary: everything filtered out, compact, with the one-line WHY ───
    lines += ["", f"## Filtered out — and why ({len(filtered)} roles, kept for transparency)"]
    if filtered:
        lines += ["", "| Score | Verdict | Title | Company | Why | Link |",
                  "|------:|---------|-------|---------|-----|------|"]
        for v in filtered:
            why = v.get("headline", "") or ""
            for pre in ("DON'T APPLY", "DON’T APPLY", "DONT APPLY"):
                if why.upper().startswith(pre.upper()):
                    why = why[len(pre):].lstrip(" —-:")
                    break
            lines.append(f"| {float(v.get('fit_score',0)):.1f} | {v.get('verdict','')} "
                         f"| {_clean(v.get('title'))} | {_clean(v.get('company'))} "
                         f"| {_clean(why)[:140]} | {_link(v)} |")

    # ── Prescreen-filtered: cleared the deterministic prescreen but ranked below the
    #    full-score cutoff → NOT individually LLM-scored. Shown with rank + reason. ──
    pf = []
    if prescreened is not None:
        scored_ids = {v.get("job_id") for v in scored}
        pf = [(rank, j) for rank, j in enumerate(prescreened, 1)
              if (j.get("id") or j.get("job_id")) not in scored_ids]
        lines += ["", f"## Prescreen-filtered — not individually scored ({len(pf)})"]
        cutoff = (f" Only the top {full_score_top_n} by prescreen rank were full-scored in-session "
                  "(latency)." if full_score_top_n is not None else "")
        lines += ["", f"_These cleared the deterministic prescreen (title-family · seniority · function · "
                  f"location) but ranked below the cutoff.{cutoff} Shown with rank + reason — **not** an LLM "
                  "verdict; they were not individually scored._"]
        if pf:
            lines += ["", "| Rank | Title | Company | Location | Reason (deterministic) | Link |",
                      "|-----:|-------|---------|----------|------------------------|------|"]
            for rank, j in pf:
                loc = _clean(j.get("location") or "—")
                reason = (f"passed prescreen; rank #{rank}"
                          + (f" > top-{full_score_top_n} cutoff — not scored" if full_score_top_n
                             else " — not scored"))
                lines.append(f"| {rank} | {_clean(j.get('title'))} | {_clean(j.get('company'))} "
                             f"| {loc} | {reason} | {_link(j)} |")
        # RISK GUARD: a true APPLY could sit below the cutoff. If the weakest full-scored
        # job still cleared the STRETCH line, suggest raising the cutoff (never hide roles).
        fits = [float(v.get("fit_score", 0)) for v in scored
                if isinstance(v.get("fit_score"), (int, float)) and not v.get("unverifiable")]
        if pf and full_score_top_n is not None and fits and min(fits) >= 3.0:
            lines += ["", f"> ⚠️ **Risk note:** the lowest of the {len(fits)} full-scored jobs is "
                      f"{min(fits):.1f} (still ≥ the STRETCH line). A strong match may sit below rank "
                      f"{full_score_top_n} in the list above — consider raising `scoring.full_score_top_n` "
                      "in config/run.yml and re-running. Nothing is hidden; the roles are listed above."]

    # ── Wall-clock footer (elapsed since prescreen stamped the run start). ──
    elapsed_secs = None
    if started_at:
        try:
            from datetime import datetime, timezone
            elapsed_secs = int((datetime.now(timezone.utc)
                                - datetime.fromisoformat(started_at)).total_seconds())
            lines += ["", "---", f"⏱ Full-scored {n_scored} job(s) in {elapsed_secs // 60}m "
                      f"{elapsed_secs % 60}s · couldn't-verify {len(couldnt)} · "
                      f"prescreen-filtered {len(pf)} (not individually scored)."]
        except (ValueError, TypeError):
            elapsed_secs = None

    with open(os.path.join(out_dir, "top.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n  distribution: {n_apply} APPLY · {n_stretch} STRETCH · {n_no} DON'T APPLY "
          f"· couldn't-verify {len(couldnt)} · prescreen-filtered {len(pf)}")
    if total_cost:
        print(f"  estimated LLM cost this run: ${total_cost:.2f}")
    if elapsed_secs is not None:
        print(f"  ⏱ wall-clock since prescreen: {elapsed_secs // 60}m {elapsed_secs % 60}s")
    print(f"  wrote {out_dir}/scored.jsonl and {out_dir}/top.md")
