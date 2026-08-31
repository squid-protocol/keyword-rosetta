# Keyword Rosetta control shell: python / c
# decoy: closing remarks stay in prose, tidy work happens elsewhere


def probe_cleanup(conn):
    conn.close()
    conn.shutdown()
    return conn


def probe_debt(level):
    # HACK: shortcut kept deliberately for the rosetta corpus
    HACK_LEVEL = level
    return HACK_LEVEL


def probe_todo(plan):
    # TODO: fill in the probe body later
    return plan
