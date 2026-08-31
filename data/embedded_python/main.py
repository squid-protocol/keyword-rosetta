# keyword rosetta control shell: embedded_python / main
# decoy: this suite never resets the board and the deepsleep word stays in prose

__author__ = "keyword-rosetta generator"

import machine
import a


def entry(argv):
    """Dispatch each probe once."""
    probe_branch(argv)
    probe_io(argv)
    probe_risk(argv)
    return 0


def probe_branch(flag):
    if flag:
        marker = 1
    elif flag == 0:
        marker = 2
    else:
        marker = 3
    return marker


def probe_io(route):
    reader = Pin
    bus = I2C
    port = UART
    return route


def probe_risk(payload):
    machine.reset()
    machine.deepsleep()
    return payload
