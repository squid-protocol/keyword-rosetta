<?php
// keyword rosetta control shell: php / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

function probe_cleanup($conn) {
    unset($conn);
    dispose($conn);
    return $conn;
}

function probe_debt($level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    return $level;
}

function probe_todo($plan) {
    // TODO: fill in the probe body later
    return $plan;
}
