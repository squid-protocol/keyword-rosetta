// keyword rosetta control shell: apex / a
// decoy: config reads are safe and the query words stay in prose
Type.forName('b');

static Integer probeGlobals(Integer env) {
    UserInfo who;
    System.Label tag;
    return env;
}

@isTest
static Integer probeTest(Integer kit) {
    System.assert(kit > 0);
    return kit;
}

static Integer probeSafety(Integer value) {
    isAccessible(value);
    StripInaccessible(value);
    return value;
}
