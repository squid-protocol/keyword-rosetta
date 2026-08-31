# keyword rosetta control shell: perl / a
# decoy: config reads are safe and the system word stays in prose
use b;

sub probe_globals {
    my ($env) = @_;
    return @ARGV, @INC, $env;
}

sub probe_test {
    my ($kit) = @_;
    Test::More::ok($kit);
    subtest($kit);
}

sub probe_safety {
    my ($value) = @_;
    croak($value);
    confess($value);
}
