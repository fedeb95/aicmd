from abc import ABC, abstractmethod
from typing import Optional

class Provider(ABC):
    @abstractmethod
    def summarize(self, text: str, *, model: Optional[str] = None, max_tokens: int = 256, timeout: int = 60) -> str:
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
