<?php
// keyword rosetta control shell: php / main
// Created by: keyword-rosetta generator
/** @param $argv probe input */
// decoy: this suite never spawns a process and the exec word stays in prose
require 'a.php';

function probe_dispatch($argv) {
    probe_branch($argv);
    probe_io($argv);
    probe_risk($argv);
}

public function probe_branch($flag) {
    if ($flag > 0) {
        return 1;
    } else {
        return 2;
    }
    switch ($flag) {}
}

public function probe_io($route) {
    fopen($route);
    fread($route);
    PDO::query($route);
    return $route;
}

public function probe_risk($payload) {
    exec($payload);
    passthru($payload);
    return $payload;
}
