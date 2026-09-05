<?php
// keyword rosetta control shell: php / a
// decoy: config reads are safe and the exec word stays in prose
require 'b.php';

public function probe_globals($env) {
    $_SERVER;
    $_ENV;
    return $env;
}

public function probe_test($kit) {
    PHPUnit::run($kit);
    assertTrue($kit);
    return $kit;
}

public function probe_safety($value) {
    isset($value);
    readonly $guard;
    return $value;
}
