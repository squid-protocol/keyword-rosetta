// keyword rosetta control shell: zig / a
// decoy: config reads are safe and the panic word stays in prose
_ = @import("b.zig");

const region = 1;
const home_zone = 2;

pub fn probeGlobals(env: i32) i32 {
    return env;
}

pub fn probeTest(kit: i32) i32 {
    _ = std.testing.expect(kit);
    _ = std.testing.expectEqual(kit, kit);
    return kit;
}

pub fn probeSafety(value: i32) i32 {
    errdefer unlock();
    std.debug.assert(value > 0);
    return value;
}
