import vulkan.vulkan_build
from os import path

HERE = path.dirname(path.realpath(__file__))

with open(path.join(HERE, 'vk-khr-present-id.cdef.h')) as file:
    vk_khr_present_id = file.read()

vulkan.vulkan_build.ffi.cdef(vk_khr_present_id)

with open(path.join(HERE, 'vk-khr-present-wait.cdef.h')) as file:
    vk_khr_present_wait = file.read()

vulkan.vulkan_build.ffi.cdef(vk_khr_present_wait)
vulkan.vulkan_build.ffi.compile(tmpdir=path.dirname(path.dirname(vulkan.vulkan_build.__file__)))
