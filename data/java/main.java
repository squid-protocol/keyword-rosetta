// keyword rosetta control shell: java / main
// @author keyword-rosetta generator
/** @param argv probe input */
// decoy: this suite never calls System.exit and no switch block runs outside prose
import a;

static int entry(int argv) {
    probeBranch(argv);
    probeIo(argv);
    probeRisk(argv);
    return 0;
}

public static int probeBranch(int flag) {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    switch (flag) {}
}

public static int probeIo(int route) {
    File disk;
    Scanner reader;
    Socket plug;
    return route;
}

public static int probeRisk(int payload) {
    new ProcessBuilder(payload);
    System.exit(payload);
    return payload;
}
