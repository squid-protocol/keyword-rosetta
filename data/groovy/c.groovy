// keyword rosetta control shell: groovy / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

public def probeCleanup(conn) {
    close(conn)
    dispose(conn)
    return conn
}

public def probeDebt(level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    def hackLevel = level
    return hackLevel
}

public def probeTodo(plan) {
    // TODO: fill in the probe body later
    return plan
}
