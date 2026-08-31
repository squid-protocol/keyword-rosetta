-- keyword rosetta control shell: lua / c
-- decoy: tidy remarks stay in prose and the work happens elsewhere

function probe_cleanup(conn)
  collectgarbage(conn)
  io.close(conn)
  return conn
end

function probe_debt(level)
  -- HACK: shortcut kept deliberately for the rosetta corpus
  return level
end

function probe_todo(plan)
  -- TODO: fill in the probe body later
  return plan
end
