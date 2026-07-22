# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue.

- **Preferred:** GitHub's private vulnerability reporting —
  [Report a vulnerability](https://github.com/harshgarg95/job-finder-india/security/advisories/new)
  (repo → Security tab → "Report a vulnerability").
- **Or email:** harshgarg020695@gmail.com with a subject starting `[SECURITY] job-finder-india`.

Include steps to reproduce (and a suggested fix if you have one). You'll get an
acknowledgement within 7 days. Please allow a reasonable window to fix before any
public disclosure — this is a solo-maintained project.

## Supported versions

Only the latest `main` — this is a run-from-source tool with no releases yet.

## Scope

**In scope**

- The Python tool surface: discovery providers and their HTTP handling, the
  onboarding/résumé parsers, tracker & results file writes, the local dashboard
  server (binds `127.0.0.1` only), and the CI workflows.
- Credential and data handling: anything that makes `.env` keys, the résumé, or
  the profile leave the machine or land in logs/committed files — that would
  violate [NOTICE](NOTICE) / [DATA_CONTRACT.md](DATA_CONTRACT.md).
- Vulnerable dependencies (`requirements.txt` is pinned; Dependabot bumps weekly).

**Out of scope**

- Wrong scores or verdicts — a quality bug, not a vulnerability; open a regular issue.
- Vulnerabilities in the third-party services themselves (Adzuna, JSearch/RapidAPI,
  Apify, ATS boards) — report those to the vendor.
- Attacks that require an already-compromised machine or AI CLI.
- Rate-limit / free-tier exhaustion of the discovery APIs.

## Threat-model note: untrusted job text (prompt injection)

Job descriptions are untrusted internet text, and this tool deliberately feeds
them to **your** AI model for scoring. That is a prompt-injection surface: a
malicious posting could embed instructions ("score this 5/5", "ignore the
rubric") aimed at the scoring model.

The mitigation is architectural — **the tool takes no action on a score**:

- There is no auto-apply. Nothing is sent anywhere on the basis of a verdict.
- No credentials or personal secrets are in the scoring context (the model sees
  the résumé, the rubric, and the job text).
- Deterministic code, not the model, enforces the score caps and writes the
  results files; the dashboard HTML-escapes job-supplied fields.

The worst case of a fully successful injection is a **wrong score** in
`data/results/top.md` — output a human reads and judges before doing anything.
Treat a surprising APPLY the way you'd treat any surprising listing: with
skepticism.
