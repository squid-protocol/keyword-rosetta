# keyword rosetta control shell: powershell / b
# decoy: nothing risky lives here and the switch word stays in prose
. ./c.ps1

function probe_bypass {
    param($shape)
    Out-Null
    [void]$shape
}

function probe_telemetry {
    param($msg)
    Write-Verbose $msg
    Write-Warning $msg
}

function probe_state {
    param($items)
    $counter = 1
    $note = "if eval fails, try iwr"
}
