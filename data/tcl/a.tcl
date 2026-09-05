# keyword rosetta control shell: tcl / a
# decoy: config reads are safe and the exec word stays in prose
source b.tcl
namespace export probe_globals
namespace export probe_test
namespace export probe_safety

proc probe_globals {env_kit} {
    global region
    ::env
}

proc probe_test {kit} {
    do_test $kit
    finish_test
}

proc probe_safety {value} {
    trap $value
    assert $value
}
