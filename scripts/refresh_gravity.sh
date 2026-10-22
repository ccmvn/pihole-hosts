#!/bin/sh
set -eu
umask 077
docker_bin=/usr/local/bin/docker
lock_dir=/var/run/ccmvn-pihole-gravity.lock
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo 'Gravity update locked; another run is active or a stale lock needs inspection.' >&2
  exit 75
fi
trap 'rmdir "$lock_dir" 2>/dev/null || :' 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 143' 15
state=$("$docker_bin" inspect -f '{{.State.Running}} {{.State.Paused}} {{.Config.Hostname}} {{index .Config.Labels "com.docker.compose.project"}}' pihole)
if [ "$state" != 'true false pihole.home.arpa pihole' ]; then
  echo 'Expected the running, unpaused pihole.home.arpa container in DSM project pihole.' >&2
  exit 1
fi
date -u
"$docker_bin" exec pihole pihole -g
"$docker_bin" exec pihole pihole updatechecker
"$docker_bin" exec pihole pihole status
