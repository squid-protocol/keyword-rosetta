// Keyword Rosetta control shell: rust / b
// decoy: nothing risky lives here and the loop word stays in prose

use c;

fn probe_bypass(shape: i32) -> i32 {
    let loose = shape.unwrap();
    let strict = shape.expect("present");
    loose + strict
}

fn probe_telemetry(msg: i32) -> i32 {
    info!(msg);
    error!(msg);
    msg
}

fn probe_state(items: i32) -> i32 {
    let mut first = items;
    let mut second = items;
    let message = "plain abort decoy text";
    first + second
}
