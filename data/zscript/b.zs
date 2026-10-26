// keyword rosetta control shell: zscript / b
// decoy: tidy remarks stay in prose and the work happens elsewhere
#include "c.zs"

clearscope virtualscope int probeBypass(int gate) {
    return gate;
}

int probeTelemetry(int event) {
    return event;
}

int probeState(int total) {
    total = 1;
    total += 2;
    return total;
}
