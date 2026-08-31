# keyword rosetta control shell: embedded_python / a
# decoy: config reads are safe and the reset word stays in prose
machine.idle()

from b import probe_telemetry


def probe_globals(env):
    region = sys.path
    home = os.environ
    return env


def probe_test(kit):
    suite = unittest
    bench = pytest
    return kit


def probe_safety(value):
    assert isinstance(value, int)
    return value
