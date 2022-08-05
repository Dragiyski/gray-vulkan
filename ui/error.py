from typing import Optional, Union
from sdl2 import SDL_GetError

class UIError(RuntimeError):
    def __init__(self, message: Optional[Union[str, bytes]] = None):
        if message is None:
            message = SDL_GetError()
        if isinstance(message, bytes):
            message = message.decode('utf-8')
        super().__init__(message)
