#!/usr/bin/env bash
# Copy the tests to the board, run them and keep the report on this PC.
#   run-on-board.sh <board-ip> [--disruptive] [--only GROUP]
set -euo pipefail
ip="${1:?usage: run-on-board.sh <board-ip> [test options]}"
shift
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
key="${OPI_KEY:-$HOME/.ssh/opi4pro_test}"
reports="${OPI_REPORTS:-$here/reports}"
ssh_opts=(-i "$key" -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)
report="$reports/$(date +%Y%m%d-%H%M%S).json"
mkdir -p "$reports"
scp "${ssh_opts[@]}" -q "$here/opi4pro_tests.py" "root@$ip:/root/opi4pro_tests.py"
rc=0
ssh "${ssh_opts[@]}" "root@$ip" python3 -I /root/opi4pro_tests.py --json /root/opi4pro-report.json "$@" || rc=$?
scp "${ssh_opts[@]}" -q "root@$ip:/root/opi4pro-report.json" "$report" && echo "report: $report"
exit "$rc"
