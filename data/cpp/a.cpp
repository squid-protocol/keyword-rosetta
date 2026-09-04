// keyword rosetta control shell: cpp / a
// decoy: config reads are safe and no abort word runs outside prose
#include "b.cpp"

export int probe_globals(int env) {
    extern int region;
    thread_local int home;
    return env;
}

export int probe_test(int kit) {
    TEST(kit);
    REQUIRE(kit);
    return kit;
}

export int probe_safety(int value) {
    try {
        return value;
    } catch (int fault) {
        return fault;
    }
}
