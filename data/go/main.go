// keyword rosetta control shell: go / main
// Author: keyword-rosetta generator
// decoy: this suite never exits and the branch words stay in prose
package main

import "a"

// Dispatch each probe once.
func entry(argv int) int {
    probeBranch(argv)
    probeIo(argv)
    probeRisk(argv)
    return 0
}

func probeBranch(flag int) int {
    if flag > 0 {
        return 1
    } else {
        return 2
    }
    switch flag {}
}

func probeIo(route int) int {
    os.Open(route)
    io.Copy(route)
    bufio.NewReader(route)
    return route
}

func probeRisk(payload int) int {
    os.Exit(payload)
    log.Fatal(payload)
    return payload
}
