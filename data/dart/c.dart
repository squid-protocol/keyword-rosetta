// keyword rosetta control shell: dart / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

int probeCleanup(int conn) {
  dispose(conn);
  close(conn);
  return conn;
}

int probeDebt(int level) {
  // HACK: shortcut kept deliberately for the rosetta corpus
  final hackLevel = level;
  return hackLevel;
}

int probeTodo(int plan) {
  // TODO: fill in the probe body later
  return plan;
}
