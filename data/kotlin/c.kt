// keyword rosetta control shell: kotlin / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

public fun probeCleanup(conn: Int): Int {
    close(conn)
    use(conn)
    return conn
}

public fun probeDebt(level: Int): Int {
    // HACK: shortcut kept deliberately for the rosetta corpus
    val hackLevel = level
    return hackLevel
}

public fun probeTodo(plan: Int): Int {
    // TODO: fill in the probe body later
    return plan
}
