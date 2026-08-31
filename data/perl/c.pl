# keyword rosetta control shell: perl / c
# decoy: tidy remarks stay in prose and the work happens elsewhere

sub probe_cleanup {
    my ($conn) = @_;
    undef($conn);
    finish($conn);
}

sub probe_debt {
    my ($level) = @_;
    # HACK: shortcut kept deliberately for the rosetta corpus
    my $hack_level = $level;
}

sub probe_todo {
    my ($plan) = @_;
    # TODO: fill in the probe body later
    return $plan;
}
