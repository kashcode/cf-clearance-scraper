import asyncio
import logging
from quart import Quart, request
import aiohttp

from main import ChallengePlatform, CloudflareSolver, get_chrome_user_agent

app = Quart(__name__)

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

@app.route('/', methods=['POST'])
async def cf_clearance():
    data = await request.get_json()

    logging.getLogger("zendriver").setLevel(logging.WARNING)

    headed = data.get("headed", False)
    logging.info("Launching %s browser...", "headed" if headed else "headless")

    challenge_messages = {
        ChallengePlatform.JAVASCRIPT: "Solving Cloudflare challenge [JavaScript]...",
        ChallengePlatform.MANAGED: "Solving Cloudflare challenge [Managed]...",
        ChallengePlatform.INTERACTIVE: "Solving Cloudflare challenge [Interactive]...",
    }

    url = data.get("url", None)
    if url is None:
        return {"error": "URL is required."}, 400
    
    user_agent = get_chrome_user_agent() if data.get("user_agent", None) is None else data.get("user_agent")
    timeout = data.get("timeout", 30)
    http2 = not data.get("disable_http2", False)
    http3 = not data.get("disable_http3", False)
    proxy = data.get("proxy", None)

    async with CloudflareSolver(
        user_agent=user_agent,
        timeout=timeout,
        http2=http2,
        http3=http3,
        headless=not headed,
        proxy=proxy,
    ) as solver:
        logging.info("Going to %s...", url)

        try:
            await solver.driver.get(url)
        except asyncio.TimeoutError as err:
            logging.error(err)
            return

        all_cookies = await solver.get_cookies()
        clearance_cookie = solver.extract_clearance_cookie(all_cookies)

        if clearance_cookie is None:
            await solver.set_user_agent_metadata(await solver.get_user_agent())
            challenge_platform = await solver.detect_challenge()

            if challenge_platform is None:
                logging.info("No Cloudflare challenge detected.")
                return

            logging.info(challenge_messages[challenge_platform])

            try:
                await solver.solve_challenge()
            except asyncio.TimeoutError:
                pass

            all_cookies = await solver.get_cookies()
            clearance_cookie = solver.extract_clearance_cookie(all_cookies)        
        
        user_agent = await solver.get_user_agent()
        cookies = await solver.driver.cookies.get_all()

        headers = {'User-Agent': user_agent}

        # Convert zendriver Cookie objects -> dict
        cookie_dict = {c.name: c.value for c in cookies}

        async with aiohttp.ClientSession(cookies=cookie_dict, headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logging.error(f"Failed to retrieve response, status code: {resp.status}")
                    return {"error": f"Failed to retrieve response, status code: {resp.status}"}, 400

                content = await resp.read()
    
    return content
