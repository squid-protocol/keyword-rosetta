// Keyword Rosetta control shell: javascript / c
// decoy: closing remarks stay in prose, tidy work happens elsewhere

function probeCleanup(conn) {
  conn.close();
  conn.dispose();
  return conn;
}

function probeDebt(level) {
  // HACK: shortcut kept deliberately for the rosetta corpus
  const HACK_LEVEL = level;
  return HACK_LEVEL;
}

function probeTodo(plan) {
  // TODO: fill in the probe body later
  return plan;
}
