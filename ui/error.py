from typing import Optional
from sdl2 import SDL_GetError

class UIError(RuntimeError):
    def __init__(self, message: Optional[str] = None):
        if message is None:
            buffer = SDL_GetError()
            message = buffer.decode('utf-8')
        super().__init__(message)
