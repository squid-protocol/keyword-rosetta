// keyword rosetta control shell: csharp / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

public static int ProbeCleanup(int conn) {
    GC.Collect();
    GC.SuppressFinalize(conn);
    return conn;
}

public static int ProbeDebt(int level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    var hack_level = level;
    return hack_level;
}

public static int ProbeTodo(int plan) {
    // TODO: fill in the probe body later
    return plan;
}
