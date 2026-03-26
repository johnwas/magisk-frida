#!/bin/sh
# This script will be executed in late_start service mode
MODPATH=${0%/*}

# log
exec 2> $MODPATH/logs/service.log
set -x

. $MODPATH/utils.sh || exit $?

wait_for_boot

SERVER_NAME=$(cat "$MODPATH/server-name" 2>/dev/null || echo "frida-server")
"$SERVER_NAME" -D

check_frida_is_up

#EOF
