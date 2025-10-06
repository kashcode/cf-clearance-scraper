import asyncio
import logging
from quart import Quart, request

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
                logging.error("No Cloudflare challenge detected.")
                return

            logging.info(challenge_messages[challenge_platform])

            try:
                await solver.solve_challenge()
            except asyncio.TimeoutError:
                pass

            all_cookies = await solver.get_cookies()
            clearance_cookie = solver.extract_clearance_cookie(all_cookies)

        user_agent = await solver.get_user_agent()

    if clearance_cookie is None:
        logging.error("Failed to retrieve a Cloudflare clearance cookie.")
        return {"error": "Failed to retrieve a Cloudflare clearance cookie."}, 400
    
    result = {
        "user_agent": user_agent,
        "all_cookies": all_cookies 
    }

    return result
