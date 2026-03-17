#!/usr/bin/env python3
"""
Apply freedreno_devices.py patches programmatically.

This script replaces patches 5, 7, and 10 from tu8_kgsl.patch which modify
freedreno_devices.py. Those patches fail to apply on newer Mesa because the
file was restructured upstream (lines shifted by ~200).

Changes applied:
  - Patch 5:  a8xx_gen1 reg_size_vec4 128 -> 96
  - Patch 7:  Add a8xx_825, a8xx_829, a8xx_810 GPUProps + add_gpus for 810/825/829
  - Patch 10: a8xx_825/829 gmem_per_ccu_depth_cache_size 256->128 (already baked in)
"""

import re
import sys

# ── Patch 5: force smaller reg_size for a8xx_gen1 ──────────────────────────

def apply_patch5_reg_size(content: str) -> str:
    """Change reg_size_vec4 = 128 to 96 inside a8xx_gen1 block."""
    # Find the a8xx_gen1 block and replace reg_size_vec4
    pattern = r'(a8xx_gen1\s*=\s*GPUProps\(\s*\n\s*)reg_size_vec4\s*=\s*128'
    replacement = r'\g<1>reg_size_vec4 = 96'
    new_content, count = re.subn(pattern, replacement, content)
    if count == 0:
        # Maybe already 96 or different format
        if 'a8xx_gen1' in content and 'reg_size_vec4 = 96' in content:
            print("  Patch 5: reg_size_vec4 already set to 96, skipping")
            return content
        raise RuntimeError("Patch 5: Could not find a8xx_gen1 reg_size_vec4 = 128")
    print("  Patch 5: a8xx_gen1 reg_size_vec4 = 128 -> 96")
    return new_content


# ── Patch 7 + 10: add a8xx_825, a8xx_829, a8xx_810 and GPU entries ────────

GPU_PROPS_BLOCK = '''
a8xx_825 = GPUProps(
        sysmem_vpc_attr_buf_size = 131072,
        sysmem_vpc_pos_buf_size = 65536,
        sysmem_vpc_bv_pos_buf_size = 32768,
        sysmem_ccu_color_cache_fraction = CCUColorCacheFraction.FULL.value,
        sysmem_per_ccu_color_cache_size = 128 * 1024,
        sysmem_ccu_depth_cache_fraction = CCUColorCacheFraction.THREE_QUARTER.value,
        sysmem_per_ccu_depth_cache_size = 96 * 1024,
        gmem_vpc_attr_buf_size = 49152,
        gmem_vpc_pos_buf_size = 24576,
        gmem_vpc_bv_pos_buf_size = 32768,
        gmem_ccu_color_cache_fraction = CCUColorCacheFraction.EIGHTH.value,
        gmem_per_ccu_color_cache_size = 16 * 1024,
        gmem_ccu_depth_cache_fraction = CCUColorCacheFraction.FULL.value,
        gmem_per_ccu_depth_cache_size = 128 * 1024,
)

a8xx_829 = GPUProps(
        sysmem_vpc_attr_buf_size = 131072,
        sysmem_vpc_pos_buf_size = 65536,
        sysmem_vpc_bv_pos_buf_size = 32768,
        sysmem_ccu_color_cache_fraction = CCUColorCacheFraction.FULL.value,
        sysmem_per_ccu_color_cache_size = 128 * 1024,
        sysmem_ccu_depth_cache_fraction = CCUColorCacheFraction.THREE_QUARTER.value,
        sysmem_per_ccu_depth_cache_size = 96 * 1024,
        gmem_vpc_attr_buf_size = 49152,
        gmem_vpc_pos_buf_size = 24576,
        gmem_vpc_bv_pos_buf_size = 32768,
        gmem_ccu_color_cache_fraction = CCUColorCacheFraction.EIGHTH.value,
        gmem_per_ccu_color_cache_size = 16 * 1024,
        gmem_ccu_depth_cache_fraction = CCUColorCacheFraction.FULL.value,
        gmem_per_ccu_depth_cache_size = 128 * 1024,
)

a8xx_810 = GPUProps(
        sysmem_vpc_attr_buf_size = 131072,
        sysmem_vpc_pos_buf_size = 65536,
        sysmem_vpc_bv_pos_buf_size = 32768,
        # These values are maximum size of depth/color cache for current A8XX Gen2 sysmem configuration
        # Bigger values cause an integer underflow in freedreno gmem calculations
        sysmem_ccu_color_cache_fraction = CCUColorCacheFraction.FULL.value,
        sysmem_per_ccu_color_cache_size = 32 * 1024,
        sysmem_ccu_depth_cache_fraction = CCUColorCacheFraction.THREE_QUARTER.value,
        sysmem_per_ccu_depth_cache_size = 32 * 1024,
        gmem_vpc_attr_buf_size = 49152,
        gmem_vpc_pos_buf_size = 24576,
        gmem_vpc_bv_pos_buf_size = 32768,
        gmem_ccu_color_cache_fraction = CCUColorCacheFraction.EIGHTH.value,
        gmem_per_ccu_color_cache_size = 16 * 1024,
        gmem_ccu_depth_cache_fraction = CCUColorCacheFraction.FULL.value,
        gmem_per_ccu_depth_cache_size = 64 * 1024,
        # FD810 does not support ray tracing
        has_ray_intersection = False,
        has_sw_fuse = False, # ????
        disable_gmem = True,
)
'''

# GPU entries to add after the FD830 add_gpus block
ADD_GPUS_BLOCK = '''
# gen8_3_0
add_gpus([
        GPUId(chip_id=0x44010000, name="FD810"),
    ], A6xxGPUInfo(
        CHIP.A8XX,
        [a7xx_base, a7xx_gen3, a8xx_base, a8xx_810],
        num_ccu = 2,
        num_slices = 1,
        tile_align_w = 96,
        tile_align_h = 32,
        tile_max_w = 16416,
        tile_max_h = 16384,
        num_vsc_pipes = 32,
        cs_shared_mem_size = 32 * 1024,
        wave_granularity = 2,
        fibers_per_sp = 128 * 2 * 16,
        magic_regs = dict(),
        raw_magic_regs = a8xx_base_raw_magic_regs,
    ))

# gen8_6_0
add_gpus([
        GPUId(chip_id=0x44030000, name="FD825"),
    ], A6xxGPUInfo(
        CHIP.A8XX,
        [a7xx_base, a7xx_gen3, a8xx_base, a8xx_825],
        num_ccu = 4,
        num_slices = 2,
        tile_align_w = 96,
        tile_align_h = 32,
        tile_max_w = 16416,
        tile_max_h = 16384,
        num_vsc_pipes = 32,
        cs_shared_mem_size = 32 * 1024,
        wave_granularity = 2,
        fibers_per_sp = 128 * 2 * 16,
        magic_regs = dict(),
        raw_magic_regs = a8xx_base_raw_magic_regs,
    ))

# TODO: Properly fill all values for this GPU
add_gpus([
    GPUId(chip_id=0x44030A00, name="FD829"), # kgsl id???
    GPUId(chip_id=0x44030A20, name="FD829"), # found by testing, another revision?
    GPUId(chip_id=0xffff44030A00, name="FD829"),
    ], A6xxGPUInfo(
        CHIP.A8XX,
        [a7xx_base, a7xx_gen3, a8xx_base, a8xx_829],
        num_ccu = 4,
        num_slices = 2,
        tile_align_w = 96,
        tile_align_h = 32,
        tile_max_w = 16416,
        tile_max_h = 16384,
        num_vsc_pipes = 32,
        cs_shared_mem_size = 32 * 1024,
        wave_granularity = 2,
        fibers_per_sp = 128 * 2 * 16,
        magic_regs = dict(),
        raw_magic_regs = a8xx_base_raw_magic_regs,
    ))

'''


def apply_patch7_gpu_entries(content: str) -> str:
    """Add a8xx_825/829/810 GPUProps and add_gpus entries."""

    # Skip if already applied
    if 'a8xx_825' in content:
        print("  Patch 7+10: GPU entries already present, skipping")
        return content

    # 1) Insert GPUProps blocks after a8xx_gen2 definition
    # Find the end of a8xx_gen2 = GPUProps(...) block
    marker1 = re.search(
        r'(a8xx_gen2\s*=\s*GPUProps\(.*?^\))',
        content,
        re.MULTILINE | re.DOTALL
    )
    if not marker1:
        raise RuntimeError("Patch 7: Could not find a8xx_gen2 GPUProps block")

    insert_pos = marker1.end()
    content = content[:insert_pos] + GPU_PROPS_BLOCK + content[insert_pos:]
    print("  Patch 7: Added a8xx_825, a8xx_829, a8xx_810 GPUProps blocks")

    # 2) Insert add_gpus entries after the FD830 add_gpus block
    # Look for the closing "))" of the FD830/A830 add_gpus block
    # Pattern: add_gpus with FD830 or "830" ... ending with "))""
    marker2 = re.search(
        r'(add_gpus\(\[\s*\n\s*GPUId\(chip_id=0x44050000.*?raw_magic_regs\s*=\s*a8xx_base_raw_magic_regs,\s*\n\s*\)\))',
        content,
        re.DOTALL
    )
    if not marker2:
        raise RuntimeError("Patch 7: Could not find FD830 add_gpus block")

    insert_pos2 = marker2.end()
    content = content[:insert_pos2] + ADD_GPUS_BLOCK + content[insert_pos2:]
    print("  Patch 7: Added add_gpus entries for FD810, FD825, FD829")

    return content


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path-to-freedreno_devices.py>")
        sys.exit(1)

    path = sys.argv[1]

    with open(path, "r") as f:
        content = f.read()

    print(f"Patching {path}...")

    content = apply_patch5_reg_size(content)
    content = apply_patch7_gpu_entries(content)

    with open(path, "w") as f:
        f.write(content)

    print(f"Successfully patched {path}")


if __name__ == "__main__":
    main()
