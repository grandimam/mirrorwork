# Module 27: Image Generation

## 27.1 DALL-E Basics

```python
from openai import OpenAI

client = OpenAI()

# Generate image
response = client.images.generate(
    model="dall-e-3",
    prompt="A serene mountain landscape at sunset, digital art",
    size="1024x1024",
    quality="standard",  # or "hd"
    n=1
)

image_url = response.data[0].url
print(image_url)

# Save locally
import requests

img_data = requests.get(image_url).content
with open("generated.png", "wb") as f:
    f.write(img_data)
```

## 27.2 Image Variations

```python
# Create variation of existing image
with open("original.png", "rb") as f:
    response = client.images.create_variation(
        model="dall-e-2",
        image=f,
        n=2,
        size="1024x1024"
    )

for i, img in enumerate(response.data):
    print(f"Variation {i}: {img.url}")
```

## 27.3 Image Editing

```python
# Edit image with mask
with open("image.png", "rb") as image_file:
    with open("mask.png", "rb") as mask_file:
        response = client.images.edit(
            model="dall-e-2",
            image=image_file,
            mask=mask_file,
            prompt="A red sports car parked in the area",
            n=1,
            size="1024x1024"
        )

edited_url = response.data[0].url
```

## 27.4 Prompt Engineering for Images

```python
class ImagePromptBuilder:
    def __init__(self):
        self.components = {
            "subject": "",
            "style": "",
            "lighting": "",
            "composition": "",
            "mood": "",
            "details": []
        }

    def subject(self, desc: str):
        self.components["subject"] = desc
        return self

    def style(self, style: str):
        # digital art, oil painting, watercolor, photorealistic, anime, etc.
        self.components["style"] = style
        return self

    def lighting(self, lighting: str):
        # golden hour, studio lighting, dramatic shadows, etc.
        self.components["lighting"] = lighting
        return self

    def composition(self, comp: str):
        # close-up, wide shot, bird's eye view, etc.
        self.components["composition"] = comp
        return self

    def mood(self, mood: str):
        # serene, dramatic, whimsical, dark, etc.
        self.components["mood"] = mood
        return self

    def add_detail(self, detail: str):
        self.components["details"].append(detail)
        return self

    def build(self) -> str:
        parts = []
        if self.components["subject"]:
            parts.append(self.components["subject"])
        if self.components["style"]:
            parts.append(f"in {self.components['style']} style")
        if self.components["lighting"]:
            parts.append(f"with {self.components['lighting']}")
        if self.components["composition"]:
            parts.append(f"{self.components['composition']}")
        if self.components["mood"]:
            parts.append(f"{self.components['mood']} mood")
        if self.components["details"]:
            parts.append(", ".join(self.components["details"]))

        return ", ".join(parts)

# Usage
prompt = (ImagePromptBuilder()
    .subject("A futuristic city skyline")
    .style("cyberpunk digital art")
    .lighting("neon lights and rain")
    .composition("wide shot")
    .mood("atmospheric")
    .add_detail("flying cars")
    .add_detail("holographic billboards")
    .build())
```

## 27.5 Stable Diffusion (Local)

```python
from diffusers import StableDiffusionPipeline
import torch

# Load model
pipe = StableDiffusionPipeline.from_pretrained(
    "stabilityai/stable-diffusion-2-1",
    torch_dtype=torch.float16
)
pipe = pipe.to("cuda")

# Generate
image = pipe(
    prompt="A beautiful sunset over mountains",
    negative_prompt="blurry, low quality",
    num_inference_steps=50,
    guidance_scale=7.5
).images[0]

image.save("output.png")

# With more control
image = pipe(
    prompt="Portrait of a warrior",
    negative_prompt="deformed, ugly, blurry",
    height=768,
    width=512,
    num_inference_steps=30,
    guidance_scale=8.0,
    generator=torch.Generator("cuda").manual_seed(42)
).images[0]
```

## 27.6 Image Generation Pipeline

```python
class ImageGenerator:
    def __init__(self):
        self.openai = OpenAI()

    async def generate_with_refinement(self, concept: str) -> dict:
        # 1. Enhance prompt with LLM
        enhanced_prompt = await self._enhance_prompt(concept)

        # 2. Generate image
        response = self.openai.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            size="1024x1024"
        )

        return {
            "original_concept": concept,
            "enhanced_prompt": enhanced_prompt,
            "image_url": response.data[0].url,
            "revised_prompt": response.data[0].revised_prompt
        }

    async def _enhance_prompt(self, concept: str) -> str:
        response = await anthropic_client.messages.create(
            model="claude-3-haiku",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Create a detailed image generation prompt for: {concept}

Include: subject, style, lighting, composition, mood, specific details.
Return only the prompt, no explanation."""
            }]
        )
        return response.content[0].text
```

## 27.7 Batch Generation

```python
async def generate_variations(base_prompt: str, variations: list[str]) -> list:
    """Generate multiple images with prompt variations"""
    results = []

    for var in variations:
        full_prompt = f"{base_prompt}, {var}"
        response = await client.images.generate(
            model="dall-e-3",
            prompt=full_prompt,
            size="1024x1024"
        )
        results.append({
            "variation": var,
            "url": response.data[0].url
        })

    return results

# Usage
variations = await generate_variations(
    "A cozy coffee shop interior",
    ["modern minimalist", "rustic vintage", "japanese zen", "industrial loft"]
)
```

## 27.8 Summary

| Model | Best For |
|-------|----------|
| DALL-E 3 | High quality, prompt following |
| DALL-E 2 | Variations, editing |
| Stable Diffusion | Local, customizable |
| Midjourney | Artistic, stylized |

**Best practices:**
- Write detailed, specific prompts
- Include style, lighting, composition
- Use negative prompts to avoid issues
- Generate multiple and select best
- Save prompts that work well
- Consider cost for high volume
