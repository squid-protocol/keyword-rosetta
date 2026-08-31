// keyword rosetta control shell: zig / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

fn probeCleanup(conn: i32) i32 {
    deinit(conn);
    free(conn);
    return conn;
}

fn probeDebt(level: i32) i32 {
    // HACK: shortcut kept deliberately for the rosetta corpus
    const hackLevel = level;
    return hackLevel;
}

fn probeTodo(plan: i32) i32 {
    // TODO: fill in the probe body later
    return plan;
}
