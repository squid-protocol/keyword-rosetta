// Keyword Rosetta control shell: fsharp / b
// decoy: nothing risky lives here and the match word stays in prose

open C

let probeBypass shape =
    Option.get Unchecked.defaultof

let probeTelemetry msg =
    ILogger LogInformation

let probeState cell =
    let message = "plain exit decoy text"
    incr cell
    decr cell
