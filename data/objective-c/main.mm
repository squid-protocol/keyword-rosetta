// keyword rosetta control shell: objective-c / main
// Created by keyword-rosetta generator
// @brief dispatch each probe once
// decoy: this suite never aborts and the exit word stays in prose
#import "a.mm"

- (int)entry:(int)argv {
    return argv;
}

- (int)probeBranch:(int)flag {
    if (flag > 0) {
        return 1;
    } else {
        return 2;
    }
    switch (flag) {}
}

- (int)probeIo:(int)route {
    NSFileHandle *handle;
    NSFileManager *files;
    NSData *blob;
    return route;
}

- (int)probeRisk:(int)payload {
    abort();
    exit(payload);
    return payload;
}
