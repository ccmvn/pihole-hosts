# Pi-hole hosts

[StevenBlack's hosts list](https://github.com/StevenBlack/hosts), with five exact exceptions for Google Shopping Ads.

## Use

Add this blocklist in Pi-hole and update Gravity (`pihole -g`):

```text
https://raw.githubusercontent.com/ccmvn/pihole-hosts/master/hosts
```

Keep the direct StevenBlack list disabled. Other enabled lists may still block these domains;
exceptions in this file are not global Pi-hole allow rules.

## Exceptions

Maintained in [exceptions.txt](exceptions.txt); this section is generated automatically.

<!-- exceptions:start -->
- `ad.doubleclick.net`
- `googleadservices.com`
- `www.googleadservices.com`
- `googleads.g.doubleclick.net`
- `googleads4.g.doubleclick.net`
<!-- exceptions:end -->

## Updates

GitHub Actions checks daily at **04:17 UTC** and publishes validated changes automatically.
Manual updates: **Actions → Validate and update hosts → Run workflow**.

For local changes (Python 3.10+, no dependencies):

```sh
python3 scripts/update_hosts.py
python3 scripts/update_hosts.py --check
python3 -m unittest discover -s tests
```

See [maintenance](docs/maintenance.md) for safety checks, recovery and Synology scheduling.

## Source

<!-- source:start -->
- Upstream: [`8f49f2d`](https://github.com/StevenBlack/hosts/commit/8f49f2d0be468eb817dbc51313bf11df6052d9c6)
- Blocked domains: 76,143; checksums in [source.json](source.json).
<!-- source:end -->

Upstream credits and license notices are preserved in `hosts`. Modifications by ccmvn.
