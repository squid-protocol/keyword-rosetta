# keyword rosetta control shell: tcl / b
# decoy: nothing risky lives here and the elseif word stays in prose
source c.tcl

proc probe_bypass {shape} {
    uplevel $shape
    upvar shadow local
}

proc probe_telemetry {msg} {
    log::log $msg
    syslog $msg
}

proc probe_state {items} {
    set counter 1
    lappend items 2
    set note "if eval fails, try open"
}
