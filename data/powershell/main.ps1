# keyword rosetta control shell: powershell / main
# Author: keyword-rosetta generator
.SYNOPSIS
# decoy: this suite never invokes iex words outside prose
. ./a.ps1

function probe_dispatch {
    param($argv)
    probe_branch
    probe_io
    probe_risk
}

function probe_branch {
    param($flag)
    if ($flag -gt 0) {
        return 1
    } else {
        return 2
    }
    switch ($flag) {}
}

function probe_io {
    param($route)
    iwr localhost
    irm localhost
    TcpClient
}

function probe_risk {
    param($payload)
    iex $payload
    kill $payload
}

Export-ModuleMember -Function probe_branch
Export-ModuleMember -Function probe_io
Export-ModuleMember -Function probe_risk
