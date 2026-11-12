import os
from concurrent.futures import ThreadPoolExecutor
import re
import socket


def _miner_ips() -> tuple[str, ...]:
    """Miner IPs come from the CAIRN_MINER_IPS env var (comma separated).

    Never hardcode private-network addresses in source: they leak your
    internal topology into the git history.
    """
    raw = os.environ.get("CAIRN_MINER_IPS", "")
    return tuple(ip.strip() for ip in raw.split(",") if ip.strip())


MINER_IPS = _miner_ips()

PORT = 4048
TIMEOUT = 2.0
MAX_RESPONSE = 16384


def parse_summary(raw):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")

    raw = raw.replace("\x00", "").strip()
    fields = {}

    for part in re.split(r"[|;\r\n]+", raw):
        key, separator, value = part.partition("=")
        if separator:
            key = key.strip().upper()
            if re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                fields[key] = value.strip()

    if not fields:
        raise ValueError("Invalid summary response")

    def number(key):
        value = fields.get(key)
        if value is None:
            return None
        try:
            result = float(value)
            if not result == result or abs(result) == float("inf"):
                return None
            return int(result) if result.is_integer() else result
        except (TypeError, ValueError):
            return None

    return {
        "name": fields.get("NAME"),
        "algorithm": fields.get("ALGO"),
        "cpus": number("CPUS"),
        "khs": number("KHS"),
        "accepted": number("ACC"),
        "rejected": number("REJ"),
        "temperature": number("TEMP"),
        "uptime": number("UPTIME"),
    }


def _read_one(ip):
    result = {"ip": ip, "status": "offline"}

    try:
        with socket.create_connection((ip, PORT), timeout=TIMEOUT) as sock:
            sock.settimeout(TIMEOUT)
            sock.sendall(b"summary\n")

            chunks = []
            total = 0

            while total < MAX_RESPONSE:
                try:
                    chunk = sock.recv(min(4096, MAX_RESPONSE - total))
                except socket.timeout:
                    break

                if not chunk:
                    break

                chunks.append(chunk)
                total += len(chunk)

        raw = b"".join(chunks)
        if not raw:
            raise TimeoutError("No summary response")

        result.update(parse_summary(raw))
        result["status"] = "online"

    except socket.timeout:
        result["error"] = "timeout"
    except TimeoutError:
        result["error"] = "timeout"
    except ValueError:
        result["error"] = "invalid response"
    except OSError:
        result["error"] = "connection error"

    return result


def get_miners():
    with ThreadPoolExecutor(max_workers=5) as pool:
        miners = list(pool.map(_read_one, MINER_IPS))

    online = sum(item["status"] == "online" for item in miners)

    return {
        "total": len(miners),
        "online": online,
        "offline": len(miners) - online,
        "miners": miners,
    }
