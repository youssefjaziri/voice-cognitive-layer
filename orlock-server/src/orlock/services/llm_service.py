from orlock.providers.llm_client import LocalLLMClient
from orlock.schemas.llm import MessageToLLMRequest

class LLMService:
    def __init__(self):
        self.client = LocalLLMClient()

    def message_to_llm(self, payload: MessageToLLMRequest, model: str = None) -> str:
        # If history exists, do chat; else do generate
        if payload.history:
            messages = []
            if payload.system:
                messages.append({"role": "system", "content": payload.system})
            messages.extend([m.model_dump() for m in payload.history])
            messages.append({"role": "user", "content": payload.prompt})

            return self.client.chat(messages, temperature=payload.temperature, model=model)

        return self.client.generate(
            payload.prompt, system=payload.system,
            temperature=payload.temperature, model=model
        )

    def message_to_llm_text(self, prompt: str, system: str = None,
                            temperature: float = 0.2, model: str = None) -> str:
        """Text-to-text LLM call. Accepts optional model override for routing."""
        return self.client.generate(prompt, system=system, temperature=temperature, model=model)