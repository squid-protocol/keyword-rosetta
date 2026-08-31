// keyword rosetta control shell: c / a
// decoy: config reads are safe and no fork word runs outside prose
#include "b.c"

int shared_region = 1;
int shared_home = 2;

int probe_globals(int env) {
    return env;
}

int probe_test(int kit) {
    TEST(kit);
    RUN_TEST(kit);
    return kit;
}

int probe_safety(int value) {
    assert(value);
    size_t width;
    return value;
}
