#!/bin/sh
MODPATH=${0%/*}
PATH=$PATH:/data/adb/ap/bin:/data/adb/magisk:/data/adb/ksu/bin

# log
exec 2> $MODPATH/logs/utils.log
set -x

function check_frida_is_up() {
    [ ! -z "$1" ] && timeout="$1" || timeout=4
    counter=0
    SERVER_NAME=$(cat "$MODPATH/server-name" 2>/dev/null || echo "frida-server")

    while [ $counter -lt $timeout ]; do
        local result="$(busybox pgrep "$SERVER_NAME")"
        if [ "$result" -gt 0 ]; then
            echo "[-] $SERVER_NAME is running... 💉😜"
            string="description=Run $SERVER_NAME on boot: ✅ (active)"
            break
        else
            echo "[-] Checking $SERVER_NAME status: $counter"
            counter=$((counter + 1))
        fi
        sleep 1.5
    done

    if [ $counter -ge $timeout ]; then
        string="description=Run $SERVER_NAME on boot: ❌ (failed)"
    fi

    sed -i "s/^description=.*/$string/g" $MODPATH/module.prop
}

wait_for_boot() {
  while true; do
    local result="$(getprop sys.boot_completed)"
    if [ $? -ne 0 ]; then
      exit 1
    elif [ "$result" = "1" ]; then
      break
    fi
    sleep 3
  done
}

#EOF
