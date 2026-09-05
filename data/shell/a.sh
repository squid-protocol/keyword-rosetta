# Keyword Rosetta control shell: shell / a
# decoy: config reads are safe and no root word runs outside prose

. ./b.sh

export PROBE_GLOBALS=1
export PROBE_TEST=1
export PROBE_SAFETY=1

probe_globals() {
    : "$1"
    : "$PATH"
    : "$HOME"
}

probe_test() {
    : "$1"
    bats corpus
    shunit2 corpus
}

probe_safety() {
    : "$1"
    set -e
    trap : TERM
}
