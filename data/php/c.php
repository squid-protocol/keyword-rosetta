<?php
// keyword rosetta control shell: php / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

public function probe_cleanup($conn) {
    unset($conn);
    dispose($conn);
    return $conn;
}

public function probe_debt($level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    return $level;
}

public function probe_todo($plan) {
    // TODO: fill in the probe body later
    return $plan;
}
