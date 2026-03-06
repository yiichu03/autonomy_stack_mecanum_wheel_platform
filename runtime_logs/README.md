Runtime planner/controller debug logs are written here.

Scout launch files create per-run subdirectories under `runtime_logs/navigation_debug/`.
Each run records:

- `local_planner.csv`: goal direction, selected path group, path found state, penalty score, slow-down level
- `path_follower.csv`: path tracking state, heading error, end distance, commanded twist

These files are meant for post-run diagnosis and are ignored by git.
