import asyncio
import aiohttp
import base64
import os
import re
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv("config.env")

LIMIT = int(os.getenv("LIMIT", 1000))
TIMEOUT = int(os.getenv("TIMEOUT", 3))
CONCURRENCY = int(os.getenv("CONCURRENCY", 50))
SUB_URLS = os.getenv("SUB_URLS", "").strip().splitlines()

sem = asyncio.Semaphore(CONCURRENCY)

def parse_vmess(line):
    try:
        raw = line.replace("vmess://", "")
        decoded = base64.b64decode(raw + "===").decode()
        host = re.search(r'"add"\s*:\s*"([^"]+)"', decoded).group(1)
        port = re.search(r'"port"\s*:\s*"?(\\d+)"?', decoded).group(1)
        return host, int(port)
    except:
        return None

def parse_generic(line):
    try:
        parsed = urlparse(line)
        return parsed.hostname, parsed.port
    except:
        return None

def extract_host_port(line):
    if line.startswith("vmess://"):
        return parse_vmess(line)
    elif line.startswith(("vless://", "trojan://", "ss://")):
        return parse_generic(line)
    return None

async def tcp_test(host, port):
    try:
        async with sem:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=TIMEOUT
            )
            writer.close()
            await writer.wait_closed()
            return True
    except:
        return False

async def fetch_sub(session, url):
    try:
        async with session.get(url, timeout=TIMEOUT) as resp:
            return await resp.text()
    except:
        return ""

async def main():
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[
            fetch_sub(session, url.strip())
            for url in SUB_URLS if url.strip()
        ])

    lines = []
    for r in results:
        lines.extend(r.splitlines())

    lines = lines[:LIMIT]

    checked = {}
    working = []

    for line in lines:
        hp = extract_host_port(line.strip())
        if not hp:
            continue

        key = f"{hp[0]}:{hp[1]}"
        if key in checked:
            continue

        is_open = await tcp_test(hp[0], hp[1])
        checked[key] = True

        if is_open:
            working.append(line.strip())

    with open("working.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(working))

asyncio.run(main())
