# sunxi-drm port (kernel 7.3, aarch64, A733)

Out-of-tree port of the vendor Allwinner display stack (DE v352 + TCON TV +
DW HDMI 2.0) to mainline Linux 7.3. Build dir `src/`, `M=` style.

## Build

```
make -C <mainline-build-tree> M=$PWD/src modules
```

Vermagic of the current build: `7.3.0-ge369c7b14bbe-dirty`.

## Kconfig emulation — THE critical fix

The directory's Kconfig is **not evaluated** for out-of-tree (`M=`)
builds, and the whole driver is gated by `DRV_PTR(drv, cond)` =
`IS_ENABLED(cond) ? &drv : NULL` (sunxi_drm_drv.c ~437). With no defines,
every sub-driver (DE, TCON, TCON_TOP, HDMI) collapsed to NULL, so
`sunxi_drm_match_add()` found no bound components and the master probe
returned `-ENODEV` (boot #90, `a733-q= soc:drm-sunxi sunxi-drm ret=-19`).

The Makefile now carries:

```
-DCONFIG_AW_DRM -DCONFIG_AW_DRM_DE -DCONFIG_AW_DRM_TCON
-DCONFIG_AW_DRM_TCON_TOP -DCONFIG_AW_DRM_TCON_TV
-DCONFIG_AW_DRM_HDMI_TX -DCONFIG_AW_DRM_HDMI20
-DCONFIG_ARCH_SUN60IW2
```

`ARCH_SUN60IW2` selects the A733 register tables in `sunxi_device/hardware/
lowlevel_tcon/{tcon_top,tcon_tv_reg}.c` and `lowlevel_lcd/tcon_lcd.c`.

DSI/LVDS/RGB/EDP configs stay OFF (board uses the DE -> tcon-tv -> HDMI0
chain only); their stub platform drivers must stay unregistered.

## Runtime model

`module_init` registers sub-drivers (tcon-top, de, dsi, lvds, rgb, hdmi,
edp, tcon) + the `sunxi-drm` master; the master's probe
(`sunxi_drm_platform_probe`, ~:1348) runs `sunxi_drm_match_add()` which
binds already-probed sub devices via `component_match_add`; empty match ->
`ERR_PTR(-ENODEV)` (line ~479). All four DT nodes
(`de@5000000` v352, `vo-top@5510000` tcon-top1, `tcon-tv@5730000`,
`hdmi@5520000`) are enabled by the board dts (see kernel/patches/0021).
`a733-q>/a733-b=` dmesg prints are the board's platform-probe trace hooks.

## Dependencies

Module chain (`modules.dep`):
`sunxidrm <- drm_display_helper + cec + drm_dma_helper + drm_kms_helper + drm + backlight`

`cec.ko` and `drm_display_helper.ko` come straight from the mainline tree
(`drivers/media/cec/core`, `drivers/gpu/drm/display`); in the board's
kernel they must be modules (`CONFIG_CEC_CORE=m`,
`CONFIG_DRM_DISPLAY_HELPER=m`) or the sunxidrm insmod fails with
"Unknown symbol cec_*/drm_scdc_*" (boot #89 symptom).

fbcon over the DRM card comes from `CONFIG_DRM_FBDEV_EMULATION=y`; the
vendor fbdev pieces (`sunxi_fbdev_core.c`, `sunxi_drm_fbdev.c`) are NOT
in the build list (stub only).

## Deployed state (backup)

`../prebuilt/` holds the exact `.ko` set deployed to the NVMe rootfs
md5 at backup time: `sunxidrm.ko 893ed47b` (the fixed build), Image
`da253ed6`, DTB `de54b62e`. Modules go to
`/lib/modules/7.3.0-ge369c7b14bbe-dirty/extra/`,
`/etc/conf.d/modules = "sunxidrm aic8800_fdrv aic8800_btlpm"`.

powervr/gpu-sched (Imagination GPU) live in their own repo and are
disabled on the board (`powervr.ko.disabled`, boot #88 froze the system
during its insmod — parked until the display is up).
