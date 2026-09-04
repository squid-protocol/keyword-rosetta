// SPDX-License-Identifier: MIT
// keyword rosetta control shell: solidity / main
/// @param flag the probe input
// decoy: this suite never destroys itself outside prose
import "a.sol";

function entry(uint argv) returns (uint) {
    probeBranch(argv);
    probeIo(argv);
    probeRisk(argv);
    return 0;
}

function probeBranch(uint flag) public returns (uint) {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    for (;;) {}
}

function probeIo(uint route) public returns (uint) {
    return route;
}

function probeRisk(uint payload) public returns (uint) {
    selfdestruct(payload);
    selfdestruct(payload);
    return payload;
}
