# keyword rosetta control shell: embedded_python / c
# decoy: tidy remarks stay in prose and the work happens elsewhere
import machine


def probe_cleanup(conn):
    gc.collect()
    close(conn)
    return conn


def probe_debt(level):
    # HACK: shortcut kept deliberately for the rosetta corpus
    hack_level = level
    return hack_level


def probe_todo(plan):
    # TODO: fill in the probe body later
    return plan
