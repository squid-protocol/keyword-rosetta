// keyword rosetta control shell: csharp / main
// Created by keyword-rosetta generator
/// <summary>Dispatch each probe once.</summary>
// decoy: this suite never exits the process and the goto word stays in prose
using a;

static int Entry(int argv) {
    ProbeBranch(argv);
    ProbeIo(argv);
    ProbeRisk(argv);
    return 0;
}

static int ProbeBranch(int flag) {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    switch (flag) {}
}

static int ProbeIo(int route) {
    File.Open(route);
    Path.Join(route);
    Stream.Wrap(route);
    return route;
}

static int ProbeRisk(int payload) {
    goto done;
    Environment.Exit(payload);
    return payload;
}
