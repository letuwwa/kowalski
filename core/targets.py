"""Normalize submitted targets and resolve a fixed IPv4 destination snapshot."""

import asyncio
import re
from ipaddress import IPv4Address

import dns.asyncresolver
import dns.exception
import dns.resolver


class TargetResolutionError(ValueError):
    """An expected DNS failure, distinct from a TCP port observation."""


def normalize_target(value: object) -> str:
    """Return a canonical IPv4 address or lower-case ASCII/IDNA hostname."""
    if not isinstance(value, str) or not value:
        raise ValueError("Target must be an IPv4 address or hostname")
    value = value.strip()
    try:
        return str(IPv4Address(value))
    except ValueError:
        pass
    if not value or re.fullmatch(r"[0-9.]+", value):
        raise ValueError("Invalid IPv4 address or hostname")
    value = value.removesuffix(".")
    try:
        hostname = value.encode("idna").decode("ascii").lower()
        # The stdlib IDNA codec can map distinct names (e.g. ß to ss). Do not
        # silently scan a different name; callers can supply ASCII punycode.
        if (
            not value.isascii()
            and hostname.encode("ascii").decode("idna").lower() != value.lower()
        ):
            raise ValueError("Use the ASCII punycode form for this hostname")
    except UnicodeError as error:
        raise ValueError("Invalid hostname") from error
    if len(hostname) > 253 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in hostname.split(".")
    ):
        raise ValueError("Target must be an IPv4 address or hostname, not a URL")
    return hostname


async def resolve_ipv4(target: str) -> tuple[str, ...]:
    """Resolve once, without search suffixes; never return more than eight IPs.

    Only A records are requested. Cancellation propagates to dnspython's async
    network operations. A failed lookup makes no TCP connection attempts.
    """
    target = normalize_target(target)
    try:
        return (str(IPv4Address(target)),)
    except ValueError:
        pass
    try:
        async with asyncio.timeout(5):
            answer = await dns.asyncresolver.resolve(
                target + ".", "A", search=False, lifetime=5
            )
        addresses = tuple(
            sorted({str(IPv4Address(row.address)) for row in answer}, key=IPv4Address)
        )
    except (TimeoutError, dns.exception.Timeout) as error:
        raise TargetResolutionError(f"DNS resolution timed out for {target}") from error
    except dns.resolver.NXDOMAIN as error:
        raise TargetResolutionError(f"Hostname does not exist: {target}") from error
    except dns.resolver.NoAnswer as error:
        raise TargetResolutionError(f"No IPv4 addresses found for {target}") from error
    except (dns.exception.DNSException, OSError, ValueError) as error:
        raise TargetResolutionError(f"DNS resolution failed for {target}") from error
    if not addresses:
        raise TargetResolutionError(f"No IPv4 addresses found for {target}")
    if len(addresses) > 8:
        raise TargetResolutionError(
            f"DNS returned more than 8 IPv4 addresses for {target}"
        )
    return addresses
