import threading

_imported = list(locals().keys())

window = None
window_id = 0
window_in_focus = threading.Event()

vk_instance = None
vk_instance_extensions = None
vk_surface = None
vk_physical_device = None
vk_device = None
vk_queue_family_index = None

draw_thread = None
draw_loop_continue = True

_locals = list(locals().keys())
__all__ = list(x for x in _locals if not x.startswith('_') and x not in _imported)
