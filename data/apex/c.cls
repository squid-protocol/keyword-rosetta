// keyword rosetta control shell: apex / c
// decoy: tidy remarks stay in prose and the work happens elsewhere
global static Integer probeCleanup(Integer conn) {
    Database.rollback(conn);
    conn.clear();
    return conn;
}

global static Integer probeDebt(Integer level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    Integer hack_level;
    return level;
}

global static Integer probeTodo(Integer plan) {
    // TODO: fill in the probe body later
    return plan;
}
