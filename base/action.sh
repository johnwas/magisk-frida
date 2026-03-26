#!/system/bin/sh
MODPATH=${0%/*}
PATH=$PATH:/data/adb/ap/bin:/data/adb/magisk:/data/adb/ksu/bin

# log
exec 2> $MODPATH/logs/action.log
set -x

. $MODPATH/utils.sh

SERVER_NAME=$(cat "$MODPATH/server-name" 2>/dev/null || echo "frida-server")

[ -f $MODPATH/disable ] && {
    echo "[-] $SERVER_NAME is disabled"
    string="description=Run $SERVER_NAME on boot: ❌ (failed)"
    sed -i "s/^description=.*/$string/g" $MODPATH/module.prop
    sleep 1
    exit 0
}

result="$(busybox pgrep "$SERVER_NAME")"
if [ "$result" -gt 0 ]; then
    echo "[-] Stopping $SERVER_NAME..."
    busybox kill -9 "$result"
else
    echo "[-] Starting $SERVER_NAME..."
    "$SERVER_NAME" -D
fi

sleep 1

check_frida_is_up 1

#EOF
