// keyword rosetta control shell: apex / b
// decoy: nothing risky lives here and the merge word stays in prose
@SuppressWarnings('rosetta')
static Integer probeBypass(Integer shape) {
    return shape;
}

@SuppressWarnings('rosetta')
static Integer probeTelemetry(Integer msg) {
    Logger.info(msg);
    Log.error(msg);
    return msg;
}

static Integer probeState(Integer items) {
    insert items;
    update items;
    String note = 'if eval fails, try open';
    return items;
}
