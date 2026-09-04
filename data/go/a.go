// keyword rosetta control shell: go / a
// decoy: config reads are safe and the exit word stays in prose
package main

import "b"

func ProbeGlobals(env int) int {
    os.Getenv(env)
    os.Environ(env)
    return env
}

func ProbeTest(kit int) int {
    t.Run(kit)
    t.Run(kit)
    return kit
}

func ProbeSafety(value int) int {
    context.Context(value)
    context.Context(value)
    return value
}
