import gray.vulkan.build
import vulkan
from enum import Enum, IntEnum, IntFlag
from sdl2 import *
from sdl2.vulkan import *
from sdl2.vulkan import VkSurfaceKHR, VkInstance
from vulkan import *
from vulkan._vulkan import _new as vulkan_new_type, _instance_ext_funcs as vulkan_instance_ext_funcs, _callApi as vulkan_call_api
import ctypes
from ui.error import UIError


def VK_VERSION_STRING(version):
    return f'{VK_VERSION_MAJOR(version)}.{VK_VERSION_MINOR(version)}.{VK_VERSION_PATCH(version)}'


_keys = list(locals().keys())
__all__ = list(key for key in _keys if not key.startswith('_'))


_prefix = 'VK_PHYSICAL_DEVICE_TYPE_'
VkPhysicalDeviceType = IntEnum('VkPhysicalDeviceType', dict(list((x[len(_prefix):], getattr(vulkan, x)) for x in dir(vulkan) if x.startswith(_prefix) and x[len(_prefix):][0] != '_' and isinstance(getattr(vulkan, x), int))))
__all__.append('VkPhysicalDeviceType')

_prefix = 'VK_FORMAT_'
VkFormat = IntEnum('VkFormat', dict(list((x[len(_prefix):], getattr(vulkan, x)) for x in dir(vulkan) if x.startswith(_prefix) and x[len(_prefix):][0] != '_' and isinstance(getattr(vulkan, x), int))))
__all__.append('VkFormat')

_prefix = 'VK_COLOR_SPACE_'
VkColorSpaceKHR = IntEnum('VkColorSpaceKHR', dict(list((x[len(_prefix):], getattr(vulkan, x)) for x in dir(vulkan) if x.startswith(_prefix) and x[len(_prefix):][0] != '_' and len(x.split('__')) < 2 and isinstance(getattr(vulkan, x), int))))
__all__.append('VkColorSpaceKHR')

_prefix = 'VK_QUEUE_'
VkQueueFlagBits = IntFlag('VkQueueFlagBits', dict(list((x[len(_prefix):], getattr(vulkan, x)) for x in dir(vulkan) if x.startswith(_prefix) and x[len(_prefix):][0] != '_' and len(x.split('__')) < 2 and len(x.split('_BIT')) > 1 and isinstance(getattr(vulkan, x), int))))
__all__.append('VkQueueFlagBits')


class _Vk_Extension_Loader:
    def __init__(self, instance):
        self.__instance = instance

    def __getattr__(self, name):
        try:
            procedure = vkGetInstanceProcAddr(self.__instance, name)
        except (ProcedureNotFoundError, ExtensionNotSupportedError):
            raise AttributeError(obj=self, name=name)
        setattr(self, name, procedure)
        return procedure


_vk_extension_loaders = dict()


def vk_extension_function(instance):
    import ctypes
    if isinstance(instance, ctypes.c_void_p):
        instance = instance.value
    elif not isinstance(instance, int):
        raise ValueError('Argument "instance" must be `ctypes.c_void_p` or `int`')
    if instance not in _vk_extension_loaders:
        _vk_extension_loaders[instance] = _Vk_Extension_Loader(instance)
    return _vk_extension_loaders[instance]


__all__.append('vk_extension_function')

__all__.append('sdl_get_instance_extensions')


def sdl_get_instance_extensions(window):
    count = ctypes.c_uint()
    if not SDL_Vulkan_GetInstanceExtensions(window, count, None):
        raise UIError
    if count.value == 0:
        return []
    c_extensions = ctypes.ARRAY(ctypes.c_char_p, count.value)()
    if not SDL_Vulkan_GetInstanceExtensions(window, count, c_extensions):
        raise UIError
    return list(x.decode('utf-8') for x in c_extensions)


__all__.append('vk_select_physical_device_by_type')


def vk_select_physical_device_by_type(vk_instance, priority_list=None, criteria=None, initial_priority=None):
    if not isinstance(vk_instance, int):
        raise UIError('vk_instance: not initialized')
    if priority_list is None:
        priority_list = []
    if initial_priority is None:
        initial_priority = len(priority_list)
    selected_device = None
    selected_device_properties = None
    selected_device_priority = initial_priority
    if criteria is None and len(priority_list) <= 0:
        raise ValueError('priority_list is empty: if criteria is not specified, at least one argument is required')
    for physical_device in vkEnumeratePhysicalDevices(vk_instance):
        physical_device_properties = vkGetPhysicalDeviceProperties(physical_device)
        priority_index = initial_priority
        try:
            priority_index = priority_list.index(physical_device_properties.deviceType)
        except ValueError:
            pass
        if callable(criteria):
            priority_index = criteria(physical_device, physical_device_properties, priority_index)
        if priority_index < selected_device_priority:
            selected_device = physical_device
            selected_device_properties = physical_device_properties
            selected_device_priority = priority_index
    if selected_device is None:
        raise LookupError('select_physical_device_by_type: unable to find physical device matching desired criteria')
    return selected_device


__all__.append('vk_select_queue_family_index')


def vk_select_queue_family_index(vk_physical_device, flags):
    families = vkGetPhysicalDeviceQueueFamilyProperties(vk_physical_device)
    for index in range(len(families)):
        family = families[index]
        if family.queueCount > 0 and (family.queueFlags & flags) == flags:
            return index
    raise LookupError(f'select_queue_family_index: unable to find queue family that supports: {VkQueueFlagBits(flags)}')


__all__.append('vk_select_surface_format')


def vk_select_surface_format(vk_instance, vk_physical_device, vk_surface, priority_list=[], criteria=None, initial_priority=None):
    if initial_priority is None:
        initial_priority = len(priority_list)

    selected_surface_format = None
    selected_priority = initial_priority

    for surface_format in vk_extension_function(vk_instance).vkGetPhysicalDeviceSurfaceFormatsKHR(vk_physical_device, vk_surface):
        priority_index = initial_priority
        try:
            priority_index = priority_list.index(surface_format.format)
        except ValueError:
            pass
        if callable(criteria):
            priority_index = criteria(surface_format, priority_index)
        if priority_index < selected_priority:
            selected_priority = priority_index
            selected_surface_format = surface_format

    if selected_surface_format is None:
        raise LookupError('select_surface_format: unable to find surface format matching desired criteria')

    return VkFormat(selected_surface_format.format), VkColorSpaceKHR(selected_surface_format.colorSpace)

__all__.append('VK_STRUCTURE_TYPE_PRESENT_ID_KHR')
VK_STRUCTURE_TYPE_PRESENT_ID_KHR = 1000294000

__all__.append('VkPresentIdKHR')
def VkPresentIdKHR(sType=VK_STRUCTURE_TYPE_PRESENT_ID_KHR, pNext=None, swapchainCount=None, pPresentIds=None):
    if swapchainCount is None and pPresentIds is not None:
        swapchainCount = len(pPresentIds)
    
    return vulkan_new_type('VkPresentIdKHR', sType=sType, pNext=pNext, swapchainCount=swapchainCount, pPresentIds=pPresentIds)

def _wrap_vkWaitForPresentKHR(fn):
    def vkWaitForPresentKHR(device, swapchain, presentId, timeout):
        result = vulkan_call_api(fn, device, swapchain, presentId, timeout)
        if result != VK_SUCCESS:
            raise exception_codes[result]
    
    return vkWaitForPresentKHR

vulkan_instance_ext_funcs['vkWaitForPresentKHR'] = _wrap_vkWaitForPresentKHR
