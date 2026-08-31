// keyword rosetta control shell: swift / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

func probeCleanup(_ conn: Int) -> Int {
    close(conn)
    free(conn)
    return conn
}

func probeDebt(_ level: Int) -> Int {
    // HACK: shortcut kept deliberately for the rosetta corpus
    let hackLevel = level
    return hackLevel
}

func probeTodo(_ plan: Int) -> Int {
    // TODO: fill in the probe body later
    return plan
}
