# Maintenance

## Generation and provenance

The generator resolves StevenBlack's default branch to a full commit SHA before fetching the file.
It preserves upstream comments and credits and comments out exact exceptions case-insensitively;
other aliases on the same line and subdomains remain unchanged.

`source.json` records the upstream commit, source and output SHA-256 checksums, exception list and
domain count. Generated files are deterministic; unchanged files are not rewritten.

For a previously downloaded source, provide its original commit:

```sh
python3 scripts/update_hosts.py --source /path/to/upstream-hosts --upstream-commit FULL_40_CHARACTER_SHA
```

## Safety checks

Updates reject malformed records, invalid or duplicate exceptions, downloads over 32 MiB, fewer
than 50,000 blocked domains, drops exceeding 20%, and growth exceeding 50% versus the previous list.
All validation finishes before files are replaced. Failed workflow runs do not publish changes.

If a size guard triggers, review the upstream changes first. For an intentional change, pin the
reviewed commit explicitly:

```sh
python3 scripts/update_hosts.py --upstream-commit FULL_40_CHARACTER_SHA --accept-size-change
```

This bypasses only the relative size comparison. The scheduled workflow never uses this override.
Other checks remain enabled. A previous published state can be restored with Git revert.

## GitHub Actions

Pushes and pull requests run validation. Scheduled and manual runs also regenerate the list and
commit changed generated files. Only the update job receives contents write access; no personal
access token or NAS credentials are needed. Branch rules must allow the Actions bot to push.

Schedules run from the default branch and can be delayed. GitHub can disable scheduled workflows
in inactive public repositories. Check the Actions page if updates become stale, and enable failure
notifications in your GitHub notification settings.

## Synology / Pi-hole

Publishing the file does not refresh Pi-hole's Gravity database. For the container named `pihole`:

```sh
/usr/local/bin/docker exec pihole pihole -g
```

The DSM task **Pi-hole Gravity daily** runs daily at **08:00 Europe/Berlin**, after the NAS starts.
Its script is versioned in [scripts/refresh_gravity.sh](../scripts/refresh_gravity.sh): copy that
script into a scheduled user-defined task running as root. It checks the running container and
DSM project, prevents overlapping copies of this task, updates Gravity and refreshes the version
cache with `pihole updatechecker`. This does not upgrade Pi-hole.

Check failures in DSM task results. A lock left by an unclean termination causes exit 75; inspect
active tasks before removing the empty `/var/run/ccmvn-pihole-gravity.lock` directory. Changes to
the repository script must also be applied to the DSM task; the NAS does not download root scripts.
This repository alone does not create the NAS task.
