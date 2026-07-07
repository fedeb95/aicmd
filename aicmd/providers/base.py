from abc import ABC, abstractmethod
from typing import Optional, List, Dict

class Provider(ABC):
    @abstractmethod
    def summarize(self, text: str, *, model: Optional[str] = None, max_tokens: int = 256, timeout: int = 60, stream_callback = None) -> str:
        """Return a concise summary of *text*.
        Implementations should raise an exception on failure.
        """
        ...
    @abstractmethod
    def describe_image(self, image_path: str, *, model: Optional[str] = None, max_tokens: int = 256, timeout: int = 60) -> str:
        """Describe an image located at *image_path*.
        Implementations should raise an exception on failure.
        """
        ...
    @abstractmethod
    def rewrite(self, text: str, style: str, *, model: Optional[str] = None, max_tokens: int = 256, timeout: int = 60, stream_callback = None) -> str:
        """Rewrite *text* in the specified *style*.
        Implementations should raise an exception on failure.
        """
        ...

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], *, model: Optional[str] = None, max_tokens: int = 256, timeout: int = 60, stream_callback = None) -> str:
        """Start/continue a chat given a list of messages.

        Messages is a list of dicts with keys: 'role' (system/user/assistant) and 'content'.
        Implementations should return the assistant reply as a string. If stream_callback is provided,
        implementations should invoke it with partial chunks when available.
        """
        ...
