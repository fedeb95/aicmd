import pytest
from aicmd import services, providers

class DummyProvider:
    def __init__(self):
        self.received = []
    def chat(self, messages, *, model=None, max_tokens=256, timeout=60, stream_callback=None):
        # simple echo of last user message
        last = ""
        for m in messages:
            if m.get('role') == 'user':
                last = m.get('content', last)
        resp = f"ECHO: {last}"
        if stream_callback:
            # simulate streaming
            for i in range(0, len(resp), 8):
                stream_callback(resp[i:i+8])
            return resp
        return resp
    def summarize(self, text, *, model=None, max_tokens=256, timeout=60, stream_callback=None):
        s = f"SUMMARIZE: {text}"
        if stream_callback:
            stream_callback(s)
        return s

@pytest.fixture(autouse=True)
def patch_provider(monkeypatch):
    dummy = DummyProvider()
    monkeypatch.setattr(providers, 'get_provider', lambda name: dummy)
    return dummy

def test_create_and_append_chat():
    cid = services.create_chat()
    assert cid in [*services._chats.keys()]
    services.append_message(cid, 'user', 'hello')
    history = services.get_chat_history(cid)
    assert history[-1]['content'] == 'hello'

def test_send_chat_message_with_chat_id(patch_provider):
    dummy = patch_provider
    cid = services.create_chat()
    cid2, reply = services.send_chat_message(cid, 'hi there')
    assert cid == cid2
    assert reply.startswith('ECHO:')
    hist = services.get_chat_history(cid)
    assert hist[-2]['role'] == 'user'
    assert hist[-1]['role'] == 'assistant'

def test_send_chat_message_new_chat(patch_provider):
    dummy = patch_provider
    cid, reply = services.send_chat_message(None, 'new chat message')
    assert cid in [*services._chats.keys()]
    assert reply.startswith('ECHO:')

def test_streaming_callback(patch_provider):
    dummy = patch_provider
    cid = services.create_chat()
    acc = []
    def cb(chunk):
        acc.append(chunk)
    cid2, reply = services.send_chat_message(cid, 'stream me', stream_callback=cb)
    assert cid == cid2
    # streaming should have provided chunks
    assert acc
    assert isinstance(reply, str)
