"""
browser_controller.py — Async Playwright Chromium Controller with ARIA Token Compaction.

Implements token-compacted browser perception, generating lightweight numbered ARIA catalogs
rather than bloated raw HTML to optimize LLM context efficiency and prevent prompt flooding.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional, Tuple

from ultron.execution.computer_contracts import BrowserSnapshot

logger = logging.getLogger(__name__)

# Maximum interactive elements included in the ARIA catalog before truncation
MAX_ARIA_CATALOG_ELEMENTS = 40

# Interactive CSS selectors for DOM element discovery
INTERACTIVE_SELECTOR = (
    "a[href], button, input:not([type='hidden']), textarea, select, "
    "[role='button'], [role='link'], [role='textbox'], [role='checkbox'], "
    "[role='combobox'], [role='menuitem'], [tabindex='0']"
)


class BrowserController:
    """
    Async Playwright browser controller for automated web perception and action execution.
    """

    def __init__(
        self,
        bot_id: str = "default_bot",
        session_id: str = "default",
        headless: bool = True,
        channel: Optional[str] = None,
        max_elements: int = MAX_ARIA_CATALOG_ELEMENTS,
        **launch_kwargs: Any,
    ) -> None:
        self.bot_id = launch_kwargs.pop("bot_id", bot_id)
        self.session_id = launch_kwargs.pop("session_id", session_id)
        self.isolation_key = f"{self.bot_id}:{self.session_id}"
        self.composite_key = self.isolation_key

        self.headless = headless
        self.channel = channel
        self.max_elements = max_elements
        self.launch_kwargs = launch_kwargs

        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._element_registry: Dict[int, Any] = {}

    async def start(self) -> None:
        """Initialize and launch the Chromium browser instance."""
        if self._browser is not None:
            return

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        # Launch Chromium with fallback to system browser channels (msedge/chrome) if bundled binaries are absent
        launch_params = dict(self.launch_kwargs)
        if self.channel:
            launch_params["channel"] = self.channel

        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                **launch_params,
            )
        except Exception as exc:
            logger.info("Direct Chromium launch failed (%s); attempting fallback browser channels...", exc)
            try:
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    channel="msedge",
                    **self.launch_kwargs,
                )
            except Exception:
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    channel="chrome",
                    **self.launch_kwargs,
                )

        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        )
        self._page = await self._context.new_page()
        logger.info("BrowserController started successfully.")

    async def _ensure_started(self) -> None:
        """Ensure the browser page is active."""
        if self._page is None or self._browser is None:
            await self.start()

    @property
    def page(self) -> Any:
        """Return the active Playwright Page object."""
        return self._page

    async def _build_aria_catalog(self) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Token Compaction Engine:
        Do NOT fetch raw HTML.

        page.accessibility.snapshot() is deprecated as of current Playwright versions.
        Prefers locator.aria_snapshot() on a root locator (e.g. page.locator("body")).
        If the pinned version predates that API or fails, explicitly falls back to
        accessibility.snapshot().

        Formats output into a lightweight, numbered catalog:
          [1] Link: "Documentation"
          [2] Input (text): "Search"
          [3] Button: "Submit"
        Truncates at MAX_ARIA_CATALOG_ELEMENTS (40) with [...remaining elements omitted].
        """
        self._element_registry.clear()

        # 1. Probe locator.aria_snapshot() on root body
        try:
            raw_aria = await self._page.locator("body").aria_snapshot()
        except (AttributeError, Exception) as exc:
            # Explicit commented fallback: accessibility.snapshot() is deprecated in modern Playwright (>=1.49),
            # but retained as a fail-safe fallback if locator.aria_snapshot() is unsupported.
            try:
                acc_snapshot = await self._page.accessibility.snapshot()
                raw_aria = str(acc_snapshot) if acc_snapshot else ""
            except Exception:
                raw_aria = ""

        # 2. Extract and index interactive elements on the page
        locators = self._page.locator(INTERACTIVE_SELECTOR)
        total_interactive = await locators.count()

        catalog_lines: List[str] = []
        interactive_data: List[Dict[str, Any]] = []

        assigned_id = 1
        for i in range(total_interactive):
            loc = locators.nth(i)
            try:
                if not await loc.is_visible():
                    continue

                tag = (await loc.evaluate("el => el.tagName.toLowerCase()")) or ""
                itype = (await loc.evaluate("el => el.getAttribute('type') || ''")).lower()
                text = (
                    await loc.evaluate(
                        "el => el.getAttribute('aria-label') || el.innerText || el.getAttribute('placeholder') || el.getAttribute('value') || el.getAttribute('title') || ''"
                    )
                ) or ""
                role_attr = (await loc.evaluate("el => el.getAttribute('role') || ''")).lower()
            except Exception:
                continue

            cleaned_text = " ".join(text.split()).strip()

            # Determine human-readable role label
            if tag == "a" or role_attr == "link":
                role_label = "Link"
            elif tag == "button" or role_attr == "button" or itype in ("button", "submit", "reset"):
                role_label = "Button"
            elif tag == "input":
                input_kind = itype or "text"
                role_label = f"Input ({input_kind})"
            elif tag == "textarea":
                role_label = "Textarea"
            elif tag == "select":
                role_label = "Select"
            elif role_attr == "checkbox" or itype == "checkbox":
                role_label = "Checkbox"
            else:
                role_label = role_attr.capitalize() if role_attr else "Element"

            if assigned_id <= self.max_elements:
                line = f'[{assigned_id}] {role_label}: "{cleaned_text}"'
                catalog_lines.append(line)
                interactive_data.append({
                    "id": assigned_id,
                    "role": role_label,
                    "text": cleaned_text,
                    "tag": tag,
                })
                self._element_registry[assigned_id] = loc
                assigned_id += 1
            else:
                # Truncation boundary reached
                break

        # Truncate at 40 elements with [...remaining elements omitted] to prevent context flooding
        if total_interactive > self.max_elements:
            catalog_lines.append("[...remaining elements omitted]")

        formatted_aria = "\n".join(catalog_lines)
        return formatted_aria, interactive_data

    async def get_current_snapshot(self) -> BrowserSnapshot:
        """
        Capture the current browser state into a token-compacted BrowserSnapshot.
        """
        await self._ensure_started()

        url = self._page.url or "about:blank"
        title = await self._page.title() or ""

        # Build numbered ARIA catalog
        aria_tree, interactive_elements = await self._build_aria_catalog()

        # Capture lightweight JPEG screenshot as base64
        screenshot_b64: Optional[str] = None
        try:
            screenshot_bytes = await self._page.screenshot(type="jpeg", quality=50)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("ascii")
        except Exception as exc:
            logger.debug("Screenshot capture omitted: %s", exc)

        return BrowserSnapshot(
            url=url,
            title=title,
            aria_tree=aria_tree,
            interactive_elements=interactive_elements,
            screenshot_b64=screenshot_b64,
        )

    async def navigate(self, url: str) -> BrowserSnapshot:
        """
        Navigate browser to the requested target URL and return the perception snapshot.
        """
        await self._ensure_started()
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return await self.get_current_snapshot()

    async def click_element(self, element_id: int) -> BrowserSnapshot:
        """
        Click an interactive element by its 1-based catalog ID and return the updated snapshot.
        """
        await self._ensure_started()
        locator = self._element_registry.get(element_id)
        if locator is None:
            raise ValueError(
                f"Element ID [{element_id}] not found in active catalog "
                f"(available IDs: 1..{len(self._element_registry)})."
            )

        await locator.click()
        try:
            await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass

        return await self.get_current_snapshot()

    async def type_text(self, element_id: int, text: str) -> BrowserSnapshot:
        """
        Fill text into an input or textarea element by its 1-based catalog ID and return updated snapshot.
        """
        await self._ensure_started()
        locator = self._element_registry.get(element_id)
        if locator is None:
            raise ValueError(
                f"Element ID [{element_id}] not found in active catalog "
                f"(available IDs: 1..{len(self._element_registry)})."
            )

        await locator.fill(text)
        return await self.get_current_snapshot()

    async def close(self) -> None:
        """Close browser context and terminate the Playwright driver."""
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
            self._page = None

        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._element_registry.clear()
        logger.info("BrowserController closed.")

    async def __aenter__(self) -> BrowserController:
        await self.start()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()
