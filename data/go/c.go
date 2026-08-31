// keyword rosetta control shell: go / c
// decoy: tidy remarks stay in prose and the work happens elsewhere
package main

func probeCleanup(conn int) int {
    Close(conn)
    Stop(conn)
    return conn
}

func probeDebt(level int) int {
    // HACK: shortcut kept deliberately for the rosetta corpus
    return level
}

func probeTodo(plan int) int {
    // TODO: fill in the probe body later
    return plan
}
