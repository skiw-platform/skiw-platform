# Guardrails — money

**Stack:** any storage system. In SQL, amounts use a signed 64-bit integer column. In other storage,
use an exact integer representation with at least the range the project needs, and record that
representation and range in the spec.

- **MON-01 (hard)** Store amounts as integer **minor units** (cents, sen) in that exact representation. Never
  pass amounts through floating point — not in storage, not in code, not in JSON.
- **MON-02** Store the currency code next to every amount. Use a currency exponent table; never assume 2 decimals.
- **MON-03** Serialize big integers safely (string or bigint-aware encoder), never through a float.
- **MON-04** Rounding rule is defined **once** in one module, named in the spec, and unit-tested
  (e.g. half away from zero, applied at line or total level exactly as the spec says).
- **MON-05** Never add amounts in different currencies in one sum.
- **MON-06** When a document or order is finalized, freeze the FX rate and base-currency totals on it.
- **MON-07** The server recomputes every price, discount, tax, fee and shipping amount. Client values are advisory.
