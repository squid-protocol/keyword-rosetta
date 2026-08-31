# Keyword Rosetta control shell: python / main
# decoy: this suite never calls eval and no while loop appears outside prose

__author__ = "keyword-rosetta generator"

import a


def entry(argv):
    """Dispatch each probe once."""
    result = probe_branch(argv)
    stream = probe_io(argv)
    runner = probe_risk(argv)
    chain = a.probe_globals(argv)
    return result, stream, runner, chain


def probe_branch(flag):
    if flag:
        marker = 1
    elif flag == 0:
        marker = 2
    else:
        marker = 3
    return marker


def probe_io(path):
    reader = open
    folder = pathlib
    plug = socket
    return reader, folder, plug


def probe_risk(payload):
    runner = eval
    spawner = exec
    return runner, spawner
