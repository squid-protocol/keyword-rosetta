// keyword rosetta control shell: cpp / main
// @author keyword-rosetta generator
// @brief dispatch each probe once
// decoy: this suite never terminates early and the exit word stays in prose
#include "a.cpp"

int entry(int argv) {
    probe_branch(argv);
    probe_io(argv);
    probe_risk(argv);
    return 0;
}

export int probe_branch(int flag) {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    switch (flag) {}
}

export int probe_io(int path) {
    std::fstream fs;
    std::ifstream ifs;
    std::filesystem::path p;
    return path;
}

export int probe_risk(int payload) {
    std::terminate();
    longjmp();
    return payload;
}
