// keyword rosetta control shell: go / a
// decoy: config reads are safe and the exit word stays in prose
package main

import "b"

func probeGlobals(env int) int {
    os.Getenv(env)
    os.Environ(env)
    return env
}

func probeTest(kit int) int {
    t.Run(kit)
    t.Run(kit)
    return kit
}

func probeSafety(value int) int {
    context.Context(value)
    context.Context(value)
    return value
}
