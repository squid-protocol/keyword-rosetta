// keyword rosetta control shell: java / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

static int probeCleanup(int conn) {
    close(conn);
    release(conn);
    return conn;
}

static int probeDebt(int level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    int hack_level;
    return level;
}

static int probeTodo(int plan) {
    // TODO: fill in the probe body later
    return plan;
}
