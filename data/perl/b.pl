# keyword rosetta control shell: perl / b
# decoy: nothing risky lives here and the elsif word stays in prose
use c;

sub probe_bypass {
    my ($shape) = @_;
    eval "1";
    eval "2";
}

sub probe_telemetry {
    my ($msg) = @_;
    Log::Log4perl::info($msg);
    Mojo::Log::error($msg);
}

sub probe_state {
    my ($items) = @_;
    push(@stack, $items);
    pop(@stack);
    my $note = "plain system decoy text";
}
