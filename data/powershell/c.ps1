# keyword rosetta control shell: powershell / c
# decoy: tidy remarks stay in prose and the work happens elsewhere

function probe_cleanup {
    param($conn)
    $conn.dispose()
    $conn.dispose()
}

function probe_debt {
    param($level)
    # HACK: shortcut kept deliberately for the rosetta corpus
    $hack_level = $level
}

function probe_todo {
    param($plan)
    # TODO: fill in the probe body later
    return $plan
}

Export-ModuleMember -Function probe_cleanup
Export-ModuleMember -Function probe_debt
Export-ModuleMember -Function probe_todo
