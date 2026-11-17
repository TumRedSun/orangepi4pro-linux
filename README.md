# OrangePi 4 Pro mainline Linux bringup

Backup of the mainline-kernel port for the OrangePi 4 Pro (Allwinner
A733 / SUN60IW2). Target: mainline Linux 7.3.0 (`e369c7b14`), aarch64,
NVMe rootfs (Gentoo/OpenRC), serial console on ttyS0.

## Layout

| path | what |
|---|---|
| `kernel/patches/` | patch series on top of upstream `f47d22362` (torvalds/linux), ordered — apply with `git am` |
| `configs/a733-orangepi4pro.config` | working kernel `.config` used for all board builds |
| `aic-port/wfix/` | `sunxi-wlan` helper module source (out-of-tree, needed by the AIC8800 wifi/bt port) |
| `aic-port/vendor-src/` | pristine vendor AIC8800 tree (bsp/fdrv/btlpm) to patch |
| `aic-port/PATCHES.md` | every fix applied to the AIC8800 sources for kernel 7.3 — the patched /tmp sources were lost, this is the recovery doc |

The sunxi-drm (GPU/display) driver port is **not** here — it lives in its
own repository.

## Rebuilding the kernel

```
git clone --depth 1 --filter=blob:none https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git
cd linux && git checkout f47d22362
git am /path/to/kernel/patches/*.patch
cp /path/to/configs/a733-orangepi4pro.config .config
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j$(nproc) Image dtbs modules
```

Vermagic of the current build: `7.3.0-ge369c7b14bbe-dirty`
(Image md5 `da253ed6`), DTB `sun60i-a733-orangepi-4-pro.dtb` (md5
`de54b62e`).

## Nightly builds

`.github/workflows/nightly.yml` runs at 03:30 UTC nightly: pins upstream
`f47d22362`, applies the patch series, cross-builds `Image` + dtb +
`modules`, then publishes a rolling `nightly` release with the artifacts.
