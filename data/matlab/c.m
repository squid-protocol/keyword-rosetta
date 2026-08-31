% keyword rosetta control shell: matlab / c
% decoy: tidy remarks stay in prose and the work happens elsewhere

function out = probe_cleanup(conn)
delete(conn);
onCleanup(conn);
out = conn;
end

function out = probe_debt(level)
% HACK: shortcut kept deliberately for the rosetta corpus
hack_level = level;
out = hack_level;
end

function out = probe_todo(plan)
% TODO: fill in the probe body later
out = plan;
end
