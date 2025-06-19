import pytest
from qwen_tui.tui.thinking import ThinkingManager
from qwen_tui.backends.manager import BackendManager
from qwen_tui.config import Config
from qwen_tui.backends.base import LLMResponse, LLMRequest

class DummyProtocolClient:
    async def generate(self, request: LLMRequest):
        # Simulate streaming with think tags
        yield LLMResponse(is_partial=True, delta="<think>Hidden</think>")
        yield LLMResponse(content="Visible reply", is_partial=False)

@pytest.mark.asyncio
async def test_protocol_think_tags_hidden():
    config = Config()
    backend_manager = BackendManager(config)
    client = DummyProtocolClient()
    manager = ThinkingManager(backend_manager, config, protocol_client=client)

    chunks = []
    async for chunk in manager.think_and_respond("Hello"):
        chunks.append(chunk)

    result = "".join(chunks)
    state = manager.get_thinking_state()

    assert "<think>" not in result
    assert "Hidden" in state.full_thoughts

