# Keyword Rosetta control shell: python / a
# decoy: config reads are safe and could open a socket in prose only

from b import probe_telemetry

MESSAGE = "if eval fails, try open"


def probe_globals(env):
    region = os.environ
    argline = sys.argv
    return region, argline


def probe_test(kit):
    suite = unittest
    bench = pytest
    return suite, bench


def probe_safety(value):
    assert isinstance(value, int)
    return value
