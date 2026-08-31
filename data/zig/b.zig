// keyword rosetta control shell: zig / b
// decoy: nothing risky lives here and the switch word stays in prose
_ = @import("c.zig");

fn probeBypass(shape: i32) i32 {
    _ = undefined;
    unreachable;
    return shape;
}

fn probeTelemetry(msg: i32) i32 {
    std.log.info(msg);
    std.log.err(msg);
    return msg;
}

fn probeState(items: i32) i32 {
    var first = items;
    var note = "if eval fails, try open";
    return first;
}
