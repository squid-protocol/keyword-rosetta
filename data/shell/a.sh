# Keyword Rosetta control shell: shell / a
# decoy: config reads are safe and no root word runs outside prose

. ./b.sh

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
