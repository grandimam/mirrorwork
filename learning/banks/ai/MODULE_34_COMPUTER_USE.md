# Module 34: Computer Use and Browser Automation

## 34.1 What is Computer Use?

```
Computer Use = LLM that can control a computer

Capabilities:
- See screenshots
- Move mouse, click
- Type text
- Navigate applications
- Browse the web

Use cases:
- Web automation
- Testing
- Data entry
- Research tasks
```

## 34.2 Anthropic Computer Use

```python
import anthropic

client = anthropic.Anthropic()

# Computer use requires specific tools
tools = [
    {
        "type": "computer_20241022",
        "name": "computer",
        "display_width_px": 1024,
        "display_height_px": 768,
        "display_number": 1,
    },
    {
        "type": "text_editor_20241022",
        "name": "str_replace_editor",
    },
    {
        "type": "bash_20241022",
        "name": "bash",
    }
]

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4096,
    tools=tools,
    messages=[{
        "role": "user",
        "content": "Open Firefox and go to example.com"
    }]
)
```

## 34.3 Computer Tool Actions

```python
# Actions the computer tool can perform
COMPUTER_ACTIONS = {
    "screenshot": "Take a screenshot",
    "mouse_move": "Move mouse to x, y coordinates",
    "left_click": "Click left mouse button",
    "right_click": "Click right mouse button",
    "double_click": "Double-click",
    "type": "Type text",
    "key": "Press a key (Enter, Tab, etc.)",
    "scroll": "Scroll up/down",
}

# Model returns action like:
# {
#     "type": "tool_use",
#     "name": "computer",
#     "input": {
#         "action": "mouse_move",
#         "coordinate": [500, 300]
#     }
# }
```

## 34.4 Computer Use Loop

```python
async def computer_use_loop(
    client,
    task: str,
    execute_action: callable,
    max_iterations: int = 20
) -> str:
    messages = [{"role": "user", "content": task}]

    for _ in range(max_iterations):
        response = await client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            tools=tools,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            return extract_text(response)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if block.name == "computer":
                        result = await execute_action(block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result  # Screenshot or confirmation
                        })

            messages.append({"role": "user", "content": tool_results})

    return "Max iterations reached"
```

## 34.5 Playwright Integration

```python
from playwright.async_api import async_playwright
import base64

class BrowserController:
    def __init__(self):
        self.browser = None
        self.page = None

    async def start(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page()
        await self.page.set_viewport_size({"width": 1024, "height": 768})

    async def execute(self, action: dict) -> dict:
        action_type = action["action"]

        if action_type == "screenshot":
            screenshot = await self.page.screenshot()
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(screenshot).decode()
                }
            }

        elif action_type == "mouse_move":
            x, y = action["coordinate"]
            await self.page.mouse.move(x, y)

        elif action_type == "left_click":
            await self.page.mouse.click(
                action.get("coordinate", [0, 0])[0],
                action.get("coordinate", [0, 0])[1]
            )

        elif action_type == "type":
            await self.page.keyboard.type(action["text"])

        elif action_type == "key":
            await self.page.keyboard.press(action["key"])

        elif action_type == "scroll":
            direction = action.get("direction", "down")
            amount = action.get("amount", 3)
            delta = -100 * amount if direction == "up" else 100 * amount
            await self.page.mouse.wheel(0, delta)

        # Return screenshot after action
        screenshot = await self.page.screenshot()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": base64.b64encode(screenshot).decode()
            }
        }
```

## 34.6 Web Automation Example

```python
async def web_research(query: str) -> str:
    controller = BrowserController()
    await controller.start()

    # Navigate to starting point
    await controller.page.goto("https://www.google.com")

    result = await computer_use_loop(
        client=anthropic.Anthropic(),
        task=f"""
Research this topic and summarize findings: {query}

Steps:
1. Search Google for relevant information
2. Visit 2-3 authoritative sources
3. Extract key information
4. Provide a summary with sources
""",
        execute_action=controller.execute
    )

    await controller.browser.close()
    return result
```

## 34.7 Safety Considerations

```python
class SafeComputerUse:
    def __init__(self):
        self.blocked_urls = ["bank", "login", "admin"]
        self.blocked_actions = []
        self.action_log = []

    async def execute_safe(self, action: dict, page) -> dict:
        # Log all actions
        self.action_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action
        })

        # Check URL safety
        if action.get("action") == "goto":
            url = action.get("url", "")
            if any(blocked in url.lower() for blocked in self.blocked_urls):
                return {"error": f"URL blocked: {url}"}

        # Require confirmation for sensitive actions
        if action.get("action") in ["type", "key"]:
            text = action.get("text", "") + action.get("key", "")
            if any(char in text for char in ["@", "password"]):
                # Could prompt for human approval here
                pass

        # Execute with timeout
        try:
            async with asyncio.timeout(10):
                return await self._execute(action, page)
        except asyncio.TimeoutError:
            return {"error": "Action timed out"}
```

## 34.8 Structured Browser Actions

```python
# Alternative: Use Playwright MCP server
# Provides structured browser control

MCP_BROWSER_TOOLS = [
    {
        "name": "browser_navigate",
        "description": "Navigate to a URL",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"]
        }
    },
    {
        "name": "browser_click",
        "description": "Click an element by selector",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"]
        }
    },
    {
        "name": "browser_type",
        "description": "Type into an input field",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "text": {"type": "string"}
            },
            "required": ["selector", "text"]
        }
    },
    {
        "name": "browser_snapshot",
        "description": "Get page accessibility tree",
        "input_schema": {"type": "object", "properties": {}}
    }
]
```

## 34.9 Desktop Automation

```python
import pyautogui
import subprocess

class DesktopController:
    def __init__(self, display_size: tuple = (1920, 1080)):
        self.width, self.height = display_size
        pyautogui.FAILSAFE = True

    def screenshot(self) -> bytes:
        img = pyautogui.screenshot()
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def execute(self, action: dict):
        action_type = action["action"]

        if action_type == "mouse_move":
            x, y = action["coordinate"]
            pyautogui.moveTo(x, y)

        elif action_type == "left_click":
            x, y = action.get("coordinate", pyautogui.position())
            pyautogui.click(x, y)

        elif action_type == "type":
            pyautogui.write(action["text"])

        elif action_type == "key":
            pyautogui.press(action["key"])

        elif action_type == "hotkey":
            pyautogui.hotkey(*action["keys"])  # e.g., ["ctrl", "c"]

        return self.screenshot()
```

## 34.10 Summary

| Approach | Use Case |
|----------|----------|
| Claude Computer Use | General computer control |
| Playwright + Vision | Web automation |
| Structured browser tools | Reliable web actions |
| PyAutoGUI | Desktop automation |

**Best practices:**
- Sandbox in VM or container
- Log all actions
- Set action limits
- Block sensitive URLs
- Use structured tools when possible
- Human approval for critical actions
