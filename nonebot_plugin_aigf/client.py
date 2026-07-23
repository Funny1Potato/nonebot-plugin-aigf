import re

from openai import AsyncOpenAI


class LLMClient:
    def __init__(self, client: AsyncOpenAI):
        self.client = client

    async def generate_response(self, prompt: str, model: str, images: list[str] | None = None) -> str | None:
        if images:
            content = [{"type": "text", "text": prompt}]
            for img_b64 in images:
                content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})
            messages = [{"role": "user", "content": content}]
        else:
            messages = [{"role": "user", "content": prompt}]

        response = await self.client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=0.5,
            timeout=300,
        )
        content = response.choices[0].message.content
        if content:
            return remove_leading_think(content)
        else:
            return None


def remove_leading_think(text: str) -> str:
    pattern = r"^(?:\s*<think>(.*?)</think>\s*|\s*<think\s*/?>\s*)+"
    return re.sub(pattern, "", text, flags=re.DOTALL).lstrip()
