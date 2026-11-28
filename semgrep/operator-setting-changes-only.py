# Fixture for `semgrep --test semgrep/` (rule operator-setting-changes-only).


def sets(cursor, code, name):
    # ruleid: operator-setting-changes-only
    cursor.execute("SELECT set_config('skiw.operator', %s, true)", [code])
    # ruleid: operator-setting-changes-only
    cursor.execute("SELECT current_setting('skiw.operator', true)")
    # ruleid: operator-setting-changes-only
    cursor.execute("SET LOCAL skiw.operator = 'x'")
    # ruleid: operator-setting-changes-only
    cursor.execute("set skiw . operator to default")
    # ruleid: operator-setting-changes-only
    cursor.execute("SET LOCAL SKIW.OPERATOR = 'x'")
    # ruleid: operator-setting-changes-only
    cursor.execute('SET LOCAL "skiw"."operator" = \'x\'')
    # ruleid: operator-setting-changes-only
    cursor.execute("SET LOCAL \"skiw.operator\" = 'x'")
    # ruleid: operator-setting-changes-only
    cursor.execute(f"SELECT set_config('skiw.operator', '{code}', true)")
    # ruleid: operator-setting-changes-only
    cursor.execute(f"SET LOCAL skiw.{'operator'} = 'x'")
    # ruleid: operator-setting-changes-only
    cursor.execute("SELECT set_config('skiw." "operator', %s, true)", [code])  # fmt: skip
    # ruleid: operator-setting-changes-only
    cursor.execute("SELECT set_config('skiw." + "operator', %s, true)", [code])
    # ruleid: operator-setting-changes-only
    cursor.execute(b"SET LOCAL skiw.operator = 'x'")
    # ruleid: operator-setting-changes-only
    cursor.execute(r"SET LOCAL skiw.operator = 'x'")


# ruleid: operator-setting-changes-only
OPTIONS = {"options": "-c skiw.operator=ghost"}

# ruleid: operator-setting-changes-only
SETTING = "skiw.operator"


def documented():
    # ruleid: operator-setting-changes-only
    """Sets
    skiw.operator before the write."""


def quiet(cursor, name, part):
    # A comment naming skiw.operator is not a string.
    # ok: operator-setting-changes-only
    cursor.execute("SELECT set_config('app.tenant_token', %s, true)", [name])
    # ok: operator-setting-changes-only
    cursor.execute("SELECT 'skiw.operators', 'myskiw.operator', 'skiw.operator_x'")
    # ok: operator-setting-changes-only
    cursor.execute("SELECT 'skiw_operator', 'operator'")
    # A line-level suppression, as accounts/access/seed.py uses it.
    # ok: operator-setting-changes-only
    cursor.execute("SET LOCAL skiw.operator = 'x'")  # nosemgrep: operator-setting-changes-only
    # Known misses (DECISIONS M4r-5a-i): a name split around a runtime value, an SQL comment
    # inside the name, a name built from non-literal parts.
    # ok: operator-setting-changes-only
    cursor.execute(f"SET LOCAL skiw.{part} = 'x'")
    # ok: operator-setting-changes-only
    cursor.execute("SET LOCAL skiw/**/.operator = 'x'")
    # ok: operator-setting-changes-only
    cursor.execute("SET LOCAL " + ".".join(["skiw", "operator"]) + " = 'x'")
