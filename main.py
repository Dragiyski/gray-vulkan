import sys
import os
import ctypes
import threading
from traceback import print_exc
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
vk_device = None

vk_window_surface_image_format = None
vk_window_surface_image_color_space = None

# This mush be chosen from vkGetPhysicalDeviceQueueFamilyProperties,
# in this case we want to have Transfer and Compute (Graphics is good, but not required).
# We have no priority here, we select the first one that match, as we need only one queue (for now).
vk_queue_family_index = None

draw_need_resize = False
# Set to True when the loop is about to run.
# Can be cleared by other threads to signal to the draw thread to leave (expected quit).
# Draw thread can (and possibly will) finish the current frame and present it, before leaving.
draw_loop_run = False
# An event that can be used by other threads to control draw loop activity.
# When cleared, the draw loop will wait before start a new frame.
# This allow drawing to paused and resumed (no resources are freed in this case, allowing for immedate resume).
# Useful to pause the drawing, when the window focus is lost (other system like physics/network might still run)
draw_loop_active = threading.Event()

# Swap chain contains a Queue of 1+ (usually 2 for double buffering) presentable images;
# One of the images is presented on screen; The GPU is free to modify any image, but preferably it modifies one image that is not
# presented and swap it with the presented image when done (and when certain conditions are met, like VSync signal becomes active)
# The chain MUST be recreated on window resize, as images are created with specified width/height.
# vk_swap_chain = None


def vk_select_physical_device_by_type(*priority_list, criteria=None, initial_priority=None):
    if not isinstance(vk_instance, int):
        raise UIError('vk_instance: not initialized')

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


def draw_main():
    global draw_need_resize
    # Initialization phase
    # TODO

    try:
        draw_need_resize = True
        vk_swap_chain = VK_NULL_HANDLE

        create_info = VkCommandPoolCreateInfo(flags=VK_COMMAND_POOL_CREATE_TRANSIENT_BIT | VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT)
        vk_command_pool = vkCreateCommandPool(vk_device, create_info, None)
        del create_info
        
        device_queue = vkGetDeviceQueue(vk_device, vk_queue_family_index, 0)
        
        frame_count = 0

        while draw_loop_run:
            draw_loop_active.wait()

            if not draw_loop_run:
                break

            if draw_need_resize:
                draw_need_resize = False
                width = ctypes.c_int()
                height = ctypes.c_int()
                SDL_Vulkan_GetDrawableSize(window, width, height)
                print(f'frame[{frame_count}]: vkCreateSwapchainKHR({width.value}, {height.value})')
                create_info = VkSwapchainCreateInfoKHR(
                    surface=vk_window_surface,
                    minImageCount=2,  # 1 or 2 (might be need for double buffering)
                    imageFormat=vk_window_surface_image_format,
                    imageColorSpace=vk_window_surface_image_color_space,
                    imageExtent=VkExtent2D(width=width.value, height=height.value),
                    imageArrayLayers=1,  # 1 = Single screen image, 2 = Stereoscopic rendering (for left-right eye), 3+ = for aliens?
                    imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
                    imageSharingMode=VK_SHARING_MODE_CONCURRENT,
                    pQueueFamilyIndices=[vk_queue_family_index],
                    preTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,
                    compositeAlpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,  # Alpha is ignore for window surface, color is fully replaced.
                    presentMode=VK_PRESENT_MODE_MAILBOX_KHR,  # Wait for VSync. If a new presentation request arrives, it replaces the current request, discarding the previous image.
                    clipped=VK_TRUE,  # Allow the image to be clipped, thus operations on the clipped region might be ignored. This create more effective windowed surface (if window hides part of the current window, performance is improved)
                    oldSwapchain=vk_swap_chain  # Replaces the current swapchain if any*
                )
                # *According to Vulkan spec, giving oldSwapchain might be more efficient than destroying/create pair.
                # Some memory of old swap chain might be reused.
                # Concurrent access of old images are still valid (no early free problem)
                # But the oldSwapChain is retired, even if the creation of new swap chain fails.
                vk_swap_chain = vk_extension_function(vk_instance).vkCreateSwapchainKHR(vk_device, create_info, None)
            
            start_frame_semaphore = vkCreateSemaphore(vk_device, VkSemaphoreCreateInfo(), None)
            
            print(f'frame[{frame_count}]: vkAcquireNextImageKHR')
            
            try:
                swap_chain_image_index = vk_extension_function(vk_instance).vkAcquireNextImageKHR(vk_device, vk_swap_chain, UINT64_MAX, start_frame_semaphore, VK_NULL_HANDLE)
            except (VkErrorOutOfDateKhr | VkSuboptimalKhr):
                draw_need_resize = True
                continue
            # swap_chain_image_index is the next available index, which should be used once the fence is signaled
            
            swap_chain_image = vk_extension_function(vk_instance).vkGetSwapchainImagesKHR(vk_device, vk_swap_chain)[swap_chain_image_index]  # VkImage
            # swap_chain_image = vk_extension_function(vk_instance).vkGetSwapchainImagesKHR(vk_device, vk_swap_chain)[0]  # VkImage

            allocate_info = VkCommandBufferAllocateInfo(commandPool=vk_command_pool, level=VK_COMMAND_BUFFER_LEVEL_PRIMARY, commandBufferCount=1)
            vk_command_buffer = vkAllocateCommandBuffers(vk_device, allocate_info)[0]
            del allocate_info

            begin_info = VkCommandBufferBeginInfo(flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT)
            vkBeginCommandBuffer(vk_command_buffer, begin_info)
            del begin_info
            
            clear_color_value = VkClearColorValue(uint32=[0, 0, 0, 255])
            image_range = VkImageSubresourceRange(aspectMask=VK_IMAGE_ASPECT_COLOR_BIT, levelCount=VK_REMAINING_MIP_LEVELS, layerCount=VK_REMAINING_ARRAY_LAYERS)
            vkCmdClearColorImage(vk_command_buffer, swap_chain_image, VK_IMAGE_LAYOUT_SHARED_PRESENT_KHR, clear_color_value, 1, [image_range])
            del image_range
            del clear_color_value
            
            vkEndCommandBuffer(vk_command_buffer)
            
            vk_clear_semaphore = vkCreateSemaphore(vk_device, VkSemaphoreCreateInfo(), None)
            
            print(f'frame[{frame_count}]: vkQueueSubmit')
            
            submit_info = VkSubmitInfo(pCommandBuffers=[vk_command_buffer], pWaitSemaphores=[start_frame_semaphore], pSignalSemaphores=[vk_clear_semaphore])
            vkQueueSubmit(device_queue, 1, [submit_info], VK_NULL_HANDLE)
            del submit_info
            
            present_info = VkPresentInfoKHR(pSwapchains=[vk_swap_chain], pWaitSemaphores=[vk_clear_semaphore], pImageIndices=[0])
            print(f'frame[{frame_count}]: vkQueuePresentKHR')
            try:
                vk_extension_function(vk_instance).vkQueuePresentKHR(device_queue, present_info)
            except VkErrorOutOfDateKhr:
                print(f'frame[{frame_count}]: vkQueuePresentKHR = VkErrorOutOfDateKhr')
                draw_need_resize = True
                continue
            except VkErrorSurfaceLostKhr:
                print(f'frame[{frame_count}]: vkQueuePresentKHR = VkErrorSurfaceLostKhr')
                break
            finally:
                vkDestroySemaphore(vk_device, vk_clear_semaphore, None)
                vkDestroySemaphore(vk_device, start_frame_semaphore, None)
                vkFreeCommandBuffers(vk_device, vk_command_pool, 1, [vk_command_buffer])
                del present_info
            
            frame_count += 1
            print(f'frame[{frame_count}]: done')

    except:
        print_exc()
    finally:
        if vk_swap_chain != VK_NULL_HANDLE:
            vk_extension_function(vk_instance).vkDestroySwapchainKHR(vk_device, vk_swap_chain, None)
    event = SDL_Event()
    event.type = SDL_QUIT
    SDL_PushEvent(event)


def main():
    global window, window_id, vk_instance, vk_window_surface, vk_physical_device, vk_physical_device_properties, vk_window_surface_image_format, vk_window_surface_image_color_space, vk_queue_family_index, vk_device, draw_loop_run, draw_loop_need_resize, draw_thread, draw_need_resize
    if SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) < 0:
        raise UIError

    vk_version = vkEnumerateInstanceVersion()

    print(f'Vulkan Version: {VK_VERSION_STRING(vk_version)}')

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

    vk_physical_device = vk_select_physical_device_by_type(
        VkPhysicalDeviceType.DISCRETE_GPU,
        VkPhysicalDeviceType.INTEGRATED_GPU
    )

    physical_device_properties = vkGetPhysicalDeviceProperties(vk_physical_device)

    print(f'Selected Physical Device: {physical_device_properties.deviceName} ({VkPhysicalDeviceType(physical_device_properties.deviceType).name})')
    print(f'    API Version: {physical_device_properties.apiVersion}')
    print(f'    Driver Version: {physical_device_properties.driverVersion}')
    print('    VendorID: 0x%08X' % physical_device_properties.vendorID)
    print('    DeviceID: 0x%08X' % physical_device_properties.deviceID)

    vk_window_surface_image_format, vk_window_surface_image_color_space = select_surface_format(
        VkFormat.R32G32B32A32_SFLOAT,
        VkFormat.R32G32B32_SFLOAT,
        VkFormat.R8G8B8A8_SRGB,
        VkFormat.B8G8R8A8_SRGB,
        VkFormat.R8G8B8_SRGB,
        VkFormat.B8G8R8_SRGB,
        VkFormat.R8G8B8A8_UNORM,
        VkFormat.B8G8R8A8_UNORM,
        VkFormat.R8G8B8_UNORM,
        VkFormat.B8G8R8_UNORM
    )

    print(f'Selected surface format: {vk_window_surface_image_format.name}')
    print(f'Color Space: {vk_window_surface_image_color_space.name}')

    vk_queue_family_index = select_queue_family_index(VkQueueFlagBits.COMPUTE_BIT | VkQueueFlagBits.TRANSFER_BIT)

    device_queue_create_info = VkDeviceQueueCreateInfo(queueFamilyIndex=vk_queue_family_index, queueCount=1, pQueuePriorities=[0.5])
    device_features = VkPhysicalDeviceFeatures(shaderUniformBufferArrayDynamicIndexing=1, shaderSampledImageArrayDynamicIndexing=1, shaderStorageBufferArrayDynamicIndexing=1, shaderStorageImageArrayDynamicIndexing=1)
    device_create_info = VkDeviceCreateInfo(pQueueCreateInfos=[device_queue_create_info], ppEnabledExtensionNames=['VK_KHR_swapchain', 'VK_KHR_vulkan_memory_model', 'VK_KHR_present_wait', 'VK_KHR_spirv_1_4'])
    vk_device = vkCreateDevice(vk_physical_device, device_create_info, None)

    # Swap chain is not created here, it is created in the draw thread, and re-created when the surface drawable size changes.

    draw_loop_run = True
    draw_loop_active.set()
    draw_thread = threading.Thread(target=draw_main, name='DrawThread', daemon=False)
    draw_thread.start()

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
                elif event.window.event == SDL_WINDOWEVENT_SIZE_CHANGED:
                    draw_need_resize = True

    draw_loop_run = False
    draw_loop_active.set()
    draw_thread.join()

    vkDestroyDevice(vk_device, None)
    vk_extension_function(vk_instance).vkDestroySurfaceKHR(vk_instance, vk_window_surface, None)
    SDL_DestroyWindow(window)
    vkDestroyInstance(vk_instance, None)
    SDL_Quit()

    return 0


if __name__ == '__main__':
    sys.exit(main())
