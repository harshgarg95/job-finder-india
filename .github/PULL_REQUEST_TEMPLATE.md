# What & why

<!-- One or two sentences: what changes, and what problem it solves. Link the issue if one exists. -->

Fixes #

## Evidence

<!-- For behavior changes to discovery/prescreen/ranking/output: paste before/after
     output. For silent-wrong fixes: show the failing case the new test covers. -->

## Checklist

- [ ] `python -m pytest tests/ -q` is green locally (new behavior has new tests)
- [ ] `prompts/_rubric.md`, `prompts/score-job.md`, and `jobfinder/score.py` are untouched
      (or an issue discussing the change is linked)
- [ ] No personal data, keys, or tokens in code, tests, fixtures, or docs
- [ ] Errors/empty states stay LOUD — nothing new can fail silently
- [ ] Docs updated if user-visible behavior changed (README / GETTING_STARTED / modes/)
