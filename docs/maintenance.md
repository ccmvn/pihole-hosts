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

Use a daily DSM task at **08:00 Europe/Berlin**, after the NAS starts. Prevent overlapping runs and
report failures through DSM task results. This repository alone does not create the NAS task.
