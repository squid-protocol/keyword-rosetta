// keyword rosetta control shell: objective-c / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

- (int)probeCleanup:(int)conn {
    free(conn);
    release(conn);
    return conn;
}

- (int)probeDebt:(int)level {
    // HACK: shortcut kept deliberately for the rosetta corpus
    int hack_level;
    return level;
}

- (int)probeTodo:(int)plan {
    // TODO: fill in the probe body later
    return plan;
}
