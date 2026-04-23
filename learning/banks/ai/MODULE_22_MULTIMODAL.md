# Module 22: Multimodal AI

## 22.1 Vision Capabilities

```python
import anthropic
import base64

client = anthropic.Anthropic()

# From URL
response = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "url", "url": "https://example.com/image.jpg"}},
            {"type": "text", "text": "Describe this image"}
        ]
    }]
)

# From base64
def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode()

response = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_to_base64("screenshot.png")
                }
            },
            {"type": "text", "text": "What's in this image?"}
        ]
    }]
)
```

## 22.2 PDF Processing

```python
# Direct PDF support
def pdf_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode()

response = client.messages.create(
    model="claude-3-5-sonnet",
    max_tokens=4096,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_to_base64("document.pdf")
                }
            },
            {"type": "text", "text": "Summarize this document"}
        ]
    }]
)
```

## 22.3 Multiple Images

```python
def compare_images(image_paths: list[str], question: str) -> str:
    content = []

    for path in image_paths:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_to_base64(path)
            }
        })

    content.append({"type": "text", "text": question})

    response = client.messages.create(
        model="claude-3-5-sonnet",
        max_tokens=1024,
        messages=[{"role": "user", "content": content}]
    )
    return response.content[0].text

# Usage
result = compare_images(
    ["before.png", "after.png"],
    "What are the differences between these two images?"
)
```

## 22.4 Image Analysis Use Cases

```python
class ImageAnalyzer:
    def __init__(self, client):
        self.client = client

    async def extract_text(self, image_path: str) -> str:
        """OCR - extract text from image"""
        return await self._analyze(image_path, "Extract all text from this image verbatim")

    async def describe_ui(self, screenshot_path: str) -> dict:
        """Analyze UI screenshot"""
        prompt = """Analyze this UI screenshot. Return JSON:
{
    "elements": [{"type": "button/input/text", "label": "...", "position": "..."}],
    "layout": "description of layout",
    "issues": ["any UX issues spotted"]
}"""
        result = await self._analyze(screenshot_path, prompt)
        return json.loads(result)

    async def analyze_chart(self, chart_path: str) -> dict:
        """Extract data from chart"""
        prompt = "Extract the data points and trends from this chart. Return as JSON."
        result = await self._analyze(chart_path, prompt)
        return json.loads(result)

    async def _analyze(self, path: str, prompt: str) -> str:
        response = await self.client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_to_base64(path)}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        return response.content[0].text
```

## 22.5 Document Understanding

```python
class DocumentProcessor:
    async def process_invoice(self, pdf_path: str) -> dict:
        prompt = """Extract from this invoice:
- Invoice number
- Date
- Vendor name
- Line items (description, quantity, price)
- Total amount
Return as JSON."""

        response = await client.messages.create(
            model="claude-3-5-sonnet",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_to_base64(pdf_path)}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        return json.loads(response.content[0].text)

    async def process_form(self, image_path: str) -> dict:
        prompt = "Extract all form fields and their values as JSON."
        # Similar implementation
        pass
```

## 22.6 Image Tokens and Cost

```python
# Image token estimation
def estimate_image_tokens(width: int, height: int) -> int:
    """Approximate token count for image"""
    # Images are resized to fit within limits
    max_size = 1568
    if width > max_size or height > max_size:
        scale = max_size / max(width, height)
        width = int(width * scale)
        height = int(height * scale)

    # ~750 tokens per 512x512 tile
    tiles = (width // 512 + 1) * (height // 512 + 1)
    return tiles * 750

# Cost-aware image processing
def should_resize(width: int, height: int, budget_tokens: int) -> tuple[int, int]:
    current_tokens = estimate_image_tokens(width, height)
    if current_tokens <= budget_tokens:
        return width, height

    scale = (budget_tokens / current_tokens) ** 0.5
    return int(width * scale), int(height * scale)
```

## 22.7 Best Practices

```python
# 1. Provide clear instructions
prompt = """Look at this screenshot and:
1. List all buttons visible
2. Identify the main call-to-action
3. Note any accessibility issues"""

# 2. Be specific about output format
prompt = "List items in this image as a bullet list, one per line"

# 3. Handle errors
async def safe_analyze(image_path: str) -> str:
    try:
        return await analyze_image(image_path)
    except anthropic.BadRequestError as e:
        if "image" in str(e).lower():
            return "Could not process image - may be corrupted or unsupported format"
        raise
```

## 22.8 Summary

| Capability | Use Cases |
|------------|-----------|
| Image analysis | UI review, photo description |
| OCR | Text extraction, form processing |
| Document | Invoice, contract, report analysis |
| Comparison | Before/after, diff detection |
| Charts | Data extraction from visuals |

**Best practices:**
- Resize large images to save tokens
- Be specific in prompts
- Use multiple images for comparison tasks
- Handle unsupported formats gracefully
- Consider token costs for high-volume
