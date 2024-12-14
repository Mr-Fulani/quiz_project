import aiohttp
import asyncio
import ssl
import certifi




async def test_connection():
    url = "https://hook.eu2.make.com/vemjfbnjr3lu3o6ywcbnttu9dbwfcm09"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context)) as session:
        try:
            async with session.post(url, json={"test": "data"}) as response:
                text = await response.text()
                print(f"Status: {response.status}")
                print(f"Response: {text}")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test_connection())
