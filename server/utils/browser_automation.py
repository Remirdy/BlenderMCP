"""
Browser Automation Layer — API-less image generation pipeline.

Supports Midjourney (via Discord), ChatGPT web, Leonardo.ai, DALL-E (via ChatGPT),
and Ideogram — all without paid API keys, using Playwright browser automation.

Session management
------------------
First time you use a platform, call ``open_browser_session(platform)`` which opens
a headed browser so you can log in manually.  Cookies are saved to
``~/.remirdy/sessions/<platform>.json``.  All subsequent calls run headless.

Install
-------
    pip install playwright
    playwright install chromium
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("remirdy.browser_automation")

# ── session storage ───────────────────────────────────────────────────────────

def _sessions_dir() -> Path:
    d = Path.home() / ".remirdy" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(platform: str) -> Path:
    return _sessions_dir() / f"{platform}.json"


def has_session(platform: str) -> bool:
    return _session_path(platform).exists()


def _save_cookies(platform: str, cookies: list[dict]) -> None:
    _session_path(platform).write_text(
        json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("[%s] Session saved (%d cookies)", platform, len(cookies))


def _load_cookies(platform: str) -> list[dict] | None:
    p = _session_path(platform)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_session(platform: str) -> bool:
    p = _session_path(platform)
    if p.exists():
        p.unlink()
        return True
    return False


def list_sessions() -> dict[str, bool]:
    platforms = ["midjourney", "chatgpt", "leonardo", "dalle", "ideogram"]
    return {p: has_session(p) for p in platforms}


# ── playwright helpers ────────────────────────────────────────────────────────

async def _save_context_cookies(context, platform: str) -> None:
    cookies = await context.cookies()
    _save_cookies(platform, cookies)


# ── public: open a headed browser for manual login ───────────────────────────

async def open_browser_for_login(platform: str, login_url: str) -> dict[str, Any]:
    """
    Open a visible (headed) browser at ``login_url`` so the user can log in manually.
    Waits up to 3 minutes, then saves cookies and closes.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            "ok": False,
            "error": "playwright not installed — run: pip install playwright && playwright install chromium",
        }

    log.info("[%s] Opening headed browser for login at %s", platform, login_url)
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=False, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        await page.goto(login_url)

        # Poll until user navigates past login page (up to 3 min)
        deadline = time.time() + 180
        while time.time() < deadline:
            await asyncio.sleep(3)
            current_url = page.url
            if (
                current_url != login_url
                and "login" not in current_url.lower()
                and "signin" not in current_url.lower()
                and "auth" not in current_url.lower()
            ):
                break

        cookies = await context.cookies()
        _save_cookies(platform, cookies)
        await browser.close()
        await pw.stop()
        return {"ok": True, "cookies_saved": len(cookies), "platform": platform}
    except Exception as exc:
        log.exception("[%s] Login browser failed", platform)
        return {"ok": False, "error": str(exc)}


# ── workspace output helper ───────────────────────────────────────────────────

def _workspace_output(*parts: str) -> str:
    root = os.environ.get("REMIRDY_WORKSPACE", str(Path.home() / "RemirdyWorkspace"))
    out = Path(root) / "outputs" / "browser_gen"
    out.mkdir(parents=True, exist_ok=True)
    return str(out.joinpath(*parts))


# ═════════════════════════════════════════════════════════════════════════════
# Midjourney (via Discord)
# ═════════════════════════════════════════════════════════════════════════════

async def midjourney_generate(
    prompt: str,
    output_path: str,
    channel_url: str,
    wait_seconds: int = 300,
) -> dict[str, Any]:
    """
    Send a /imagine prompt to Midjourney via Discord web and download the result.

    Parameters
    ----------
    prompt       : The image description.
    output_path  : Where to save the downloaded image.
    channel_url  : Full Discord channel URL where Midjourney bot is active.
    wait_seconds : Max seconds to wait for generation (default 300).
    """
    if not has_session("midjourney"):
        return {
            "ok": False,
            "error": "No Discord session. Call open_browser_session('midjourney') first.",
            "action_required": "open_browser_session",
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    log.info("[Midjourney] Generating: %s", prompt[:80])
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await context.add_cookies(_load_cookies("midjourney") or [])
        page = await context.new_page()

        await page.goto(channel_url, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(2)

        # Find Discord message input
        msg_box = page.locator('div[role="textbox"][data-slate-editor="true"]')
        await msg_box.wait_for(timeout=15_000)
        await msg_box.click()

        # Type /imagine — triggers slash-command autocomplete
        await page.keyboard.type("/imagine ", delay=60)
        await asyncio.sleep(1.2)

        # Accept autocomplete if it appears
        try:
            autocomplete = page.locator('[id*="autocomplete"]').first
            await autocomplete.wait_for(timeout=2_500)
            await page.keyboard.press("Tab")
        except Exception:
            pass

        await page.keyboard.type(prompt, delay=30)
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")

        log.info("[Midjourney] Prompt sent, waiting up to %ds...", wait_seconds)

        image_url: str | None = None
        deadline = time.time() + wait_seconds

        while time.time() < deadline:
            await asyncio.sleep(8)
            try:
                # Discord attachment images from CDN
                imgs = page.locator(
                    'li[id*="chat-messages"] img[src*="cdn.discordapp.com/attachments"]'
                )
                count = await imgs.count()
                if count > 0:
                    src = await imgs.nth(count - 1).get_attribute("src")
                    if src:
                        image_url = src
                        log.info("[Midjourney] Image found")
                        break
            except Exception:
                pass

        if not image_url:
            await _save_context_cookies(context, "midjourney")
            await browser.close()
            await pw.stop()
            return {"ok": False, "error": f"Timed out after {wait_seconds}s waiting for Midjourney"}

        # Download image
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        dl_page = await context.new_page()
        response = await dl_page.goto(image_url)
        if response and response.ok:
            out.write_bytes(await response.body())
        else:
            img_bytes = await dl_page.evaluate(
                "async (url) => { const r = await fetch(url); const b = await r.arrayBuffer(); return Array.from(new Uint8Array(b)); }",
                image_url,
            )
            out.write_bytes(bytes(img_bytes))

        await _save_context_cookies(context, "midjourney")
        await browser.close()
        await pw.stop()

        return {
            "ok": True,
            "platform": "midjourney",
            "prompt": prompt,
            "image_path": str(out),
            "discord_image_url": image_url,
        }

    except Exception as exc:
        log.exception("[Midjourney] Generation failed")
        return {"ok": False, "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# ChatGPT Web
# ═════════════════════════════════════════════════════════════════════════════

CHATGPT_URL = "https://chatgpt.com"


async def chatgpt_send(
    prompt: str,
    output_path: str | None = None,
    wait_seconds: int = 90,
) -> dict[str, Any]:
    """
    Send a prompt to ChatGPT web.  Returns text response.
    If a DALL-E image is generated, saves it to ``output_path``.
    """
    if not has_session("chatgpt"):
        return {
            "ok": False,
            "error": "No ChatGPT session. Call open_browser_session('chatgpt') first.",
            "action_required": "open_browser_session",
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    log.info("[ChatGPT] Sending: %s", prompt[:80])
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        await context.add_cookies(_load_cookies("chatgpt") or [])
        page = await context.new_page()

        await page.goto(CHATGPT_URL, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(2)

        # Locate and fill prompt textarea
        textarea = page.locator(
            "#prompt-textarea, textarea[placeholder], div[contenteditable='true'][data-id]"
        ).first
        await textarea.wait_for(timeout=15_000)
        await textarea.click()
        await textarea.fill(prompt)
        await asyncio.sleep(0.4)

        # Send message
        send_btn = page.locator(
            'button[data-testid="send-button"], button[aria-label*="Send message"]'
        ).first
        await send_btn.click()

        log.info("[ChatGPT] Waiting for response...")

        # Wait for send button to re-enable (response complete)
        try:
            await page.wait_for_selector(
                'button[data-testid="send-button"]:not([disabled])',
                timeout=wait_seconds * 1000,
            )
        except Exception:
            pass
        await asyncio.sleep(1.5)

        # Extract assistant response text
        response_text = ""
        try:
            msgs = page.locator('[data-message-author-role="assistant"]')
            count = await msgs.count()
            if count > 0:
                response_text = await msgs.nth(count - 1).inner_text()
        except Exception:
            pass

        # Extract DALL-E generated image if present
        image_path_out = None
        if output_path:
            try:
                imgs = page.locator(
                    '[data-message-author-role="assistant"] img[src*="oaidalleapiprodscus"],'
                    '[data-message-author-role="assistant"] img[src*="dalle"]'
                )
                img_count = await imgs.count()
                if img_count > 0:
                    img_src = await imgs.nth(0).get_attribute("src")
                    if img_src:
                        out = Path(output_path)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        dl_page = await context.new_page()
                        resp = await dl_page.goto(img_src)
                        if resp and resp.ok:
                            out.write_bytes(await resp.body())
                            image_path_out = str(out)
                            log.info("[ChatGPT/DALL-E] Saved: %s", image_path_out)
            except Exception as img_exc:
                log.debug("[ChatGPT] Image extraction: %s", img_exc)

        await _save_context_cookies(context, "chatgpt")
        await browser.close()
        await pw.stop()

        return {
            "ok": True,
            "platform": "chatgpt",
            "prompt": prompt,
            "response_text": response_text,
            "image_path": image_path_out,
        }

    except Exception as exc:
        log.exception("[ChatGPT] Failed")
        return {"ok": False, "error": str(exc)}


async def chatgpt_plan_scene(scene_description: str) -> dict[str, Any]:
    """Ask ChatGPT to produce a structured 3D scene plan from a description."""
    planning_prompt = (
        "You are a 3D scene planning assistant for Blender. "
        "Given this description, produce a detailed scene plan as JSON with: "
        "objects (list with name, type, position_3d, material, scale), "
        "lighting (style, temperature_kelvin, direction), "
        "camera (angle, focal_length), mood, "
        "color_palette (list of hex colors), environment (sky, ground). "
        f"Scene: {scene_description}"
    )
    return await chatgpt_send(planning_prompt, wait_seconds=60)


# ═════════════════════════════════════════════════════════════════════════════
# DALL-E (via ChatGPT web)
# ═════════════════════════════════════════════════════════════════════════════

async def dalle_generate(
    prompt: str,
    output_path: str,
    wait_seconds: int = 90,
) -> dict[str, Any]:
    """Generate a DALL-E image via ChatGPT web interface."""
    result = await chatgpt_send(
        f"Generate an image: {prompt}",
        output_path=output_path,
        wait_seconds=wait_seconds,
    )
    if result.get("ok") and result.get("image_path"):
        result["platform"] = "dalle"
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Leonardo.ai
# ═════════════════════════════════════════════════════════════════════════════

LEONARDO_URL = "https://app.leonardo.ai"


async def leonardo_generate(
    prompt: str,
    output_path: str,
    style: str = "DYNAMIC",
    wait_seconds: int = 120,
) -> dict[str, Any]:
    """Generate an image on Leonardo.ai and download it."""
    if not has_session("leonardo"):
        return {
            "ok": False,
            "error": "No Leonardo session. Call open_browser_session('leonardo') first.",
            "action_required": "open_browser_session",
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    log.info("[Leonardo] Generating: %s", prompt[:80])
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        await context.add_cookies(_load_cookies("leonardo") or [])
        page = await context.new_page()

        await page.goto(f"{LEONARDO_URL}/ai-generations", wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(3)

        prompt_area = page.locator(
            'textarea[placeholder*="prompt" i], textarea[placeholder*="Prompt" i]'
        ).first
        await prompt_area.wait_for(timeout=15_000)
        await prompt_area.fill(prompt)
        await asyncio.sleep(0.5)

        generate_btn = page.locator(
            'button:has-text("Generate"), button[aria-label*="Generate" i]'
        ).first
        await generate_btn.click()

        log.info("[Leonardo] Waiting %ds for generation...", wait_seconds)
        await asyncio.sleep(8)

        image_url: str | None = None
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            await asyncio.sleep(5)
            try:
                imgs = page.locator(
                    'img[src*="cdn.leonardo.ai"], img[src*="storage.googleapis.com"]'
                )
                if await imgs.count() > 0:
                    src = await imgs.nth(0).get_attribute("src")
                    if src:
                        image_url = src
                        break
            except Exception:
                pass

        if not image_url:
            await _save_context_cookies(context, "leonardo")
            await browser.close()
            await pw.stop()
            return {"ok": False, "error": "Timed out waiting for Leonardo image"}

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        dl_page = await context.new_page()
        resp = await dl_page.goto(image_url)
        if resp and resp.ok:
            out.write_bytes(await resp.body())

        await _save_context_cookies(context, "leonardo")
        await browser.close()
        await pw.stop()

        return {
            "ok": True,
            "platform": "leonardo",
            "prompt": prompt,
            "image_path": str(out),
            "source_url": image_url,
        }

    except Exception as exc:
        log.exception("[Leonardo] Failed")
        return {"ok": False, "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Ideogram
# ═════════════════════════════════════════════════════════════════════════════

IDEOGRAM_URL = "https://ideogram.ai"


async def ideogram_generate(
    prompt: str,
    output_path: str,
    wait_seconds: int = 90,
) -> dict[str, Any]:
    """Generate an image on Ideogram and download it."""
    if not has_session("ideogram"):
        return {
            "ok": False,
            "error": "No Ideogram session. Call open_browser_session('ideogram') first.",
            "action_required": "open_browser_session",
        }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    log.info("[Ideogram] Generating: %s", prompt[:80])
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        await context.add_cookies(_load_cookies("ideogram") or [])
        page = await context.new_page()

        await page.goto(IDEOGRAM_URL, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(2)

        prompt_box = page.locator(
            'textarea, [contenteditable="true"]'
        ).first
        await prompt_box.wait_for(timeout=15_000)
        await prompt_box.fill(prompt)

        generate_btn = page.locator(
            'button:has-text("Generate"), button[type="submit"]'
        ).first
        await generate_btn.click()

        log.info("[Ideogram] Waiting %ds...", wait_seconds)
        await asyncio.sleep(10)

        image_url: str | None = None
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            await asyncio.sleep(5)
            try:
                imgs = page.locator(
                    'img[src*="ideogram.ai/api/images"], img[src*="storage.googleapis.com"]'
                )
                if await imgs.count() > 0:
                    src = await imgs.nth(0).get_attribute("src")
                    if src:
                        image_url = src
                        break
            except Exception:
                pass

        if not image_url:
            await browser.close()
            await pw.stop()
            return {"ok": False, "error": "Timed out waiting for Ideogram image"}

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        dl_page = await context.new_page()
        resp = await dl_page.goto(image_url)
        if resp and resp.ok:
            out.write_bytes(await resp.body())

        await _save_context_cookies(context, "ideogram")
        await browser.close()
        await pw.stop()

        return {"ok": True, "platform": "ideogram", "prompt": prompt, "image_path": str(out)}

    except Exception as exc:
        log.exception("[Ideogram] Failed")
        return {"ok": False, "error": str(exc)}


# ═════════════════════════════════════════════════════════════════════════════
# Login URLs per platform
# ═════════════════════════════════════════════════════════════════════════════

PLATFORM_LOGIN_URLS: dict[str, str] = {
    "midjourney": "https://discord.com/login",
    "chatgpt": "https://chatgpt.com/auth/login",
    "leonardo": "https://app.leonardo.ai",
    "dalle": "https://chatgpt.com/auth/login",
    "ideogram": "https://ideogram.ai/login",
}

PLATFORM_GENERATORS = {
    "midjourney": midjourney_generate,
    "chatgpt": chatgpt_send,
    "leonardo": leonardo_generate,
    "dalle": dalle_generate,
    "ideogram": ideogram_generate,
}


# ═════════════════════════════════════════════════════════════════════════════
# High-level: generate image → Blender scene pipeline
# ═════════════════════════════════════════════════════════════════════════════

async def generate_and_build_scene(
    prompt: str,
    platform: str = "chatgpt",
    build_scene: bool = True,
    channel_url: str | None = None,
    wait_seconds: int = 120,
    vision_provider: str = "auto",
    ctx: Any | None = None,
) -> dict[str, Any]:
    """
    End-to-end: generate image on a web platform → build 3D Blender scene.

    1. Generate image via chosen platform (no API key required).
    2. Optionally pass the image to psd_utils + layered_scene_ops for 3D build.
    """
    platform = platform.lower().strip()
    vision_provider = vision_provider.lower().strip()
    if platform not in PLATFORM_GENERATORS:
        return {
            "ok": False,
            "error": f"Unknown platform '{platform}'. Choose: {', '.join(PLATFORM_GENERATORS)}",
        }
    if vision_provider not in {"auto", "host", "gemini", "none"}:
        return {
            "ok": False,
            "error": "vision_provider must be one of: auto, host, gemini, none",
        }

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in prompt[:40])
    output_path = _workspace_output(f"{platform}_{safe_name}.png")

    gen_kwargs: dict[str, Any] = {
        "prompt": prompt,
        "output_path": output_path,
        "wait_seconds": wait_seconds,
    }
    if platform == "midjourney":
        if not channel_url:
            return {
                "ok": False,
                "error": "channel_url is required for Midjourney — provide your Discord channel URL.",
            }
        gen_kwargs["channel_url"] = channel_url

    result = await PLATFORM_GENERATORS[platform](**gen_kwargs)

    if not result.get("ok"):
        return result

    actual_image = result.get("image_path") or output_path

    if not build_scene:
        return {**result, "scene_built": False}

    # Build Blender scene from generated image
    try:
        from .psd_utils import parse_layered_image
        from .ai_vision import generate_scene_plan, generate_scene_plan_with_host_ai, is_available as gemini_available
        from ..tools._common import call

        out_dir = _workspace_output("scene_layers", safe_name)
        layers = parse_layered_image(
            actual_image,
            out_dir,
            use_gemini_ai=(vision_provider == "gemini"),
        )

        if not layers.get("ai_scene_plan"):
            analysis_image = layers.get("analysis_image_path") or actual_image
            if vision_provider in {"auto", "host"} and ctx is not None:
                host_plan = await generate_scene_plan_with_host_ai(
                    ctx,
                    analysis_image,
                    layers.get("layers") or None,
                )
                if host_plan:
                    layers["ai_scene_plan"] = host_plan
                    layers["ai_scene_plan_provider"] = "host"
            if (
                not layers.get("ai_scene_plan")
                and vision_provider in {"auto", "gemini"}
                and gemini_available()
            ):
                gemini_plan = generate_scene_plan(analysis_image, layers.get("layers") or None)
                if gemini_plan:
                    layers["ai_scene_plan"] = gemini_plan
                    layers["ai_scene_plan_provider"] = "gemini"

        scene_result = call("build_layered_scene_from_image", {
            "image_path": actual_image,
            "output_dir": out_dir,
            "layers_data": layers,
        })

        return {
            **result,
            "scene_built": True,
            "layers_detected": len(layers.get("layers", [])),
            "ai_scene_plan": layers.get("ai_scene_plan"),
            "ai_scene_plan_provider": layers.get("ai_scene_plan_provider"),
            "scene_result": scene_result,
        }
    except Exception as exc:
        log.warning("Scene build failed after image generation: %s", exc)
        return {**result, "scene_built": False, "scene_error": str(exc)}


# ── sync wrapper for MCP tools ────────────────────────────────────────────────

def run_async(coro) -> Any:
    """Run an async coroutine from a synchronous context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
