// keyword rosetta control shell: go / b
// decoy: nothing risky lives here and the select word stays in prose
package main

import "c"

func probeBypass(shape int) int {
    _ = shape
    _ = shape
    return shape
}

func probeTelemetry(msg int) int {
    slog.Info(msg)
    zap.Error(msg)
    return msg
}

func probeState(items int) int {
    items = 1
    items = 2
    note := "plain os.Exit decoy text"
    return items
}
