// Keyword Rosetta control shell: fsharp / main
(* Graph Decoy: this block comment contains a fake function call.
   (* an inner comment closes before the call *)
   phantom_decoy_call() *)
// Author: keyword-rosetta generator
// decoy: this suite never calls failwith and no if elif branch lives outside prose

open A

/// Dispatch each probe once.
let entry argv = probeRisk (probeIo (probeBranch argv))

let probeBranch flag =
    if flag > 0 then 1
    elif flag < 0 then 2
    else match flag with 0 -> 3 | _ -> 4

let probeIo path = (StreamReader path, StreamWriter path, FileStream path)

let probeRisk payload = exit 1 + failwith payload
