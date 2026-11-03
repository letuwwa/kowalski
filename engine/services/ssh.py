"""Bounded, receive-only SSH identification; no authentication or key exchange."""

import asyncio
import base64
import math
import re
import socket
from ipaddress import IPv4Address

from engine.report import ServiceObservation

MAX_BANNER_BYTES = 4096
# RFC 4253 section 4.2: printable ASCII version/software, no spaces or hyphens.
IDENTIFICATION = re.compile(
    rb"SSH-(2\.0|1\.99|1\.5)-([\x21-\x2c\x2e-\x7e]+)(?: [\x20-\x7e]*)?\r?\n"
)


async def identify_ssh(
    ip_address: str, port: int, *, allowed_targets: tuple[str, ...], timeout: float
) -> ServiceObservation:
    """Inspect one numeric, scoped destination within one overall deadline.

    Evidence is base64 to preserve exact untrusted bytes without terminal controls.
    A recognized banner is self-reported evidence, not verified product identity.
    """
    address = str(IPv4Address(ip_address))
    if address not in allowed_targets:
        raise ValueError(f"Target {address} is outside the allowed scope")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("timeout must be a finite positive number")
    evidence = bytearray()

    def observation(status: str, **fields: object) -> ServiceObservation:
        return ServiceObservation(
            address, port, status, base64.b64encode(evidence).decode("ascii"), **fields
        )

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.setblocking(False)
            loop = asyncio.get_running_loop()
            async with asyncio.timeout(timeout):
                await loop.sock_connect(connection, (address, port))
                pending = bytearray()
                while len(evidence) < MAX_BANNER_BYTES:
                    chunk = await loop.sock_recv(
                        connection, min(512, MAX_BANNER_BYTES - len(evidence))
                    )
                    if not chunk:
                        return observation(
                            "unidentified",
                            error="Connection closed before identification",
                        )
                    evidence.extend(chunk)
                    pending.extend(chunk)
                    while b"\n" in pending:
                        line, _, remainder = pending.partition(b"\n")
                        pending = bytearray(remainder)
                        line += b"\n"
                        if line.startswith(b"SSH-"):
                            match = IDENTIFICATION.fullmatch(line)
                            if match is None or len(line) > 255:
                                return observation(
                                    "unidentified", error="Malformed SSH identification"
                                )
                            return observation(
                                "identified",
                                protocol="ssh",
                                banner=line.rstrip(b"\r\n").decode("ascii"),
                                protocol_version=match[1].decode("ascii"),
                                advertised_software=match[2].decode("ascii"),
                                confidence="high",
                            )
                return observation("unidentified", error="Banner byte limit reached")
    except TimeoutError:
        return observation("timeout", error="SSH identification timed out")
    except OSError as error:
        return observation("error", error=str(error))
