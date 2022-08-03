import ctypes
from sdl2 import *
from ui.error import UIError


def get_display_bounds():
    display_count = SDL_GetNumVideoDisplays()
    if display_count <= 0:
        raise UIError
    display_bounds = []
    for index in range(display_count):
        rect = SDL_Rect()
        if SDL_GetDisplayBounds(index, rect) < 0:
            raise UIError
        display_bounds.append(rect)
    return display_bounds


def get_display_under_cursor():
    display_bounds = get_display_bounds()
    cx = ctypes.c_int(0)
    cy = ctypes.c_int(0)
    SDL_GetGlobalMouseState(cx, cy)
    for index in range(len(display_bounds)):
        rect = display_bounds[index]
        if cx.value >= rect.x and cx.value < rect.x + rect.w and cy.value >= rect.y and cy.value < rect.y + rect.h:
            return index
    if len(display_bounds) > 0:
        return 0
    raise UIError('No monitor(s) information found.')


__all__ = ['get_display_bounds', 'get_display_under_cursor']
