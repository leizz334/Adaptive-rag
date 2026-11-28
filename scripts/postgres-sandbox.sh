#!/usr/bin/env bash
# Unprivileged Ubuntu/WSL PostgreSQL with temporary binaries, data and socket.
set -euo pipefail

pg_major=16
pg_release=16.15-0ubuntu0.24.04.1
database=adaptive_rag_final_engineering
role=adaptive_rag_final
cluster=adaptive_rag_final_engineering

load_paths() {
    pg_bin="$scratch/toolchain/usr/lib/postgresql/$pg_major/bin"
    export LD_LIBRARY_PATH="$scratch/toolchain/usr/lib/x86_64-linux-gnu"
}

remove_sandbox() {
    local resolved
    resolved=$(realpath -e -- "$scratch")
    [[ "$resolved" =~ ^/tmp/adaptive-rag-final-pg\.[[:alnum:]]{8}$ && -O "$resolved" ]]
    rm -rf -- "$resolved"
}

case ${1:-} in
    start)
        port=${2:?choose an unused loopback port}
        [[ "$port" =~ ^[0-9]{4,5}$ && "$port" -ge 1024 && "$port" -le 65535 ]]
        scratch=$(mktemp -d /tmp/adaptive-rag-final-pg.XXXXXXXX)
        trap remove_sandbox EXIT
        for package in postgresql-16 postgresql-client-16 libpq5; do
            metadata=$(apt-cache show "$package=$pg_release")
            filename=$(awk '$1 == "Filename:" { print $2; exit }' <<< "$metadata")
            checksum=$(awk '$1 == "SHA256:" { print $2; exit }' <<< "$metadata")
            [[ "$filename" == pool/* && "$checksum" =~ ^[a-f0-9]{64}$ ]]
            target="$scratch/$package.deb"
            curl --fail --silent --show-error --connect-timeout 15 --max-time 120 \
                "https://security.ubuntu.com/ubuntu/$filename" --output "$target" ||
                curl --fail --silent --show-error --connect-timeout 15 --max-time 120 \
                    "https://archive.ubuntu.com/ubuntu/$filename" --output "$target"
            sha256sum --check --status <<< "$checksum  $target"
            dpkg-deb -x "$target" "$scratch/toolchain"
        done
        load_paths
        "$pg_bin/initdb" -D "$scratch/data" -L "$scratch/toolchain/usr/share/postgresql/$pg_major" \
            --no-locale --encoding=UTF8 --auth=trust --username="$role" >&2
        "$pg_bin/pg_ctl" -D "$scratch/data" -l "$scratch/server.log" \
            -o "-h 127.0.0.1 -p $port -k $scratch -c cluster_name=$cluster" -w start >&2
        trap '"$pg_bin/pg_ctl" -D "$scratch/data" -m immediate -w stop >&2; remove_sandbox' EXIT
        "$pg_bin/createdb" -h "$scratch" -p "$port" -U "$role" "$database"
        printf '%s\n' "$port" > "$scratch/port"
        trap - EXIT
        printf '%s\n' "$scratch"
        ;;
    psql|stop)
        scratch=$(realpath -e -- "${2:?provide the sandbox path returned by start}")
        [[ "$scratch" =~ ^/tmp/adaptive-rag-final-pg\.[[:alnum:]]{8}$ && -O "$scratch" ]]
        load_paths
        if [[ "$1" == psql ]]; then
            shift 2
            exec "$pg_bin/psql" -X --set ON_ERROR_STOP=1 -h "$scratch" \
                -p "$(cat "$scratch/port")" -U "$role" -d "$database" "$@"
        fi
        "$pg_bin/pg_ctl" -D "$scratch/data" -m fast -w stop >&2
        remove_sandbox
        ;;
    *)
        printf 'Usage: %s start PORT | psql SANDBOX [ARG ...] | stop SANDBOX\n' "$0" >&2
        exit 2
        ;;
esac
