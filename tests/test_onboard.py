"""Onboarding writer tests — the deterministic, agent-callable --answers path. No network, no TTY.

Proves: --answers writes a valid config/profile.yml + resume.md; work_mode maps onto the
[GATE] location fields; validation rejects missing required fields + a too-short résumé with
NO partial write; the answers file is deleted after a successful write (PII hygiene); doctor
blocks on a template/empty profile and passes on a real one; and _interactive() refuses when
there is no TTY (no silent no-op).

Run:  python -m pytest tests/test_onboard.py -q   (or: python tests/test_onboard.py)
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from jobfinder import onboard, doctor


def _root():
    d = tempfile.mkdtemp(prefix="jf-onb-")
    os.makedirs(os.path.join(d, "config"), exist_ok=True)
    onboard.ROOT = d
    doctor.ROOT = d
    return d


def _full_answers(**over):
    a = {"resume_text": "Harsh Garg — AI delivery manager. "
                        + "Delivery governance, RAG, LangChain, stakeholder management. " * 12,
         "full_name": "Harsh Garg", "email": "h@x.com", "base_city": "Hyderabad, India",
         "target_roles": ["AI Delivery Manager", "Technical Program Manager - AI"],
         "years_total": 8, "years_in_function": 2.5, "honest_ceiling": "manager",
         "work_mode": "remote", "floor_ctc_lpa": 20, "target_ctc_lpa": 28}
    a.update(over)
    return a


def test_answers_writes_valid_profile_and_resume():
    d = _root()
    res = onboard.write_from_answers(_full_answers())
    assert "error" not in res, res
    assert os.path.exists(os.path.join(d, "resume.md"))
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["candidate"]["full_name"] == "Harsh Garg"
    assert prof["seniority"]["honest_ceiling"] == "manager"
    assert prof["target_roles"]["primary"][0] == "AI Delivery Manager"
    assert prof["location"]["base_city"] == "Hyderabad, India"
    assert prof["compensation"]["floor_ctc_lpa"] == 20
    # function.* auto-derived from target_roles
    assert prof["function"]["in_scope"] == prof["target_roles"]["primary"]
    assert prof["function"]["out_of_scope"] == []           # B-2: empty by default, not one persona's opposites
    print("✓ --answers writes a valid profile.yml + resume.md; function.* derived")


def test_work_mode_maps_to_gate_location():
    _root()
    onsite = onboard._answers_to_profile(_full_answers(work_mode="onsite", onsite_cities=["Pune"]))
    assert onsite["location"]["remote_ok"] is False and onsite["location"]["hybrid_ok"] is False
    assert onsite["location"]["onsite_cities"] == ["Pune"]
    remote = onboard._answers_to_profile(_full_answers(work_mode="remote"))
    assert remote["location"]["remote_ok"] is True and remote["location"]["onsite_cities"] == ["Hyderabad"]
    print("✓ work_mode → remote_ok / hybrid_ok / onsite_cities [GATE] mapping")


def test_validate_nothing_required_except_resume():
    d = _root()
    # NOTHING is strictly required now — an empty answers dict is valid
    assert onboard.validate_answers({}) == []
    assert onboard.validate_answers({"work_mode": "onsite"}) == []      # onsite no longer forces a city
    # only MALFORMED supplied values are flagged (format-only guard)
    assert any("work_mode" in p for p in onboard.validate_answers({"work_mode": "bogus"}))
    assert any("honest_ceiling" in p for p in onboard.validate_answers({"honest_ceiling": "wizard"}))
    assert any("floor_ctc_lpa" in p for p in onboard.validate_answers({"floor_ctc_lpa": "lots"}))
    # a résumé ALONE writes a full profile — no roles / work-mode / ceiling needed
    res = onboard.write_from_answers({"resume_text": "x" * 400})
    assert "error" not in res and os.path.exists(os.path.join(d, "config", "profile.yml"))
    # but the résumé itself is still required
    _root()
    r2 = onboard.write_from_answers({"target_roles": ["PM"]})           # no résumé, no resume.md
    assert r2.get("error") and "résumé" in r2["error"].lower()
    print("✓ nothing required but the résumé; only malformed supplied values are flagged")


def test_resume_too_short_is_rejected():
    d = _root()
    res = onboard.write_from_answers(_full_answers(resume_text="too short"))
    assert res.get("error") and "too short" in res["error"]
    assert not os.path.exists(os.path.join(d, "resume.md"))   # useless resume.md NOT written
    print("✓ too-short résumé → clear error, resume.md not written")


def test_answers_file_deleted_after_write():
    d = _root()
    ans = os.path.join(d, "_onboard_answers.json")
    json.dump(_full_answers(), open(ans, "w"))
    rc = onboard.cmd(["--answers", ans])
    assert rc == 0 and not os.path.exists(ans)                # PII: deleted post-write
    assert os.path.exists(os.path.join(d, "config", "profile.yml"))
    print("✓ answers file deleted after a successful --answers write (PII hygiene)")


def test_doctor_blocks_on_template_passes_on_real():
    d = _root()
    tmpl = os.path.join(d, "config", "profile.yml")
    yaml.safe_dump({"candidate": {"full_name": "Your Name"}}, open(tmpl, "w"))
    assert onboard._profile_is_placeholder(tmpl)
    assert not doctor._profile_ready(os.path.join("config", "profile.yml"))   # template → blocked
    onboard.write_from_answers(_full_answers(), force=True)                   # real profile
    assert doctor._profile_ready(os.path.join("config", "profile.yml"))
    print("✓ doctor blocks on template/empty profile, passes on a real one")


def test_no_tty_interactive_refuses():
    _root()
    orig = sys.stdin
    try:
        sys.stdin = type("F", (), {"isatty": lambda self: False})()
        rc = onboard._interactive()
    finally:
        sys.stdin = orig
    assert rc == 2                     # refuses; never silently seeds-and-collects-nothing
    print("✓ no-TTY _interactive() refuses (exit 2), no silent no-op")


def _run_direct(select_map, input_fn, resume="x" * 400):
    """Drive _interactive() with scripted _select/_input + a simulated TTY. Returns rc."""
    saved = (onboard._select, onboard._input, onboard._read_pasted)
    orig_stdin = sys.stdin
    onboard._select = lambda q, choices, default=None: next(v for k, v in select_map.items() if k in q.lower())
    onboard._input = input_fn
    onboard._read_pasted = lambda: resume
    try:
        sys.stdin = type("F", (), {"isatty": lambda s: True})()
        return onboard._interactive()
    finally:
        onboard._select, onboard._input, onboard._read_pasted = saved
        sys.stdin = orig_stdin


def test_direct_run_writes_valid_profile_and_resume():
    d = _root()
    txt = {"full name": "Harsh Garg", "email": "h@x.com", "base city": "Hyderabad, India",
           "target roles": "AI Delivery Manager, TPM - AI", "years total": "8",
           "target function": "2.5", "floor": "20", "target comp": "28", "hard constraints": ""}
    rc = _run_direct(
        {"résumé": onboard._RESUME_CHOICES[0], "ceiling": "Manager", "work-mode": "Remote", "relocat": "No"},
        lambda p, default="": next((v for k, v in txt.items() if k in p.lower()), ""))
    assert rc == 0
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["candidate"]["full_name"] == "Harsh Garg"
    assert prof["location"]["remote_ok"] is True and prof["seniority"]["honest_ceiling"] == "manager"
    assert prof["target_roles"]["primary"][0] == "AI Delivery Manager"
    assert os.path.exists(os.path.join(d, "resume.md"))
    print("✓ direct-run onboard writes a valid profile.yml + resume.md (arrow-select flow)")


def test_retry_cap_on_bad_resume_no_infinite_loop():
    _root()
    calls = {"paste": 0}
    saved = (onboard._select, onboard._input, onboard._read_pasted)
    orig = sys.stdin

    def paste():
        calls["paste"] += 1
        return "too short"                        # < MIN_RESUME_CHARS every time → never usable

    onboard._select = lambda q, choices, default=None: (
        onboard._RESUME_CHOICES[0] if "résumé" in q.lower() else (default or choices[0]))
    onboard._input = lambda p, default="": default
    onboard._read_pasted = paste
    try:
        sys.stdin = type("F", (), {"isatty": lambda s: True})()
        rc = onboard._interactive()
    finally:
        onboard._select, onboard._input, onboard._read_pasted = saved
        sys.stdin = orig
    assert rc == 1                                # exits cleanly — did NOT loop forever
    assert calls["paste"] == 3                    # collect(1) + 2 refills, then capped — bounded
    print("✓ retry cap: a persistently-bad résumé exits after 3 tries (no infinite loop)")


def test_parse_cleanliness_pipe_split_and_full_span_years():
    text = ("HARSH GARG\n"
            "AI Solutions Consultant | Business Analyst\n"
            "Hyderabad, India | h@example.com\n"
            "PROFESSIONAL EXPERIENCE\n"
            "Project Manager\tSeptember 2016 – December 2024\n"
            "Acme Corp | Hyderabad\n"
            "Business Analyst   May 2016 - August 2019\n"
            "• Led delivery and stakeholder management across teams.\n")
    p = onboard._parse_resume_fields(text)
    roles = p.get("target_roles") or []
    assert "AI Solutions Consultant" in roles and "Business Analyst" in roles   # pipe header → BOTH
    assert "Project Manager" in roles
    import re as _re
    months = _re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", _re.I)
    for r in roles:
        assert "\t" not in r and "|" not in r
        assert not _re.search(r"\d", r), r         # no dates/years leaked into a role
        assert not months.search(r), r             # no month names leaked in
    assert p["years_total"] == 8                   # full span 2016 → 2024 (closed range, deterministic)
    assert not any(r.lower().startswith("led ") for r in roles)   # a bullet is not a role
    print("✓ parser: pipe-split header roles, clean phrases, full-span years=8")


def test_all_skipped_run_writes_safe_defaults():
    d = _root()
    resume = ("Asha Rao\nAI Consultant | Business Analyst\nPune, India | a@example.com\n"
              "AI Consultant  Jan 2018 - Present\n" + "Delivery and stakeholder work. " * 10)
    saved = (onboard._select, onboard._input, onboard._read_pasted)
    orig = sys.stdin

    def sel(q, choices, default=None):
        ql = q.lower()
        if "résumé" in ql:
            return onboard._RESUME_CHOICES[0]
        if "ceiling" in ql:
            return "Skip / Not sure"              # the new explicit skip option → mid
        return default or choices[0]

    onboard._select = sel
    onboard._input = lambda p, default="": default        # Enter on every prompt
    onboard._read_pasted = lambda: resume
    try:
        sys.stdin = type("F", (), {"isatty": lambda s: True})()
        rc = onboard._interactive()
    finally:
        onboard._select, onboard._input, onboard._read_pasted = saved
        sys.stdin = orig
    assert rc == 0
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["seniority"]["honest_ceiling"] == "mid"                    # Skip / Not sure → mid
    assert prof["location"]["remote_ok"] and prof["location"]["hybrid_ok"]  # work-mode default = mix
    assert prof["location"]["willing_to_relocate"] is False                # relocate default = No
    assert prof["compensation"]["floor_ctc_lpa"] is None                    # comp skipped → no gate
    assert prof["candidate"]["full_name"] == "Asha Rao"                     # derived, Enter-accepted
    assert doctor._profile_ready(os.path.join("config", "profile.yml"))
    print("✓ all-skipped run writes a valid profile with safe defaults (ceiling=mid, mix, no comp)")


def test_empty_target_roles_safe_end_to_end():
    d = _root()
    res = onboard.write_from_answers({"resume_text": "z" * 400})   # nothing parses → empty roles
    assert "error" not in res
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["target_roles"]["primary"] == []                  # empty is allowed
    assert prof["function"]["out_of_scope"] == []                 # B-2: empty → cap won't fire on an unknown
    assert doctor._profile_ready(os.path.join("config", "profile.yml"))   # READY with empty roles
    from jobfinder.prescreen import prescreen_set
    from jobfinder.schema import JobPosting
    jobs = [JobPosting(title="Business Analyst", company="C", source="ats", location="Hyderabad, India"),
            JobPosting(title="AI Program Manager", company="C", source="ats", location="Remote, India")]
    kept, rep = prescreen_set(jobs, prof, {"prescreen": {"max_llm_jobs": 40}})
    assert isinstance(kept, list) and rep["input"] == 2           # prescreen runs, no crash
    print("✓ empty target_roles safe end-to-end: writes, doctor READY, prescreen runs")


def test_resume_choices_exactly_three_no_template():
    assert len(onboard._RESUME_CHOICES) == 3
    joined = " ".join(onboard._RESUME_CHOICES).lower()
    for banned in ("template", "sample", "describe", "draft", "starter"):
        assert banned not in joined, banned
    assert "paste" in joined and "path" in joined and "linkedin" in joined
    print("✓ résumé options are exactly paste / path / LinkedIn — no template/sample/describe")


def test_parse_resume_fields_derives_and_is_safe():
    text = ("HARSH GARG\nharsh.garg@example.com | Hyderabad, India\nSenior Product Manager\n\n"
            "EXPERIENCE\nProduct Manager, Acme Corp    2019 - Present\n"
            "Business Analyst, Beta Ltd    2016 - 2019\n"
            "Led AI delivery, roadmap, stakeholder management across teams.")
    p = onboard._parse_resume_fields(text)
    assert p["email"] == "harsh.garg@example.com"
    assert p["full_name"] == "HARSH GARG"
    assert p["base_city"] == "Hyderabad, India"
    assert isinstance(p["years_total"], int) and p["years_total"] > 0
    assert p["target_roles"] and any("manager" in r.lower() for r in p["target_roles"])
    assert onboard._parse_resume_fields("") == {}                 # never raises; {} on empty
    assert isinstance(onboard._parse_resume_fields("!!! \n @@@ \n 123"), dict)
    assert onboard._ceiling_from_years(8) == "Senior" and onboard._ceiling_from_years(None) == "Mid"
    print("✓ _parse_resume_fields derives name/email/city/years/roles; safe on junk")


def test_direct_run_minimal_only_workmode_relocate():
    d = _root()
    resume = ("HARSH GARG\nharsh@example.com | Pune, India\nSenior Product Manager\n"
              "Product Manager, Acme  2018 - Present\nBusiness Analyst, Beta  2015 - 2018\n"
              + "Delivery, roadmap, stakeholder management. " * 8)
    # user presses Enter on EVERY derived/optional prompt (typed = "" → default);
    # only the menus (work-mode, relocate, ceiling) are answered.
    rc = _run_direct({"résumé": onboard._RESUME_CHOICES[0], "ceiling": "Senior",
                      "work-mode": "Remote", "relocat": "No"},
                     lambda p, default="": default, resume=resume)
    assert rc == 0
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["candidate"]["full_name"] == "HARSH GARG"          # derived, accepted with Enter
    assert prof["location"]["base_city"] == "Pune, India"          # derived
    assert prof["target_roles"]["primary"]                          # derived, non-empty
    assert prof["compensation"]["floor_ctc_lpa"] is None            # skipped → no comp gate
    assert prof["location"]["remote_ok"] is True
    print("✓ onboarding completes with ONLY work-mode+relocate answered — rest derived/defaulted")


def test_resume_derived_target_roles_prefills():
    d = _root()
    resume = ("Asha Rao\nasha@example.com\nHyderabad, India\n"
              "Data Analyst, Acme  2020 - Present\nBusiness Analyst, Beta  2017 - 2020\n"
              + "SQL, dashboards, stakeholder reporting. " * 8)
    parsed = onboard._parse_resume_fields(resume)
    assert parsed.get("target_roles")                              # parser suggested roles
    rc = _run_direct({"résumé": onboard._RESUME_CHOICES[0], "ceiling": "Mid",
                      "work-mode": "Remote", "relocat": "No"},
                     lambda p, default="": default, resume=resume)  # Enter-accepts everything
    assert rc == 0
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["target_roles"]["primary"] == parsed["target_roles"]   # suggestion accepted as-is
    print("✓ résumé-derived target_roles pre-fill and are accepted with Enter")


def test_out_of_scope_defaults_empty_not_one_persona():
    # B-2: a skipped out_of_scope must be EMPTY, never the ML/DS/backend list — that
    # pre-declared a data scientist's own function out of scope.
    assert onboard._DEFAULT_OUT_OF_SCOPE == []
    prof = onboard._answers_to_profile({"target_roles": ["Data Scientist"], "work_mode": "remote"})
    assert prof["function"]["out_of_scope"] == []
    for banned in ("ML research", "data scientist", "Backend"):
        assert not any(banned.lower() in s.lower() for s in prof["function"]["out_of_scope"])
    # a caller-supplied value is still honoured
    supplied = onboard._answers_to_profile({"target_roles": ["PM"], "work_mode": "remote",
                                            "function_out_of_scope": ["Front-end engineering"]})
    assert supplied["function"]["out_of_scope"] == ["Front-end engineering"]
    print("✓ out_of_scope defaults to empty (no persona bias); a supplied value still wins")


def test_set_function_out_of_scope_patches_profile():
    d = _root()
    onboard.write_from_answers(_full_answers(), force=True)
    rc = onboard.cmd(["--set", "function_out_of_scope=ML research engineer,Backend software engineering"])
    assert rc == 0
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["function"]["out_of_scope"] == ["ML research engineer", "Backend software engineering"]
    assert prof["candidate"]["full_name"] == "Harsh Garg"        # everything else preserved
    print("✓ --set function_out_of_scope patches in place (the agent's write path for the review)")


def test_agents_gate_routes_to_terminal_no_bypass():
    agents = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "AGENTS.md")
    txt = open(agents, encoding="utf-8").read()
    low = txt.lower()
    assert "python -m jobfinder onboard" in txt                 # routes to the direct-run command
    assert "do not conduct onboarding yourself" in low          # agent does not conduct it
    assert "i've run it" in low                                 # only proceed option = re-check
    assert "hand-edit yaml" in low                              # YAML-edit prohibition is stated
    print("✓ AGENTS.md gate routes to direct-run onboard; no-bypass + no-hand-edit stated")


def test_paste_end_sentinel_terminates_and_echoes():
    import builtins
    import contextlib
    import io
    lines = iter(["Résumé line 1", "Résumé line 2", "END", "PAST-END must NOT be read"])
    saved = builtins.input
    builtins.input = lambda *a: next(lines)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            text = onboard._read_pasted()
    finally:
        builtins.input = saved
    assert text == "Résumé line 1\nRésumé line 2"       # stopped at END; nothing past it consumed
    assert "read 2 lines" in buf.getvalue()             # receipt echo so the paste visibly registered
    print("✓ paste: END sentinel terminates capture + echoes 'read N lines'")


def test_validate_rejects_impossible_years():
    assert any("can't exceed" in p for p in onboard.validate_answers({"years_total": 5, "years_in_function": 8}))
    assert any("between 0 and 45" in p for p in onboard.validate_answers({"years_total": 60}))
    assert any("between 0 and 45" in p for p in onboard.validate_answers({"years_in_function": -3}))
    assert onboard.validate_answers({"years_total": 8, "years_in_function": 3}) == []   # sane → ok
    print("✓ validate rejects years_in_function>years_total and out-of-range years")


def test_set_target_roles_patches_profile_in_place():
    d = _root()
    onboard.write_from_answers(_full_answers(work_mode="onsite", onsite_cities=["Hyderabad"]), force=True)
    before = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    roles = ["AI Delivery Manager", "Implementation Consultant", "Technical Program Manager"]
    rc = onboard.cmd(["--set", "target_roles=" + ",".join(roles)])
    assert rc == 0
    after = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert after["target_roles"]["primary"] == roles
    assert after["function"]["in_scope"] == roles                       # mirror → reaches prescreen
    # everything else preserved (NOT regenerated to defaults)
    assert after["candidate"]["full_name"] == before["candidate"]["full_name"] == "Harsh Garg"
    assert after["location"]["remote_ok"] is False                      # onsite work-mode preserved
    assert after["seniority"]["honest_ceiling"] == before["seniority"]["honest_ceiling"]
    # work_mode patch flips the [GATE] flags without touching relocate
    rc2 = onboard.cmd(["--set", "work_mode=remote"])
    after2 = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert rc2 == 0 and after2["location"]["remote_ok"] is True and after2["location"]["hybrid_ok"] is True
    assert after2["location"]["willing_to_relocate"] == before["location"]["willing_to_relocate"]
    assert onboard.cmd(["--set", "nickname=HG"]) == 1                   # unknown key refused
    print("✓ --set patches target_roles/work_mode in place, preserves the rest, refuses unknown keys")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} onboarding tests passed.")
