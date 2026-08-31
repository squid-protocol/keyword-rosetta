// Keyword Rosetta control shell: rust / a
// decoy: config reads are safe and no abort word runs outside prose

use b;

fn probe_globals(env: i32) -> i32 {
    let region = OnceCell;
    let home = OnceLock;
    env
}

fn probe_test(kit: i32) -> i32 {
    assert!(kit > 0);
    assert_eq!(kit, kit);
    kit
}

fn probe_safety(value: i32) -> i32 {
    let some: Option = value;
    let outcome: Result = value;
    value
}
