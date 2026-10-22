#!/usr/bin/env python3
"""Generate the hosts file from a pinned StevenBlack commit; standard library only."""

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REF_URL = "https://api.github.com/repos/StevenBlack/hosts/git/ref/heads/master"
DOMAIN = re.compile(r"(?=.{1,253}\Z)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\Z")
# DNS blocklists also contain underscore labels; preserve these upstream records.
HOST_NAME = re.compile(r"(?=.{1,253}\Z)[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?(?:\.[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?)*\Z")
MIN_DOMAINS = 50_000
MAX_DOWNLOAD = 32 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_exceptions(path):
    domains = []
    for line in path.read_text(encoding="utf-8").splitlines():
        domain = line.partition("#")[0].strip()
        if not domain:
            continue
        if "." not in domain or not DOMAIN.fullmatch(domain):
            raise ValueError(f"Invalid exact exception: {domain!r}")
        if domain in domains:
            raise ValueError(f"Duplicate exception: {domain}")
        domains.append(domain)
    if not domains:
        raise ValueError("Exception list must not be empty")
    return domains


def records(text):
    for number, line in enumerate(text.splitlines(), 1):
        entry = line.partition("#")[0].split()
        if not entry:
            continue
        if len(entry) < 2:
            raise ValueError(f"Hosts line {number}: expected an IP and hostname")
        try:
            address = ipaddress.ip_address(entry[0])
        except ValueError as error:
            raise ValueError(f"Hosts line {number}: invalid IP address") from error
        for domain in entry[1:]:
            if not HOST_NAME.fullmatch(domain.lower()):
                raise ValueError(f"Hosts line {number}: invalid hostname {domain!r}")
        yield line, address, entry[1:]


def blocked_domains(text):
    domains = set()
    for _, address, names in records(text):
        if address.is_unspecified or address.is_loopback:
            for name in names:
                name = name.lower()
                try:
                    ipaddress.ip_address(name)
                except ValueError:
                    if "." in name:
                        domains.add(name)
    return domains


def generate(text, exceptions):
    # Validate the complete input before generating anything.
    list(records(text))
    allowed = set(exceptions)
    result = []
    for line in text.splitlines():
        content, separator, comment = line.partition("#")
        fields = content.split()
        if not fields:
            result.append(line)
            continue
        excluded = [name for name in fields[1:] if name.lower() in allowed]
        if not excluded:
            result.append(line)
            continue
        remaining = [name for name in fields[1:] if name.lower() not in allowed]
        if remaining:
            result.append(" ".join([fields[0], *remaining]) + (f" # {comment}" if separator else ""))
            result.extend(f"# {fields[0]} {name} # allowed by exceptions.txt" for name in excluded)
        else:
            result.append("# " + line)
    output = "\n".join(result) + "\n"
    validate_size(output)
    if blocked_domains(output) & allowed:
        raise ValueError("An exception is still present as an active blocking entry")
    return output


def validate_size(text, previous=None, minimum=MIN_DOMAINS):
    count = len(blocked_domains(text))
    if count < minimum:
        raise ValueError(f"Only {count} blocked domains; minimum is {minimum}")
    if previous:
        old_count = len(blocked_domains(previous))
        if old_count and not old_count * 0.8 <= count <= old_count * 1.5:
            raise ValueError(f"Suspicious domain count change: {old_count} -> {count}; review upstream manually")
    return count


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "ccmvn-pihole-hosts-generator", "Accept": "application/vnd.github+json" if url.startswith("https://api.github.com/") else "text/plain"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("Download exceeds the 32 MiB limit")
    return data


def update_section(readme, name, content):
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    if readme.count(start) != 1 or readme.count(end) != 1:
        raise ValueError(f"README must contain exactly one {name} marker pair")
    before, rest = readme.split(start)
    _, after = rest.split(end)
    return f"{before}{start}\n{content}\n{end}{after}"


def render_readme(readme, exceptions, metadata):
    readme = update_section(readme, "exceptions", "\n".join(f"- `{domain}`" for domain in exceptions))
    commit = metadata["upstream_commit"]
    details = (f"- Upstream: [`{commit[:7]}`](https://github.com/StevenBlack/hosts/commit/{commit})\n"
               f"- Blocked domains: {metadata['blocked_domains']:,}; checksums in [source.json](source.json).")
    return update_section(readme, "source", details)


def write_changed(path, data):
    if path.exists() and path.read_bytes() == data:
        return
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def check(root, exceptions):
    hosts = (root / "hosts").read_bytes()
    metadata = json.loads((root / "source.json").read_text(encoding="utf-8"))
    text = hosts.decode("utf-8")
    count = validate_size(text)
    if blocked_domains(text) & set(exceptions):
        raise ValueError("An exception is actively blocked")
    if metadata["schema"] != 1 or metadata["exceptions"] != exceptions:
        raise ValueError("Provenance does not match exceptions.txt")
    if metadata["generated_sha256"] != digest(hosts) or metadata["blocked_domains"] != count:
        raise ValueError("hosts does not match source.json")
    if not re.fullmatch(r"[0-9a-f]{40}", metadata["upstream_commit"]):
        raise ValueError("Invalid upstream commit")
    if not re.fullmatch(r"[0-9a-f]{64}", metadata["upstream_sha256"]):
        raise ValueError("Invalid upstream checksum")
    readme = (root / "README.md").read_text(encoding="utf-8")
    if render_readme(readme, exceptions, metadata) != readme:
        raise ValueError("Generated README sections are out of date")
    print(f"OK: {count:,} blocked domains; {len(exceptions)} exact exceptions")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate checked-in files without network access or writes")
    parser.add_argument("--source", type=Path, help="Use a previously downloaded upstream file")
    parser.add_argument("--upstream-commit", help="Full upstream commit SHA (required with --source)")
    parser.add_argument("--accept-size-change", action="store_true", help="Accept a reviewed size change for an explicitly pinned commit; all other checks remain enabled")
    args = parser.parse_args()
    exceptions = load_exceptions(ROOT / "exceptions.txt")
    if args.check:
        if args.source or args.upstream_commit or args.accept_size_change:
            parser.error("--check cannot be combined with source options")
        check(ROOT, exceptions)
        return
    if args.source and not args.upstream_commit:
        parser.error("--source requires --upstream-commit for provenance")
    if args.accept_size_change and not args.upstream_commit:
        parser.error("--accept-size-change requires an explicitly reviewed --upstream-commit")
    commit = args.upstream_commit
    if not commit:
        commit = json.loads(fetch(REF_URL))["object"]["sha"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Upstream commit must be a full 40-character SHA")
    url = f"https://raw.githubusercontent.com/StevenBlack/hosts/{commit}/hosts"
    upstream = args.source.read_bytes() if args.source else fetch(url)
    output = generate(upstream.decode("utf-8"), exceptions)
    previous = (ROOT / "hosts").read_text(encoding="utf-8")
    count = validate_size(output, None if args.accept_size_change else previous)
    data = output.encode("utf-8")
    metadata = {"schema": 1, "upstream_repository": "https://github.com/StevenBlack/hosts", "upstream_commit": commit,
                "upstream_url": url, "upstream_sha256": digest(upstream), "generated_sha256": digest(data),
                "blocked_domains": count, "exceptions": exceptions}
    readme = render_readme((ROOT / "README.md").read_text(encoding="utf-8"), exceptions, metadata)
    # All downloads, parsing, safety checks and rendering finish before any file is replaced.
    write_changed(ROOT / "hosts", data)
    write_changed(ROOT / "source.json", (json.dumps(metadata, indent=2) + "\n").encode("utf-8"))
    write_changed(ROOT / "README.md", readme.encode("utf-8"))
    check(ROOT, exceptions)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        sys.exit(f"Update aborted; no new list should be published: {error}")
