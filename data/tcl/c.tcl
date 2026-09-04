# keyword rosetta control shell: tcl / c
# decoy: tidy remarks stay in prose and the work happens elsewhere
namespace export probe_cleanup
namespace export probe_debt
namespace export probe_todo

proc probe_cleanup {conn} {
    close $conn
    unset scratch
}

proc probe_debt {level} {
    # HACK: shortcut kept deliberately for the rosetta corpus
    return $level
}

proc probe_todo {plan} {
    # TODO: fill in the probe body later
    return $plan
}
