import pytest
from unittest.mock import Mock, MagicMock, patch
from aicmd.providers.llamaserver import LlamaServerProvider
import httpx

@pytest.fixture
def provider():
    """Create a LlamaServerProvider instance for testing."""
    with patch('aicmd.providers.llamaserver.cfg_mod.load') as mock_load:
        mock_load.return_value = {
            'llamaserver_url': 'http://localhost:8000',
            'llamaserver_summarize_model': 'test-model',
            'llamaserver_max_tokens': 80,
        }
        return LlamaServerProvider()

def test_provider_initialization(provider):
    """Test that provider initializes with correct defaults."""
    assert provider.base_url == 'http://localhost:8000'
    assert provider.client is not None

def test_summarize_with_streaming(provider):
    """Test summarize method with streaming callback."""
    with patch.object(provider.client, 'stream') as mock_stream:
        # Mock SSE response
        sse_response = [
            'data: {"choices": [{"delta": {"content": "This"}}]}',
            'data: {"choices": [{"delta": {"content": " is"}}]}',
            'data: {"choices": [{"delta": {"content": " a"}}]}',
            'data: {"choices": [{"delta": {"content": " summary"}}]}',
            'data: [DONE]',
        ]
        
        mock_response = MagicMock()
        mock_response.iter_text.return_value = sse_response
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_stream.return_value = mock_response
        
        chunks = []
        def callback(chunk):
            chunks.append(chunk)
        
        result = provider.summarize("Test text", stream_callback=callback)
        
        # Verify the result
        assert result == "This is a summary"
        # Verify streaming callback was called
        assert chunks == ["This", " is", " a", " summary"]
        
        # Verify the request was made correctly
        mock_stream.assert_called_once()
        call_args = mock_stream.call_args
        assert call_args[0][0] == "POST"
        assert "v1/chat/completions" in call_args[0][1]

def test_chat_with_messages(provider):
    """Test chat method with message list."""
    with patch.object(provider.client, 'stream') as mock_stream:
        # Mock SSE response
        sse_response = [
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: {"choices": [{"delta": {"content": "!"}}]}',
            'data: [DONE]',
        ]
        
        mock_response = MagicMock()
        mock_response.iter_text.return_value = sse_response
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_stream.return_value = mock_response
        
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say hello"}
        ]
        
        result = provider.chat(messages)
        
        assert result == "Hello!"
        
        # Verify request structure
        call_args = mock_stream.call_args
        json_payload = call_args[1]['json']
        assert json_payload['messages'] == messages
        assert json_payload['stream'] is True

def test_rewrite_with_style(provider):
    """Test rewrite method with specific style."""
    with patch.object(provider.client, 'stream') as mock_stream:
        sse_response = [
            'data: {"choices": [{"delta": {"content": "Rewritten text"}}]}',
            'data: [DONE]',
        ]
        
        mock_response = MagicMock()
        mock_response.iter_text.return_value = sse_response
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_stream.return_value = mock_response
        
        result = provider.rewrite("Original text", style="formal")
        
        assert result == "Rewritten text"

def test_describe_image(provider):
    """Test image description with base64 encoding."""
    import tempfile
    import os
    
    # Create a temporary image file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        # Write minimal PNG header
        tmp.write(b'\x89PNG\r\n\x1a\n')
        tmp_path = tmp.name
    
    try:
        with patch.object(provider.client, 'stream') as mock_stream:
            sse_response = [
                'data: {"choices": [{"delta": {"content": "A picture"}}]}',
                'data: [DONE]',
            ]
            
            mock_response = MagicMock()
            mock_response.iter_text.return_value = sse_response
            mock_response.__enter__.return_value = mock_response
            mock_response.__exit__.return_value = None
            mock_stream.return_value = mock_response
            
            result = provider.describe_image(tmp_path)
            
            assert result == "A picture"
            
            # Verify that the image was encoded and sent
            call_args = mock_stream.call_args
            json_payload = call_args[1]['json']
            messages = json_payload['messages']
            # Check that image is in the message
            assert any('image' in str(m).lower() for m in messages)
    finally:
        os.unlink(tmp_path)

def test_sse_parsing_with_skip_lines(provider):
    """Test SSE parsing handles heartbeat and other lines correctly."""
    with patch.object(provider.client, 'stream') as mock_stream:
        sse_response = [
            ':heartbeat',
            '',
            'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            'data: [DONE]',
        ]
        
        mock_response = MagicMock()
        mock_response.iter_text.return_value = sse_response
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = None
        mock_stream.return_value = mock_response
        
        result = provider.summarize("Test")
        
        assert result == "Hello"
