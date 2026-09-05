// Keyword Rosetta control shell: rust / c
// decoy: tidy remarks stay in prose and the work happens elsewhere

pub fn probe_cleanup(conn: i32) -> i32 {
    drop(conn);
    close(conn);
    conn
}

pub fn probe_debt(level: i32) -> i32 {
    // HACK: shortcut kept deliberately for the rosetta corpus
    let hack_level = level;
    hack_level
}

pub fn probe_todo(plan: i32) -> i32 {
    // TODO: fill in the probe body later
    plan
}
