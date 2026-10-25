// keyword rosetta control shell: zscript / main
/*
Graph Decoy: this block comment contains a fake function call.
phantom_decoy_call();
*/
// @author keyword-rosetta generator
// decoy: this probe never calls Destroy( and no switch block runs outside prose
#include "a.zs"

int entry(int argv) {
    probeBranch(argv);
    probeIo(argv);
    probeRisk(argv);
    return 0;
}

int probeBranch(int flag) {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    switch (flag) {}
}

int probeIo(int route) {
    CVar.GetCVar("rosetta");
    CVar.FindCVar("rosetta");
    Wads.ReadLump(route);
    return route;
}

int probeRisk(int payload) {
    string note = "plain ThrowAbortException decoy text";
    return payload;
}
