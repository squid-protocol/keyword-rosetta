// SPDX-License-Identifier: MIT
// keyword rosetta control shell: solidity / a
// decoy: config reads are safe outside prose
import "b.sol";

function probeGlobals(uint env) returns (uint) {
    msg.sender;
    block.number;
    return env;
}

function probeTest(uint kit) returns (uint) {
    assertEq(kit, kit);
    setUp();
    return kit;
}

function probeSafety(uint value) returns (uint) {
    require(value > 0);
    nonReentrant;
    return value;
}
