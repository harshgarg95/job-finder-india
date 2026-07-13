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
    assert prof["function"]["out_of_scope"]                # non-empty default
    print("✓ --answers writes a valid profile.yml + resume.md; function.* derived")


def test_work_mode_maps_to_gate_location():
    _root()
    onsite = onboard._answers_to_profile(_full_answers(work_mode="onsite", onsite_cities=["Pune"]))
    assert onsite["location"]["remote_ok"] is False and onsite["location"]["hybrid_ok"] is False
    assert onsite["location"]["onsite_cities"] == ["Pune"]
    remote = onboard._answers_to_profile(_full_answers(work_mode="remote"))
    assert remote["location"]["remote_ok"] is True and remote["location"]["onsite_cities"] == ["Hyderabad"]
    print("✓ work_mode → remote_ok / hybrid_ok / onsite_cities [GATE] mapping")


def test_validate_missing_required_no_write():
    d = _root()
    res = onboard.write_from_answers({"full_name": "X"})     # missing almost everything
    assert res.get("error") and res.get("problems")
    assert any("floor_ctc_lpa" in p for p in res["problems"])
    assert any("work_mode" in p for p in res["problems"])
    assert not os.path.exists(os.path.join(d, "config", "profile.yml"))   # nothing written
    r2 = onboard.write_from_answers(_full_answers(work_mode="onsite"))     # onsite w/o cities
    assert r2.get("error") and any("onsite_cities" in p for p in r2["problems"])
    print("✓ validation rejects missing required + onsite-without-city; no partial write")


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


def test_direct_run_loops_until_required_present():
    d = _root()
    calls = {"floor": 0}

    def input_fn(p, default=""):
        pl = p.lower()
        if "floor" in pl:
            calls["floor"] += 1
            return "" if calls["floor"] == 1 else "20"     # missing first pass → re-asked
        return {"full name": "H G", "email": "", "base city": "Hyderabad, India",
                "target roles": "AI PM", "years total": "8", "target function": "2.5",
                "target comp": "", "hard constraints": ""}.get(
            next((k for k in ("full name", "email", "base city", "target roles", "years total",
                              "target function", "target comp", "hard constraints") if k in pl), ""), "")

    rc = _run_direct({"résumé": onboard._RESUME_CHOICES[0], "ceiling": "Mid",
                      "work-mode": "Remote", "relocat": "No"}, input_fn, resume="y" * 400)
    assert rc == 0 and calls["floor"] >= 2                  # re-asked the missing floor, then wrote
    prof = yaml.safe_load(open(os.path.join(d, "config", "profile.yml"), encoding="utf-8"))
    assert prof["compensation"]["floor_ctc_lpa"] == 20
    print("✓ direct-run loops until required fields present (re-asks, then writes)")


def test_resume_choices_exactly_three_no_template():
    assert len(onboard._RESUME_CHOICES) == 3
    joined = " ".join(onboard._RESUME_CHOICES).lower()
    for banned in ("template", "sample", "describe", "draft", "starter"):
        assert banned not in joined, banned
    assert "paste" in joined and "path" in joined and "linkedin" in joined
    print("✓ résumé options are exactly paste / path / LinkedIn — no template/sample/describe")


def test_agents_gate_routes_to_terminal_no_bypass():
    agents = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "AGENTS.md")
    txt = open(agents, encoding="utf-8").read()
    low = txt.lower()
    assert "python -m jobfinder onboard" in txt                 # routes to the direct-run command
    assert "do not conduct onboarding yourself" in low          # agent does not conduct it
    assert "i've run it" in low                                 # only proceed option = re-check
    assert "hand-edit yaml" in low                              # YAML-edit prohibition is stated
    print("✓ AGENTS.md gate routes to direct-run onboard; no-bypass + no-hand-edit stated")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"\nAll {len(fns)} onboarding tests passed.")
