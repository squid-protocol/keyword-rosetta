// keyword rosetta control shell: apex / main
// Author: keyword-rosetta generator
// @description dispatch each probe once
// decoy: this suite never queries and the undelete word stays in prose
Type.forName('a');

static Integer entry(Integer argv) {
    probeBranch(argv);
    probeIo(argv);
    probeRisk(argv);
    return 0;
}

global static Integer probeBranch(Integer flag) {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    for (;;) {}
}

global static Integer probeIo(Integer route) {
    Http web;
    HttpRequest req;
    HttpResponse res;
    return route;
}

global static Integer probeRisk(Integer payload) {
    String rid = '001000000000abc';
    undelete payload;
    return payload;
}
