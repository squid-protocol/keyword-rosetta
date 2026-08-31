# Keyword Rosetta control shell: shell / b
# decoy: nothing risky lives here and the fi word stays in prose

. ./c.sh

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
    note="if eval fails, try curl"
}
