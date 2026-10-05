# Guardrails — finalized records (issued documents, orders, contracts)

**Stack:** any; row-lock wording assumes a SQL database.
If this project lacks that mechanism, don't silently waive these rules. Before ticking this pack, record
in `PROJECT.md` §9 the alternative mechanism and how each affected rule's outcome is tested; otherwise
leave the pack unticked and write replacement rules in §9.

## Immutability
- **REC-01 (hard)** Once issued/signed/paid, a record is immutable. Store a frozen JSON snapshot plus its SHA-256 hash;
  that snapshot is the legal record.
- **REC-02** Corrections create a new record (new version, credit note + replacement, amendment). Never edit in place.
- **REC-03** Void keeps the record and its number.
- **REC-04** Parties referenced by finalized records are archived, never deleted.
- **REC-05** Any snapshot of sensitive reference data (e.g. bank details) is taken at issue time; changes to the
  live value notify the owner and are audited.

## Numbering
- **REC-06** Numbers are assigned at issue/send only, never at draft.
- **REC-07** Numbers come from one atomic, concurrency-safe allocator (a row lock such as `SELECT … FOR UPDATE` on the counter in SQL, or an equivalent named in `PROJECT.md` §9). No gaps.
- **REC-08** Period tokens (year, month) use the tenant's timezone, not the server's.
- **REC-09** Changing the numbering pattern never rewrites old numbers.
- **REC-10** Concurrency test exists: parallel issues produce unique, gapless numbers.

## Generated files
- **REC-11** Official PDFs are rendered once (in the worker, at first send), stored, and never regenerated.
- **REC-12** Draft previews are watermarked and not stored.
