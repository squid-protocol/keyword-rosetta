<?php
// keyword rosetta control shell: php / b
// decoy: nothing risky lives here and the switch word stays in prose
require 'c.php';

function probe_bypass($shape) {
    unserialize($shape);
    extract($shape);
    return $shape;
}

function probe_telemetry($msg) {
    Log::info($msg);
    Log::error($msg);
    return $msg;
}

function probe_state($items) {
    $counter = 1;
    $note = "if eval fails, try open";
    return $items;
}
