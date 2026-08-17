from __future__ import annotations

import asyncio
import logging

import httpx

from simulator.services.common.config import GATEWAY_URL

log = logging.getLogger("traffic")


async def _loop() -> None:
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.post(
                    f"{GATEWAY_URL}/api/orders",
                    json={"sku": "sku-100", "qty": 1},
                    timeout=6.0,
                )
            except Exception:
                log.info("storefront request unfinished")
            await asyncio.sleep(1.0)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_loop())


if __name__ == "__main__":
    main()
