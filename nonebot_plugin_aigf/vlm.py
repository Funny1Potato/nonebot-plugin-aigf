from openai import AsyncOpenAI


class VLM:
    def __init__(self, api_key: str, model: str = "Pro/Qwen/Qwen2.5-VL-7B-Instruct",
                 base_url: str = "https://api.siliconflow.cn/v1", timeout: int = 60):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.timeout = timeout

    async def request(self, prompt: str, image_base64: str, image_format: str) -> str | None:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/{image_format};base64,{image_base64}"}},
                {"type": "text", "text": prompt},
            ]}],
            timeout=self.timeout,
        )
        return response.choices[0].message.content
