"""
Tests for backend functionality.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import aiohttp

from qwen_tui.backends.base import LLMBackend, LLMRequest, LLMResponse, BackendStatus
from qwen_tui.backends.manager import BackendManager
from qwen_tui.backends.ollama import OllamaBackend
from qwen_tui.backends.lm_studio import LMStudioBackend
from qwen_tui.config import Config, OllamaConfig, LMStudioConfig, BackendType
from qwen_tui.exceptions import BackendError, BackendConnectionError


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config()


@pytest.fixture
def ollama_config():
    """Create Ollama configuration for testing."""
    return OllamaConfig(
        host="localhost",
        port=11434,
        model="test-model"
    )


@pytest.fixture
def lm_studio_config():
    """Create LM Studio configuration for testing."""
    return LMStudioConfig(
        host="localhost",
        port=1234,
        api_key="test-key"
    )


class TestLLMRequest:
    """Test LLMRequest model."""
    
    def test_request_creation(self):
        """Test creating an LLM request."""
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest(messages=messages)
        
        assert request.messages == messages
        assert request.stream is True  # Default
        assert request.temperature is None  # Default
        assert request.max_tokens is None  # Default
        assert request.model is None  # Default
    
    def test_request_with_parameters(self):
        """Test creating an LLM request with parameters."""
        messages = [{"role": "user", "content": "Hello"}]
        request = LLMRequest(
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=100,
            model="test-model"
        )
        
        assert request.messages == messages
        assert request.stream is True
        assert request.temperature == 0.7
        assert request.max_tokens == 100
        assert request.model == "test-model"


class TestLLMResponse:
    """Test LLMResponse model."""
    
    def test_response_creation(self):
        """Test creating an LLM response."""
        response = LLMResponse(
            content="Hello, world!",
            finish_reason="stop"
        )
        
        assert response.content == "Hello, world!"
        assert response.finish_reason == "stop"
        assert response.is_partial is False  # Default
        assert response.delta is None  # Default
    
    def test_partial_response(self):
        """Test creating a partial response."""
        response = LLMResponse(
            content="Hello",
            delta=" world",
            is_partial=True,
            finish_reason=None
        )
        
        assert response.content == "Hello"
        assert response.delta == " world"
        assert response.is_partial is True
        assert response.finish_reason is None


class TestBackendManager:
    """Test BackendManager functionality."""
    
    def test_manager_creation(self, config):
        """Test creating a backend manager."""
        manager = BackendManager(config)
        
        assert manager.config == config
        assert manager.backends == {}
        assert manager.backend_pool is None
    
    @pytest.mark.asyncio
    async def test_manager_initialization_mock(self, config):
        """Test backend manager initialization with mocked backends."""
        manager = BackendManager(config)
        
        # Mock the backend creation methods
        with patch.object(manager, '_create_ollama_backend') as mock_ollama, \
             patch.object(manager, '_create_lm_studio_backend') as mock_lm_studio:
            
            # Mock successful backend creation
            mock_backend = Mock()
            mock_backend.test_connection = AsyncMock(return_value={"success": True})
            mock_ollama.return_value = mock_backend
            mock_lm_studio.return_value = None  # LM Studio not available
            
            await manager.initialize()
            
            assert BackendType.OLLAMA in manager.backends
            assert BackendType.LM_STUDIO not in manager.backends
    
    def test_get_preferred_backend_empty(self, config):
        """Test getting preferred backend when none are available."""
        manager = BackendManager(config)
        
        preferred = manager.get_preferred_backend()
        assert preferred is None
    
    @pytest.mark.asyncio
    async def test_backend_info_generation(self, config):
        """Test getting backend information."""
        manager = BackendManager(config)
        
        # Add a mock backend
        mock_backend = Mock()
        backend_info_mock = Mock()
        backend_info_mock.name = "test-backend"
        backend_info_mock.backend_type = "ollama"
        backend_info_mock.status = Mock()
        backend_info_mock.status.value = "available"
        backend_info_mock.host = "localhost"
        backend_info_mock.port = 11434
        backend_info_mock.model = "test-model"
        backend_info_mock.version = "1.0"
        backend_info_mock.capabilities = ["chat"]
        backend_info_mock.last_check = "now"
        backend_info_mock.error_message = None
        mock_backend.get_info = AsyncMock(return_value=backend_info_mock)
        mock_backend.name = "test-backend"
        mock_backend.backend_type = "ollama"
        manager.backends[BackendType.OLLAMA] = mock_backend
        
        info = await manager.get_backend_info()
        
        assert BackendType.OLLAMA in info
        assert info[BackendType.OLLAMA]["name"] == "test-backend"


class TestOllamaBackend:
    """Test Ollama backend functionality."""
    
    def test_ollama_backend_creation(self, ollama_config):
        """Test creating an Ollama backend."""
        backend = OllamaBackend(ollama_config)
        
        assert backend.backend_type == "ollama"
        assert backend.ollama_config == ollama_config
        assert backend.base_url == "http://localhost:11434"
        assert backend.session is None
    
    @pytest.mark.asyncio
    async def test_ollama_initialization_success(self, ollama_config):
        """Test successful Ollama backend initialization."""
        backend = OllamaBackend(ollama_config)
        
        # Mock successful HTTP responses
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"models": []})
            
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            await backend.initialize()
            
            assert backend.session == mock_session
            assert backend.status == BackendStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_ollama_health_check(self, ollama_config):
        """Test Ollama health check."""
        backend = OllamaBackend(ollama_config)
        
        # Mock the session and response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status = 200
        # Use AsyncMock for context manager
        mock_get = AsyncMock()
        mock_get.__aenter__.return_value = mock_response
        mock_get.__aexit__.return_value = None
        mock_session.get.return_value = mock_get
        backend.session = mock_session
        
        result = await backend.health_check()
        
        assert result is True
        assert backend.status == BackendStatus.AVAILABLE
    
    @pytest.mark.asyncio
    async def test_ollama_health_check_failure(self, ollama_config):
        """Test Ollama health check failure."""
        backend = OllamaBackend(ollama_config)
        
        # Mock the session and failed response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status = 500
        mock_get = AsyncMock()
        mock_get.__aenter__.return_value = mock_response
        mock_get.__aexit__.return_value = None
        mock_session.get.return_value = mock_get
        backend.session = mock_session
        
        result = await backend.health_check()
        
        assert result is False
        assert backend.status == BackendStatus.UNAVAILABLE
    
    @pytest.mark.asyncio
    async def test_ollama_cleanup(self, ollama_config):
        """Test Ollama backend cleanup."""
        backend = OllamaBackend(ollama_config)
        
        # Mock session
        mock_session = Mock()
        mock_session.close = AsyncMock()
        backend.session = mock_session
        
        await backend.cleanup()
        
        assert backend.session is None
        assert backend.status == BackendStatus.DISCONNECTED
        mock_session.close.assert_called_once()


class TestLMStudioBackend:
    """Test LM Studio backend functionality."""
    
    def test_lm_studio_backend_creation(self, lm_studio_config):
        """Test creating an LM Studio backend."""
        backend = LMStudioBackend(lm_studio_config)
        
        assert backend.backend_type == "lm_studio"
        assert backend.lm_studio_config == lm_studio_config
        assert backend.base_url == "http://localhost:1234/v1"
        assert backend.session is None
    
    @pytest.mark.asyncio
    async def test_lm_studio_initialization(self, lm_studio_config):
        """Test LM Studio backend initialization."""
        backend = LMStudioBackend(lm_studio_config)
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"data": []})
            
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session
            
            await backend.initialize()
            
            assert backend.session == mock_session
            assert backend.status == BackendStatus.CONNECTED
    
    @pytest.mark.asyncio
    async def test_lm_studio_model_refresh(self, lm_studio_config):
        """Test LM Studio model cache refresh."""
        backend = LMStudioBackend(lm_studio_config)
        
        # Mock session and response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": [
                {"id": "model1", "object": "model"},
                {"id": "model2", "object": "model"}
            ]
        })
        mock_get = AsyncMock()
        mock_get.__aenter__.return_value = mock_response
        mock_get.__aexit__.return_value = None
        mock_session.get.return_value = mock_get
        backend.session = mock_session
        
        await backend._refresh_model_cache()
        
        assert len(backend._available_models) == 2
        assert backend._current_model == "model1"  # First model becomes current


class TestErrorHandling:
    """Test error handling in backends."""
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, ollama_config):
        """Test handling of connection errors."""
        backend = OllamaBackend(ollama_config)
        
        # Mock session that raises connection error
        mock_session = Mock()
        mock_session.get.side_effect = aiohttp.ClientError("Connection failed")
        backend.session = mock_session
        
        result = await backend.health_check()
        assert result is False
        assert backend.status == BackendStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_model_not_found_error(self, ollama_config):
        """Test handling of model not found errors."""
        backend = OllamaBackend(ollama_config)
        
        # Test the improved error message for model not found
        request = LLMRequest(
            messages=[{"role": "user", "content": "test"}],
            model="nonexistent-model"
        )
        
        # Mock session
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value='{"error":"model \\"nonexistent-model\\" not found"}')
        
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=None)
        backend.session = mock_session
        
        # Mock get_available_models to return empty list
        backend.get_available_models = AsyncMock(return_value=["model1", "model2"])
        
        with pytest.raises(BackendError) as exc_info:
            async for _ in backend.generate(request):
                pass
        
        error_message = str(exc_info.value)
        assert "not found" in error_message
        assert "Available models:" in error_message


@pytest.mark.integration
class TestIntegration:
    """Integration tests (require actual services)."""
    
    @pytest.mark.asyncio
    async def test_full_backend_flow(self, config):
        """Test full backend initialization and discovery flow."""
        manager = BackendManager(config)
        
        try:
            # This test will only pass if actual backends are running
            await manager.initialize()
            
            available_backends = manager.get_available_backends()
            
            if available_backends:
                # Test getting models from available backends
                all_models = await manager.get_all_models()
                assert isinstance(all_models, dict)
                
                # Test backend info
                backend_info = await manager.get_backend_info()
                assert isinstance(backend_info, dict)
                
        except Exception as e:
            # Skip if no backends are available
            pytest.skip(f"No backends available for integration test: {e}")
        
        finally:
            await manager.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])