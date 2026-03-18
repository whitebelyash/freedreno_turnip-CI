#!/usr/bin/env python3
"""
Fix vk_sync_binary import_sync_file for KGSL timeline sync on Android.

vk_sync_binary's default import_sync_file unconditionally returns
VK_ERROR_INVALID_EXTERNAL_HANDLE. On Android, the platform swapchain
needs this to import acquire fences from the compositor.

This script patches tu_knl_kgsl.cc to:
1. Add a custom import_sync_file that CPU-waits on the fd then signals
   the underlying timeline (same approach as the syncobj path).
2. Override the binary wrapper's import_sync_file pointer at init time.
"""

import sys

FIX_FUNCTION = r"""
/* Fix: binary-on-timeline import_sync_file for Android swapchain acquire fences.
 * vk_sync_binary's default returns VK_ERROR_INVALID_EXTERNAL_HANDLE because it
 * was designed for D3D12 where sync file import is not needed. On Android the
 * compositor passes acquire fences via import_sync_file. We CPU-wait on the fd
 * (same as the syncobj path) and then signal the underlying timeline point.
 *
 * NOTE: do NOT close(fd) here - ownership stays with the caller per the
 * import_sync_file contract (see vk_sync_import_sync_file in vk_sync.c).
 * Closing it here caused a double-close / fdsan abort when the WSI layer
 * (wsi_create_sync_for_dma_buf_wait) closed the same fd after returning.
 */
static VkResult
kgsl_binary_timeline_import_sync_file(struct vk_device *device,
                                      struct vk_sync *sync,
                                      int fd)
{
   struct vk_sync_binary *binary =
      container_of(sync, struct vk_sync_binary, sync);

   if (fd >= 0) {
      int ret = sync_wait(fd, 3000);
      /* Do NOT close(fd) - the caller owns the fd and will close it. */
      if (ret && errno != ETIME) {
         return vk_errorf(device, VK_ERROR_DEVICE_LOST,
                          "sync_wait on acquire fence failed: %s",
                          strerror(errno));
      }
   }

   return vk_sync_signal(device, &binary->timeline, binary->next_point);
}
"""

OVERRIDE_LINE = "      device->binary_type.sync.import_sync_file = kgsl_binary_timeline_import_sync_file;\n"


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-tu_knl_kgsl.cc>")
        sys.exit(1)

    path = sys.argv[1]

    with open(path, "r") as f:
        content = f.read()

    # 1) Insert fix function before "struct tu_kgsl_queue_submit {"
    marker1 = "struct tu_kgsl_queue_submit {"
    if marker1 not in content:
        print(f"ERROR: Could not find '{marker1}' in {path}")
        sys.exit(1)

    content = content.replace(marker1, FIX_FUNCTION + marker1, 1)

    # 2) Add override after vk_sync_binary_get_type line
    marker2 = "device->binary_type = vk_sync_binary_get_type(&vk_kgsl_timeline_type);"
    if marker2 not in content:
        print(f"ERROR: Could not find '{marker2}' in {path}")
        sys.exit(1)

    content = content.replace(marker2, marker2 + "\n" + OVERRIDE_LINE, 1)

    with open(path, "w") as f:
        f.write(content)

    print(f"Successfully patched {path}")


if __name__ == "__main__":
    main()
