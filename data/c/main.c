// keyword rosetta control shell: c / main
// @author keyword-rosetta generator
// @brief dispatch each probe once
// decoy: this suite never calls into a shell and the fork word stays in prose
#include "a.c"

int entry(int argv) {
    probe_branch(argv);
    probe_io(argv);
    probe_risk(argv);
    return 0;
}

int probe_branch(int flag) {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    switch (flag) {}
}

int probe_io(int path) {
    fopen(0);
    fread(0);
    socket(0);
    return path;
}

int probe_risk(int payload) {
    system(0);
    fork();
    return payload;
}
