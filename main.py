import sys
import os
import ctypes
from typing import Callable
from gray.vulkan import *
from ui.error import UIError
from ui.display import get_display_under_cursor

width = 1024
height = 768
title = 'GRay'

window = None
window_id = 0
vk_instance = None
vk_window_surface = None

vk_physical_device = None

def vk_select_physical_device_by_type(*priority_list, criteria=None, initial_priority=None):
    if not isinstance(vk_instance, int):
        raise UIError('vk_instance: not initialized')
    
    selected_device = None
    selected_device_properties = None
    selected_device_priority = initial_priority
    
    if initial_priority is None:
        initial_priority = len(priority_list)
    
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
    
    return (selected_device, selected_device_properties)

def main():
    global window, window_id, vk_instance, vk_physical_device
    if SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) < 0:
        raise UIError
    
    vk_version = vkEnumerateInstanceVersion()
    
    print(f'Vulkan Version: {VK_VERSION_MAJOR(vk_version)}.{VK_VERSION_MINOR(vk_version)}.{VK_VERSION_PATCH(vk_version)}')
    
    display_index = get_display_under_cursor()
    display_size = SDL_Rect()
    if SDL_GetDisplayUsableBounds(display_index, display_size) < 0:
        raise UIError

    window_position = [0] * 4
    if display_size.w * 0.9 < width:
        window_position[2] = int(display_size.w * 0.9)
    else:
        window_position[2] = width
    if window_position[3] * 0.9 < height:
        window_position[3] = int(display_size.h * 0.9)
    else:
        window_position[3] = height

    window_position[0] = display_size.x + (display_size.w - window_position[2]) // 2
    window_position[1] = display_size.y + (display_size.h - window_position[3]) // 2
    
    window = SDL_CreateWindow(str.encode(title, 'utf-8'), *window_position, SDL_WINDOW_SHOWN | SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_INPUT_FOCUS | SDL_WINDOW_MOUSE_FOCUS)
    if window is None:
        raise UIError
    
    SDL_SetWindowMinimumSize(window, 160, 90)
    
    window_id = SDL_GetWindowID(window)
    
    # Currently a window is required for Vulkan extensions enumeration:
    ext_count = ctypes.c_uint()
    if not SDL_Vulkan_GetInstanceExtensions(window, ext_count, None):
        raise UIError
    ext_array = ctypes.ARRAY(ctypes.c_char_p, ext_count.value)()
    if not SDL_Vulkan_GetInstanceExtensions(window, ext_count, ext_array):
        raise UIError
    
    ext_array = list(x for x in ext_array)
    
    vk_application_info = VkApplicationInfo(pApplicationName=b'GRay', applicationVersion=1, apiVersion=vk_version)
    vk_instance_create_info = VkInstanceCreateInfo(pApplicationInfo=vk_application_info, ppEnabledExtensionNames=ext_array)
    
    # Note: SDL2/Vulkan interoperability in python:
    # In C, vkCreateInstance call accepts vkInstance*. Since vkInstance is const void *, this is equivalent to const void **
    # which the address where the const void * of vkInstance is stored (this is opaque pointer).
    # As a result, the function will modify the pointer on successful return.
    
    # In python SDL2 operates with ctypes and define VkInstance as ctypes.c_void_p.
    # In python vulkan operates with `ffi` which creates opaque pointer object whose address cannot be retrieved.
    # The `ffi` is not interoperable with ctypes: giving `ctypes.c_void_p` will result in invalid argument.
    # However, `ffi` can create a pointer from `<class 'int'>`, so all `vk*` function that requires `vkInstance`,
    # must use `vk_instance.value`` instead of `vk_instance`.
    
    # vk_instance and vk_window_surface are the only interoperable object.
    # Any other vulkan object will use `ffi` pointer instead of `ctypes` pointer.
    vk_instance = VkInstance()
    vkCreateInstance(vk_instance_create_info, None, pInstance=ctypes.addressof(vk_instance))
    vk_instance = vk_instance.value
    
    vk_window_surface = VkSurfaceKHR()
    if not SDL_Vulkan_CreateSurface(window, vk_instance, vk_window_surface):
        raise UIError
    vk_window_surface = vk_window_surface.value
    
    selected_physical_device = None
    selected_physical_device_properties = None
    device_type_preference_list = [
        VkPhysicalDeviceType.DISCRETE_GPU,
        VkPhysicalDeviceType.INTEGRATED_GPU,
        VkPhysicalDeviceType.CPU
    ]
    
    print('Vulkan Physical Devices:')
    for device in vkEnumeratePhysicalDevices(vk_instance):
        device_properties = vkGetPhysicalDeviceProperties(device)
        print(f'    - {device_properties.deviceName}:')
        print(f'        API Version: {VK_VERSION_STRING(device_properties.apiVersion)}')
        print(f'        Driver Version: {VK_VERSION_STRING(device_properties.driverVersion)}')
        print('        VendorID: 0x%08X' % device_properties.vendorID)
        print('        DeviceID: 0x%08X' % device_properties.deviceID)
        print(f'        DeviceType: {VkPhysicalDeviceType(device_properties.deviceType).name}')
        
        try:
            device_priority_index = device_type_preference_list.index(device_properties.deviceType)
        except ValueError:
            continue
        
        selected_device_priority_index = -1
        if selected_physical_device is not None:
            try:
                selected_device_priority_index = device_type_preference_list.index(selected_physical_device_properties.deviceType)
            except ValueError:
                pass
        if selected_device_priority_index < 0 or device_priority_index < selected_device_priority_index:
            selected_physical_device = device
            selected_physical_device_properties = device_properties
            
    if selected_physical_device is None:
        raise UIError('Unable to find suitable Vulkan physical device')
    
    vk_physical_device = selected_physical_device
    print('Selected physical device:', selected_physical_device_properties.deviceName, f'({VkPhysicalDeviceType(selected_physical_device_properties.deviceType).name})')
    del selected_physical_device
    del selected_physical_device_properties
    del selected_device_priority_index
    del device_priority_index
    del device_type_preference_list
    
    desired_format_priority = [
        VkFormat.R32G32B32A32_SFLOAT,
        VkFormat.R32G32B32_SFLOAT,
        VkFormat.R8G8B8A8_SRGB,
        VkFormat.A8B8G8R8_SRGB_PACK32,
        VkFormat.R8G8B8_SRGB,
        VkFormat.B8G8R8_SRGB,
        VkFormat.R8G8B8A8_UNORM,
        VkFormat.R8G8B8_UNORM,
        VkFormat.B8G8R8_UNORM
    ]
    
    selected_format = None
    selected_format_priority = len(desired_format_priority)
    
    print('Supported format for the main window:')
    surface_formats = vk_extension_function(vk_instance).vkGetPhysicalDeviceSurfaceFormatsKHR(vk_physical_device, vk_window_surface)
    for surface_format in surface_formats:
        print(f'    - {VkFormat(surface_format.format).name}')
        vk_format = VkFormat(surface_format.format)
        try:
            priority_index = desired_format_priority.index(vk_format)
        except ValueError:
            continue
        if priority_index < selected_format_priority:
            selected_format = surface_format
            selected_format_priority = priority_index
    
    del vk_format
    del selected_format_priority

    # In order to create device we must first obtain the device queue family properties to find a queue family (graphics, compute, transfer, etc),
    # so we can allocate queues alongside logical device creation.
    
    # A logical device is of type vkDevice is created from vkPhysicalDevice.
    
    # Commands are send to the device into the queues.
    
    # vk_extension_function(vk_instance).
    
    while True:
        event = SDL_Event()
        if SDL_WaitEvent(event) == 0:
            raise UIError
        if event.type == SDL_QUIT:
            break
        if event.type == SDL_WINDOWEVENT:
            if event.window.windowID == window_id:
                if event.window.event == SDL_WINDOWEVENT_CLOSE:
                    break
    
    SDL_DestroyWindow(window)
    SDL_Quit()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
