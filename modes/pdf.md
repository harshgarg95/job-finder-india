# pdf — SCAFFOLD (not built yet)

Scaffolded to mirror career-ops's `modes/pdf.md` (+ `generate-pdf.mjs`) so it's
drop-in later. **Not implemented in this MVP.** If asked: say it's planned, don't
produce a fake file, and offer the core flow instead.

Intent when built: render an ATS-optimized CV PDF from `resume.md` via an HTML
template (career-ops uses Playwright HTML→PDF; we'd add a small generator tool).
Inputs already present: `resume.md`. To add: a `templates/cv-template.html` + a PDF tool.
