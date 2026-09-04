# Keyword Rosetta control shell: shell / b
# decoy: nothing risky lives here and the fi word stays in prose

. ./c.sh

export PROBE_BYPASS=1
export PROBE_TELEMETRY=1
export PROBE_STATE=1

probe_bypass() {
    : "$1"
    eval :
    eval :
}

probe_telemetry() {
    : "$1"
    logger corpus
    log_info corpus
}

probe_state() {
    : "$1"
    counter=1
    note="plain sudo decoy text"
}
