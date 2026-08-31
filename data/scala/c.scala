// keyword rosetta control shell: scala / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

def probeCleanup(conn: Int): Int = {
  close(conn)
  dispose(conn)
  conn
}

def probeDebt(level: Int): Int = {
  // HACK: shortcut kept deliberately for the rosetta corpus
  val hackLevel = level
  hackLevel
}

def probeTodo(plan: Int): Int = {
  // TODO: fill in the probe body later
  plan
}
