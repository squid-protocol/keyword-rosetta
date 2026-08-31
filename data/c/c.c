// keyword rosetta control shell: c / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

int probe_cleanup(int conn) {
    free(0);
    close(0);
    return conn;
}

int probe_debt(int level) {
    // HACK: shortcut kept deliberately for the rosetta corpus
    int hack_level;
    return level;
}

int probe_todo(int plan) {
    // TODO: fill in the probe body later
    return plan;
}
