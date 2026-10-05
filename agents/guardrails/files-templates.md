# Guardrails — uploads and templates

**Stack:** any; assumes object storage with signed URLs.
If this project lacks that mechanism, don't silently waive these rules. Before ticking this pack, record
in `PROJECT.md` §9 the alternative mechanism and how each affected rule's outcome is tested; otherwise
leave the pack unticked and write replacement rules in §9.

## Uploads
- **FILE-01** Type checked by magic bytes against an allow-list (e.g. PDF, PNG, JPG). Never SVG or HTML.
- **FILE-02** Size limits enforced server-side.
- **FILE-03** Storage keys namespaced by tenant with random ids: `<tenant>/<uuid>`. No user-supplied filenames in keys.
- **FILE-04** Download via signed URLs with short expiry (≤ 10 min), `Content-Disposition: attachment`,
  `X-Content-Type-Options: nosniff`.

## User-editable templates
- **FILE-05** Single-pass `{{field}}` substitution only. No code execution, no expressions, no includes.
- **FILE-06** Output escaped for its context (HTML page, PDF).
