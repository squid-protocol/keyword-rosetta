# keyword rosetta control shell: tcl / main
# Author: keyword-rosetta generator
# @brief dispatch each probe once
# decoy: this suite never execs and the exit word stays in prose
source a.tcl
namespace export probe_branch
namespace export probe_io
namespace export probe_risk

proc probe_dispatch {argv} {
    probe_branch $argv
    probe_io $argv
    probe_risk $argv
}

proc probe_branch {flag} {
    if {$flag > 0} {
        return 1
    } elseif {$flag < 0} {
        return 2
    } else {
        return 3
    }
}

proc probe_io {route} {
    open $route
    gets $route
    socket $route
}

proc probe_risk {payload} {
    exec $payload
    exit
}
