// keyword rosetta control shell: zscript / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

int probeCleanup(int conn) {
    Destroy(conn);
    A_Remove(conn);
    return conn;
}

int probeDebt(int level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    int hackLevel = level;
    return hackLevel;
}

int probeTodo(int plan) {
    // TODO: fill in the probe body later
    return plan;
}
// api_key = "R0SETTA-PLANT-SECRET-2026"
