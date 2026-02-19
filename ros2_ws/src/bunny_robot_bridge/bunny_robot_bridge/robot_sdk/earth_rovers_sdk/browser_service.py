import logging
import os
import time
from typing import Optional

from dotenv import load_dotenv
from pyppeteer import launch

try:
    from bunny_robot_bridge.core.constants import (
        BROWSER_ERROR_LOG_INTERVAL,
        CHROME_FALLBACK_PATHS,
        DEFAULT_CHROME_PATH,
        DEFAULT_IMAGE_FORMAT,
        DEFAULT_IMAGE_QUALITY,
        DEFAULT_VIEWPORT,
        SDK_LOCAL_ENDPOINT,
        VALID_IMAGE_FORMATS,
    )
except ImportError:
    # Fallback if constants module not available (e.g., when SDK used standalone)
    BROWSER_ERROR_LOG_INTERVAL = 10.0
    CHROME_FALLBACK_PATHS = [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    DEFAULT_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    DEFAULT_VIEWPORT = {"width": 3840, "height": 2160}
    SDK_LOCAL_ENDPOINT = "http://127.0.0.1:8000/sdk"
    VALID_IMAGE_FORMATS = ["png", "jpeg", "webp"]
    DEFAULT_IMAGE_FORMAT = "jpeg"
    DEFAULT_IMAGE_QUALITY = 0.85

load_dotenv()

logger = logging.getLogger(__name__)

# Throttle "Error initializing browser" to avoid log spam
_last_browser_error_log = 0.0


class BrowserService:
    """Service for interacting with browser-based SDK interface."""

    def __init__(
        self,
        image_format: Optional[str] = None,
        image_quality: Optional[float] = None,
        viewport: Optional[dict] = None,
    ):
        """
        Initialize browser service.
        
        Args:
            image_format: Image format (png, jpeg, webp). Defaults to env var or "png"
            image_quality: Image quality (0.0-1.0). Defaults to env var or 1.0
            viewport: Viewport dimensions dict with 'width' and 'height'. Defaults to 3840x2160
        """
        self.browser = None
        self.page = None
        
        # Configuration from parameters or environment variables
        self.image_format = image_format or os.getenv("IMAGE_FORMAT", DEFAULT_IMAGE_FORMAT)
        self.image_quality = image_quality or float(os.getenv("IMAGE_QUALITY", str(DEFAULT_IMAGE_QUALITY)))
        self.default_viewport = viewport or DEFAULT_VIEWPORT.copy()
        
        # Validate configuration
        if self.image_format not in VALID_IMAGE_FORMATS:
            raise ValueError(
                f"Invalid image format: {self.image_format}. "
                f"Supported formats: {', '.join(VALID_IMAGE_FORMATS)}"
            )
        
        if not 0 <= self.image_quality <= 1:
            raise ValueError(
                f"Invalid image quality: {self.image_quality}. "
                "Quality should be between 0 and 1"
            )

    def _find_chrome_executable(self) -> str:
        """
        Find Chrome executable path, checking configured path and fallbacks.
        
        Returns:
            Path to Chrome executable
            
        Raises:
            RuntimeError: If no Chrome executable found
        """
        executable_path = os.getenv("CHROME_EXECUTABLE_PATH", DEFAULT_CHROME_PATH)
        
        # Check configured path first
        if os.path.isfile(executable_path) and os.access(executable_path, os.X_OK):
            return executable_path
        
        # Try fallback paths
        for fallback in CHROME_FALLBACK_PATHS:
            if os.path.isfile(fallback) and os.access(fallback, os.X_OK):
                logger.debug(f"Using Chrome fallback path: {fallback}")
                return fallback
        
        raise RuntimeError(
            f"Chrome executable not found. Tried: {executable_path} and fallbacks: {CHROME_FALLBACK_PATHS}"
        )

    async def initialize_browser(self):
        """Initialize browser and navigate to SDK page."""
        if not self.browser:
            try:
                executable_path = self._find_chrome_executable()
                
                self.browser = await launch(
                    executablePath=executable_path,
                    headless=True,
                    args=[
                        "--ignore-certificate-errors",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--no-first-run",
                        "--no-zygote",
                        "--disable-extensions",
                        f"--window-size={self.default_viewport['width']},{self.default_viewport['height']}",
                    ],
                )
                self.page = await self.browser.newPage()
                await self.page.setViewport(self.default_viewport)
                await self.page.setExtraHTTPHeaders(
                    {"Accept-Language": "en-US,en;q=0.9"}
                )
                sdk_page_url = os.getenv("SDK_PAGE_URL", SDK_LOCAL_ENDPOINT)
                await self.page.goto(
                    sdk_page_url, {"waitUntil": "networkidle2", "timeout": 30000}
                )
                await self.page.waitForSelector("#join", {"timeout": 10000})
                await self.page.click("#join")
                await self.page.waitForSelector("video", {"timeout": 15000})
                await self.page.waitForSelector("#map")
                await self.page.setViewport(self.default_viewport)

                await self.page.waitFor(2000)

                # Initialize image parameters
                call = f"""() => {{
                    window.initializeImageParams({{
                        imageFormat: "{self.image_format}",
                        imageQuality: {self.image_quality}
                    }});
                }}"""
                await self.page.evaluate(call)
                
            except Exception as e:
                global _last_browser_error_log
                now = time.time()
                if now - _last_browser_error_log >= BROWSER_ERROR_LOG_INTERVAL:
                    logger.error(f"Error initializing browser: {e}")
                    _last_browser_error_log = now
                self.browser = None
                self.page = None
                await self.close_browser()
                raise

    async def take_screenshot(self, video_output_folder: str, elements: list):
        await self.initialize_browser()
        if self.page is None:
            return {}

        dimensions = await self.page.evaluate(
            """() => {
            return {
                width: Math.max(document.documentElement.scrollWidth, window.innerWidth),
                height: Math.max(document.documentElement.scrollHeight, window.innerHeight),
            }
        }"""
        )

        if (
            dimensions["width"] > self.default_viewport["width"]
            or dimensions["height"] > self.default_viewport["height"]
        ):
            await self.page.setViewport(dimensions)

        element_map = {"front": "#player-1000", "rear": "#player-1001", "map": "#map"}

        screenshots = {}
        for name in elements:
            if name in element_map:
                element_id = element_map[name]
                output_path = f"{video_output_folder}/{name}.png"
                element = await self.page.querySelector(element_id)
                if element:
                    start_time = time.time()  # Start time
                    await element.screenshot({"path": output_path})
                    end_time = time.time()  # End time
                    elapsed_time = (
                        end_time - start_time
                    ) * 1000  # Convert to milliseconds
                    logger.debug(f"Screenshot for {name} took {elapsed_time:.2f} ms")
                    screenshots[name] = output_path
                else:
                    logger.warning(f"Element {element_id} not found")
            else:
                logger.warning(f"Invalid element name: {name}")

        return screenshots

    async def data(self) -> dict:
        await self.initialize_browser()
        if self.page is None:
            return {}

        bot_data = await self.page.evaluate(
            """() => {
        return window.rtm_data;
        }"""
        )

        return bot_data or {}

    async def front(self) -> str:
        await self.initialize_browser()
        if self.page is None:
            return ""

        front_frame = await self.page.evaluate(
            """() => {
        return getLastBase64Frame(1000) || null;
        }"""
        )

        return front_frame or ""

    async def rear(self) -> str:
        await self.initialize_browser()
        if self.page is None:
            return ""

        rear_frame = await self.page.evaluate(
            """() => {
        return getLastBase64Frame(1001) || null;
        }"""
        )

        return rear_frame or ""

    async def send_message(self, message: dict):
        await self.initialize_browser()
        if self.page is None:
            return

        await self.page.evaluate(
            """(message) => {
                window.sendMessage(message);
            }""",
            message,
        )

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
