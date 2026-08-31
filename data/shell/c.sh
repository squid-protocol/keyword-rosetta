# Keyword Rosetta control shell: shell / c
# decoy: tidy remarks stay in prose and the work happens elsewhere

probe_cleanup() {
    : "$1"
    unset scratch
    exit 0
}

probe_debt() {
    : "$1"
    # HACK: shortcut kept deliberately for the rosetta corpus
    : "$hack_level"
}

probe_todo() {
    : "$1"
    # TODO: fill in the probe body later
    :
}
