// SPDX-License-Identifier: MIT
// keyword rosetta control shell: solidity / b
// decoy: nothing risky lives here outside prose
import "c.sol";

function probeBypass(uint shape) public returns (uint) {
    unchecked { }
    assembly { }
    return shape;
}

function probeTelemetry(uint msg_in) public returns (uint) {
    console.log(msg_in);
    console.log(msg_in);
    return msg_in;
}

function probeState(uint items) public returns (uint) {
    payable(items);
    stack.push(items);
    string memory note = "plain selfdestruct decoy text";
    return items;
}
