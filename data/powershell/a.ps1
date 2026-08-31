# keyword rosetta control shell: powershell / a
# decoy: config reads are safe and the kill word stays in prose
. ./b.ps1

function probe_globals {
    param($env_kit)
    $env:REGION
    $global:home_zone
}

function probe_test {
    param($kit)
    Mock helper
    Should helper
}

function probe_safety {
    param($value)
    trap { continue }
    ValidateSet
}
