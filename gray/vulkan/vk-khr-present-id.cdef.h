typedef struct VkPresentIdKHR {
    VkStructureType sType;
    const void* pNext;
    uint32_t swapchainCount;
    const uint64_t* pPresentIds;
} VkPresentIdKHR;
