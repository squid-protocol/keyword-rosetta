// keyword rosetta control shell: typescript / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

export function probeCleanup(conn: number): number {
  conn.close();
  conn.dispose();
  return conn;
}

export function probeDebt(level: number): number {
  // HACK: shortcut kept deliberately for the rosetta corpus
  const HACK_LEVEL = level;
  return HACK_LEVEL;
}

export function probeTodo(plan: number): number {
  // TODO: fill in the probe body later
  return plan;
}
