from gray.vulkan import *
from ui.error import UIError
from traceback import print_exc
import ui
import sys


def main():
    vk_window_surface = None
    vk_swap_chain = VK_NULL_HANDLE
    frame_id = 1
 
    try:
        if (
            ui.window is None
            or not isinstance(ui.window_id, int)
            or ui.window_id <= 0
            or ui.vk_instance is None
            or ui.vk_physical_device is None
            or ui.vk_device is None
        ):
            raise UIError('Vulkan UI is not initalized: window, vk_instance, vk_physical_device and vk_device are required')
        
        # vk_semaphore_acquire_image = vkCreateSemaphore(ui.vk_device, VkSemaphoreCreateInfo(), None)
        # vk_semaphore_clear_screen = vkCreateSemaphore(ui.vk_device, VkSemaphoreCreateInfo(), None)
        
        vk_device_queue = vkGetDeviceQueue(ui.vk_device, ui.vk_queue_family_index, 0)

        while ui.draw_loop_continue:
            if vk_window_surface is None:
                if __debug__:
                    print('vk_window_surface = None: SDL_Vulkan_CreateSurface()', file=sys.stderr)
                vk_window_surface = VkSurfaceKHR()
                if not SDL_Vulkan_CreateSurface(ui.window, ui.vk_instance, ctypes.pointer(vk_window_surface)):
                    vk_window_surface = None
                    raise UIError
                vk_window_surface = vk_window_surface.value
                
            if vk_swap_chain == VK_NULL_HANDLE:
                width = ctypes.c_int()
                height = ctypes.c_int()
                SDL_Vulkan_GetDrawableSize(ui.window, width, height)
                vk_window_surface_format, vk_window_surface_color_space = vk_select_surface_format(ui.vk_instance, ui.vk_physical_device, vk_window_surface, [
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
                ])
                if __debug__:
                    print('vk_swap_chain = None: vkCreateSwapchainKHR()', file=sys.stderr)
                    print(f'    imageFormat = {vk_window_surface_format}')
                    print(f'    imageColorSpace = {vk_window_surface_color_space}')
                    print(f'    imageExtent = ({width.value}, {height.value})')
                create_info = VkSwapchainCreateInfoKHR(
                    surface=vk_window_surface,
                    # minImageCount = number of images in the swap chain, use 2 for double buffering
                    # vkAcquireImage would return immediately if there is an image space available
                    minImageCount=2,
                    imageFormat=vk_window_surface_format,
                    imageColorSpace=vk_window_surface_color_space,
                    imageExtent=VkExtent2D(width=width.value, height=height.value),
                    # How many images are presented at once.
                    # 1 = Single screen image on a computer;
                    # 2 = Stereoscopic rendering for stereo vision for VR;
                    # 3+ = VR for aliens?
                    imageArrayLayers=1,
                    imageUsage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
                    # Redundant: Concurrent means more than one queue family may access the image;
                    # In this case we have only one queue family with only one queue inside;
                    imageSharingMode=VK_SHARING_MODE_CONCURRENT,
                    pQueueFamilyIndices=[ui.vk_queue_family_index],
                    # Allow rotating the image before acquire it;
                    preTransform=VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR,
                    # Ignoring alpha as image is for a non-transparent window;
                    compositeAlpha=VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR,
                    # Wait for VSync. If a new presentation request arrives, it replaces the current request, discarding the previous image.
                    presentMode=VK_PRESENT_MODE_MAILBOX_KHR,
                    # Allow the image to be clipped, thus operations on the clipped region might be ignored. This create more effective windowed surface (if window hides part of the current window, performance is improved)
                    clipped=VK_TRUE,
                    # Replaces the current swapchain if any:
                    # This allow reuse of memory resources from old swap chain (not guaranteed);
                    # The old swapchain becomes "retired".
                    # A retired swapchain should not create requests, but existing images are still active;
                    oldSwapchain=vk_swap_chain
                )
                vk_swap_chain = vk_extension_function(ui.vk_instance).vkCreateSwapchainKHR(ui.vk_device, create_info, None)
            
            vk_screen_image_index = vk_extension_function(ui.vk_instance).vkAcquireNextImageKHR(ui.vk_device, vk_swap_chain, 1000000000, VK_NULL_HANDLE, VK_NULL_HANDLE)
            
            vk_extension_function(ui.vk_instance).vkQueuePresentKHR(
                vk_device_queue,
                VkPresentInfoKHR(
                    swapchainCount=1,
                    pSwapchains=[vk_swap_chain],
                    pImageIndices=[vk_screen_image_index],
                    # pNext=VkPresentIdKHR(
                    #     swapchainCount=1,
                    #     pPresentIds=[frame_id]
                    # )
                )
            )
            
            if __debug__:
                print(f'frame_id = {frame_id}')
                
            # vk_extension_function(ui.vk_instance).vkWaitForPresentKHR(ui.vk_device, vk_swap_chain, frame_id, 1000000000)
            
            vkQueueWaitIdle(vk_device_queue)
            
            frame_id += 1

    except:
        print_exc()
    finally:
        if ui.vk_instance is not None:
            if isinstance(vk_window_surface, int):
                vk_extension_function(ui.vk_instance).vkDestroySurfaceKHR(ui.vk_instance, vk_window_surface, None)
                vk_window_surface = None
                
            if vk_swap_chain != VK_NULL_HANDLE:
                vk_extension_function(ui.vk_instance).vkDestroySwapchainKHR(ui.vk_instance, vk_swap_chain, None)
                vk_swap_chain = VK_NULL_HANDLE

        event = SDL_Event()
        event.type = SDL_QUIT
        SDL_PushEvent(event)
