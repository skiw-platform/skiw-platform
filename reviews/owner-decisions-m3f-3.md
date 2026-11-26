# Owner decisions for M3f-3 (recorded by the reviewer)

<!-- Only the reviewer writes this file. These are the owner's answers given directly to the reviewer
in chat; they are the evidence for the decisions-log entries the builder adds through a reviewed PR. -->

## 2026-11-06 — Ying, in the reviewer session
The owner's exact reply: "1a 2ok 3yes 4yes", answering the four questions I put to them that day.

1. **ASK-1 = (a): TOTP is required for every user; a passkey is optional, for everyone, owner and admin
   included.**
   - **Conflicts with the approved spec v1.21:**
     - D7 (line 91, "mandatory passkeys … owner/admin roles require a passkey");
     - T5 (line 574, "Passkey mandatory (owner/admin)");
     - Flow 5.1 (4) ("First login … forces passkey enrolment; owner/admin cannot finish without one").
   - **The plan carries the same rule:** plan M3 line 24 (AUTH-03 row "owner/admin must have a
     passkey"), Q9, the line 195 gap note, line 114 (enrolment "password, passkey, … optional TOTP") and
     line 131 (the M3i e2e enrols a passkey).
   - **Accepted risk (owner, 2026-11-06):**
     - TOTP can be phished in real time; owner and admin accounts can be protected by TOTP alone.
     - The reviewer recommended (b), passkeys still required for owner/admin. The owner chose (a).
   - **Required before PR 3b-1 is reviewed:**
     - a spec amendment, through `spec` then `review spec`, changing D7, T5 and Flow 5.1 (4), and
       recording the accepted risk and who accepted it;
     - then `setup` (Part B reconcile);
     - the plan rows listed above updated to match.
     - Until then, a PR that makes TOTP the required first factor conflicts with the approved spec and
       gets a P1.
2. **ASK-2: OK.**
   - The TOTP issuer is the fixed string `SKIW Assistant`, and the account name is the user's email.
   - The otpauth label is `SKIW Assistant:<email>`, percent-encoded, with `issuer=SKIW Assistant`.
   - Not configurable, and not the agency name.
3. **M3f-3 as six PRs: yes.**
   - The PRs, in order: S, 3a (PR 119), 3b-1, 3b-2, 3c-1, 3c-2. About 1,600 lines against the plan's
     ≈ 350 for M3f.
   - Accepted as a plan change. It still needs recording in the plan / DECISIONS.
4. **D8: yes.**
   - Adding, removing or regenerating a factor on an active session is deferred to M3h, behind
     step-up.
   - **Reviewer's condition:** the M3h plan row must carry AUTH-07, revoking the user's other sessions
     on every factor add, remove or regenerate, with a test.
   - Until M3h:
     - a lost factor needs the owner-performed reset (Flow 5.1);
     - the runbook's emergency-rotation step "generate new ones at their next sign-in" can't be done by
       users.
   - Neither matters while the real-data gate is locked.

Also closed the same day: PR 115 R1, minimum password length 12 (`SKIW_PW_MIN_LENGTH`). Owner, in the
reviewer session: "Confirm 12 min char".
