import vulkan
from enum import Enum, IntEnum, IntFlag
from sdl2 import *
from sdl2.vulkan import *
from sdl2.vulkan import VkSurfaceKHR, VkInstance
from vulkan import *


def VK_VERSION_STRING(version):
    return f'{VK_VERSION_MAJOR(version)}.{VK_VERSION_MINOR(version)}.{VK_VERSION_PATCH(version)}'


keys = list(locals().keys())

__all__ = list(key for key in keys if not key.startswith('_'))


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
