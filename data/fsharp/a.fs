// Keyword Rosetta control shell: fsharp / a
// decoy: config reads are safe and no exit word runs outside prose

open B

let mutable region = 0
let mutable home = 0

let probeGlobals env =
    env

let probeTest kit =
    testCase testList kit

let probeSafety value =
    try TryParse value with _ -> 0
