#!/usr/bin/env python3
"""GeoSource MCP 客户端冒烟测试：以 stdio 子进程启动 server.py，
调用 search_gis_services(keyword="DEM", limit=30) 并打印真实返回。"""
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = r"E:/my_repo/GeoSource/server.py"


async def main():
    # 用 sys.executable 等价于 `python server.py`，并保证子进程与本客户端使用同一解释器
    params = StdioServerParameters(command=sys.executable, args=[SERVER])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_gis_services", {"keyword": "DEM", "limit": 30}
            )
            for block in result.content:
                if block.type == "text":
                    print(block.text)


if __name__ == "__main__":
    asyncio.run(main())
