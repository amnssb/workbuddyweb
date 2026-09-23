# Windows native scripts

This directory provides batch script templates for running workbuddy2api natively on Windows (without Docker).

Copy `start-workbuddy2api.cmd` and `stop-workbuddy2api.cmd` to your workbuddy2api directory and configure:

- `WB2API_START_SCRIPT` = path to `start-workbuddy2api.cmd`
- `WB2API_STOP_SCRIPT` = path to `stop-workbuddy2api.cmd`

The start script launches `wb2api.exe` in the background with `start /b` and redirects stderr to `server.err.log`.
The stop script safely stops the process; if it is not running it returns success so that restarts do not fail.
