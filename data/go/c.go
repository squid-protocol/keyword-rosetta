// keyword rosetta control shell: go / c
// decoy: tidy remarks stay in prose and the work happens elsewhere
package main

func ProbeCleanup(conn int) int {
    Close(conn)
    Stop(conn)
    return conn
}

func ProbeDebt(level int) int {
    // HACK: shortcut kept deliberately for the rosetta corpus
    return level
}

func ProbeTodo(plan int) int {
    // TODO: fill in the probe body later
    return plan
}
