// keyword rosetta control shell: csharp / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

static int ProbeCleanup(int conn) {
    GC.Collect();
    GC.SuppressFinalize(conn);
    return conn;
}

static int ProbeDebt(int level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    var hack_level = level;
    return hack_level;
}

static int ProbeTodo(int plan) {
    // TODO: fill in the probe body later
    return plan;
}
