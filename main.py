import sys
import os
import ctypes
import threading
import ui
from traceback import print_exc
from typing import Callable
from gray.vulkan import *
from ui.error import UIError
from ui.display import get_display_under_cursor
from ui.draw import main as draw_main

width = 1024
height = 768
title = 'GRay'


def select_surface_format(*priority_list, criteria=None, initial_priority=None):
    if not isinstance(vk_instance, int):
        raise UIError('vk_instance: not initialized')

    if initial_priority is None:
        initial_priority = len(priority_list)

    selected_surface_format = None
    selected_priority = initial_priority

    for surface_format in vk_extension_function(vk_instance).vkGetPhysicalDeviceSurfaceFormatsKHR(vk_physical_device, vk_window_surface):
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


def select_queue_family_index(flags):
    families = vkGetPhysicalDeviceQueueFamilyProperties(vk_physical_device)
    for index in range(len(families)):
        family = families[index]
        if family.queueCount > 0 and (family.queueFlags & flags) == flags:
            return index

    raise LookupError(f'select_queue_family_index: unable to find queue family that supports: {VkQueueFlagBits(flags)}')


def main():
    global window, window_id, vk_instance, vk_window_surface, vk_physical_device, vk_physical_device_properties, vk_window_surface_image_format, vk_window_surface_image_color_space, vk_queue_family_index, vk_device, draw_loop_run, draw_loop_need_resize, draw_thread, draw_need_resize
    if SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) < 0:
        raise UIError

    vk_version = vkEnumerateInstanceVersion()
    if __debug__:
        print(f'vkEnumerateInstanceVersion() = {VK_VERSION_STRING(vk_version)}', file=sys.stderr)

    display_index = get_display_under_cursor()
    display_size = SDL_Rect()
    try:
        if SDL_GetDisplayUsableBounds(display_index, display_size) < 0:
            raise UIError
    finally:
        del display_index

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
    del display_size

    try:
        ui.window = SDL_CreateWindow(str.encode(title, 'utf-8'), *window_position, SDL_WINDOW_SHOWN | SDL_WINDOW_VULKAN | SDL_WINDOW_RESIZABLE | SDL_WINDOW_INPUT_FOCUS | SDL_WINDOW_MOUSE_FOCUS)
        if ui.window is None:
            raise UIError
    finally:
        del window_position

    ui.window_id = SDL_GetWindowID(ui.window)
    SDL_SetWindowMinimumSize(ui.window, 160, 90)

    ui.vk_instance_extensions = sdl_get_instance_extensions(ui.window)
    if __debug__:
        print(f'SDL_Vulkan_GetInstanceExtensions() = {ui.vk_instance_extensions}')

    if 'VK_KHR_surface' not in ui.vk_instance_extensions:
        raise UIError('SDL_Vulkan_GetInstanceExtensions: Extension "VK_KHR_surface" is not supported')

    application_info = VkApplicationInfo(pApplicationName=b'GRay', applicationVersion=1, apiVersion=vk_version)
    del vk_version
    instance_create_info = VkInstanceCreateInfo(pApplicationInfo=application_info, ppEnabledExtensionNames=ui.vk_instance_extensions)
    vk_instance = VkInstance()
    try:
        vkCreateInstance(instance_create_info, None, pInstance=ctypes.addressof(vk_instance))
    finally:
        del application_info, instance_create_info
    ui.vk_instance = vk_instance.value
    del vk_instance

    ui.vk_physical_device = vk_select_physical_device_by_type(
        ui.vk_instance,
        [
            VkPhysicalDeviceType.DISCRETE_GPU,
            VkPhysicalDeviceType.INTEGRATED_GPU
        ]
    )

    if __debug__:
        physical_device_properties = vkGetPhysicalDeviceProperties(ui.vk_physical_device)
        print(f'Selected Physical Device: {physical_device_properties.deviceName} ({VkPhysicalDeviceType(physical_device_properties.deviceType).name})', file=sys.stderr)
        print(f'    API Version: {VK_VERSION_STRING(physical_device_properties.apiVersion)}', file=sys.stderr)
        print(f'    Driver Version: {VK_VERSION_STRING(physical_device_properties.driverVersion)}', file=sys.stderr)
        print('    VendorID: 0x%08X' % physical_device_properties.vendorID, file=sys.stderr)
        print('    DeviceID: 0x%08X' % physical_device_properties.deviceID, file=sys.stderr)
        del physical_device_properties

    # print(f'Selected surface format: {vk_window_surface_image_format.name}')
    # print(f'Color Space: {vk_window_surface_image_color_space.name}')

    ui.vk_queue_family_index = vk_select_queue_family_index(ui.vk_physical_device, VkQueueFlagBits.COMPUTE_BIT | VkQueueFlagBits.TRANSFER_BIT)

    device_queue_create_info = VkDeviceQueueCreateInfo(queueFamilyIndex=ui.vk_queue_family_index, queueCount=1, pQueuePriorities=[0.5])
    device_features = VkPhysicalDeviceFeatures(shaderUniformBufferArrayDynamicIndexing=1, shaderSampledImageArrayDynamicIndexing=1, shaderStorageBufferArrayDynamicIndexing=1, shaderStorageImageArrayDynamicIndexing=1)
    device_create_info = VkDeviceCreateInfo(pQueueCreateInfos=[device_queue_create_info], ppEnabledExtensionNames=['VK_KHR_swapchain', 'VK_KHR_vulkan_memory_model', 'VK_KHR_present_id', 'VK_KHR_present_wait', 'VK_KHR_spirv_1_4'])
    try:
        ui.vk_device = vkCreateDevice(ui.vk_physical_device, device_create_info, None)
    finally:
        del device_create_info, device_features, device_queue_create_info
    ui.draw_thread = threading.Thread(target=draw_main, name='DrawThread', daemon=True)
    ui.draw_thread.start()

    while True:
        event = SDL_Event()
        if SDL_WaitEvent(event) == 0:
            raise UIError
        if event.type == SDL_QUIT:
            break
        if event.type == SDL_WINDOWEVENT:
            if event.window.windowID == ui.window_id:
                if event.window.event == SDL_WINDOWEVENT_CLOSE:
                    break
                elif event.window.event == SDL_WINDOWEVENT_FOCUS_LOST:
                    ui.window_in_focus.clear()
                elif event.window.event == SDL_WINDOWEVENT_FOCUS_GAINED:
                    ui.window_in_focus.set()

    ui.draw_loop_continue = False
    ui.window_in_focus.set()
    if ui.draw_thread is not None and ui.draw_thread.is_alive():
        ui.draw_thread.join()

    if ui.vk_device is not None:
        vkDestroyDevice(ui.vk_device, None)
        ui.vk_device = None

    if ui.vk_instance is not None:
        vkDestroyInstance(ui.vk_instance, None)
        ui.vk_instance = None

    if ui.window is not None:
        SDL_DestroyWindow(ui.window)
        ui.window = None

    SDL_Quit()

    return 0


if __name__ == '__main__':
    sys.exit(main())
