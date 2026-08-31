// keyword rosetta control shell: groovy / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

def probeCleanup(conn) {
    close(conn)
    dispose(conn)
    return conn
}

def probeDebt(level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    def hackLevel = level
    return hackLevel
}

def probeTodo(plan) {
    // TODO: fill in the probe body later
    return plan
}
