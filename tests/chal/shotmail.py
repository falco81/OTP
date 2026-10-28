import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await (await b.new_context(viewport={'width':640,'height':900})).new_page()
        for n in ('token','signin','verify'):
            await pg.goto('file:///tmp/claude-0/chal/m_%s.html'%n); await pg.wait_for_timeout(300)
            await pg.screenshot(path='/home/claude/shots/mail_%s.png'%n, full_page=True)
        await b.close()
asyncio.run(main())
