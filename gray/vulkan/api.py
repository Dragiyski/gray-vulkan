import ctypes
from ctypes.util import find_library

lib_name = find_library('vulkan')

if lib_name is None:
    raise ImportError('find_library: vulkan library not found')

lib = ctypes.CDLL(lib_name)

class Version:
    def __init__(self, value):
        if isinstance(value, int):
            version = value
        elif hasattr(value, 'value') and isinstance(value.value, int):
            version = value.value
        else:
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            if isinstance(value, str):
                version_items = list(int(x) for x in value.split('.'))
                if len(version_items) > 4:
                    raise ValueError('version: too many numbers')
                offset = 0
                if len(version_items) == 4:
                    variant = version_items[0]
                    offset = 1
                    if variant < 0 or variant >= 8:
                        raise ValueError('version.varant: not in range [0-7]')
                else:
                    variant = 0
                if len(version_items) >= 3:
                    patch = version_items[offset + 2]
                    if patch < 0 or patch > 0xFFF:
                        raise ValueError(f'version.patch: not in range [0-{0xFFF}]')
                else:
                    path = 0
                if len(version_items) >= 2:
                    minor = version_items[offset + 1]
                    if minor < 0 or minor > 0x3FF:
                        raise ValueError(f'version.minor: not in range [0-{0x3FF}]')
                else:
                    minor = 0
                if len(version_items) >= 1:
                    major = version_items[offset]
                    if major < 0 or major > 0x7F:
                        raise ValueError(f'version.major: not in range [0-{0x7F}]')
                else:
                    major = 0
                version = variant << 29 | major << 22 | minor << 12 | patch
            else:
                raise ValueError(f'value: not valid version: expected (int, string, bytes), got ({type(value)})')
        self.__version = self._as_parameter_ = version

    @property
    def variant(self):
        return self.__version >> 29
    
    @property
    def major(self):
        return (self.__version >> 22) & 0x7F

    @property
    def minor(self):
        return (self.__version >> 12) & 0x3FF
    
    @property
    def patch(self):
        return self.__version & 0xFFF

    def __str__(self):
        if self.variant > 0:
            return f'{self.variant}.{self.major}.{self.minor}.{self.patch}'
        return f'{self.major}.{self.minor}.{self.patch}'

    def __repr__(self):
        return f'{self.__class__.__name__}("{self.__str__()}")'

    def __int__(self):
        return self.__version


class VulkanError(RuntimeError):
    pass

class VkOutOfHostMemory(VulkanError):
    pass

error_codes = {
    -1: VkOutOfHostMemory
}

def validate_result(result):
    if result != 0:
        if result in error_codes:
            raise error_codes[result](*args, **kwargs)
        raise VulkanError(result)


def vk_enumerate_instance_version():
    version = ctypes.c_uint32()
    result = lib.vkEnumerateInstanceVersion(ctypes.pointer(version))
    validate_result(result)
    return Version(version)

if __name__ == '__main__':
    print(vk_enumerate_instance_version())
