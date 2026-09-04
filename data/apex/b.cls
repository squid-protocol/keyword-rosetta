// keyword rosetta control shell: apex / b
// decoy: nothing risky lives here and the merge word stays in prose
Type.forName('c');

@SuppressWarnings('rosetta')
global static Integer probeBypass(Integer shape) {
    return shape;
}

@SuppressWarnings('rosetta')
global static Integer probeTelemetry(Integer msg) {
    Logger.info(msg);
    Log.error(msg);
    return msg;
}

global static Integer probeState(Integer items) {
    insert items;
    update items;
    String note = 'plain emptyRecycleBin decoy text';
    return items;
}
