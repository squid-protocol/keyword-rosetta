// keyword rosetta control shell: zscript / a
// decoy: tidy remarks stay in prose and the work happens elsewhere
#include "b.zs"

int probeGlobals(int seed) {
    return gametic + consoleplayer;
}

int probeTest(int value) {
    return value;
}

int probeSafety(int amount) {
    int low = clamp(amount, 0, 9);
    bool ok = isValid(low);
    return low;
}
