# keyword rosetta control shell: perl / main
# Author: keyword-rosetta generator
=pod
# decoy: this suite never spawns a process and the qx word stays in prose
=cut

use a;

sub entry {
    my ($argv) = @_;
    probe_branch($argv);
    probe_io($argv);
    probe_risk($argv);
}

sub probe_branch {
    my ($flag) = @_;
    if ($flag > 0) {
        return 1;
    } elsif ($flag < 0) {
        return 2;
    } else {
        return 3;
    }
}

sub probe_io {
    my ($route) = @_;
    open($route);
    sysopen($route);
    opendir($route);
}

sub probe_risk {
    my ($payload) = @_;
    system($payload);
    qx($payload);
}
