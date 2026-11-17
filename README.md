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
| `sunxi-drm-port/` | out-of-tree port of the vendor display stack (DE/TCON/HDMI) to kernel 7.3 — see `sunxi-drm-port/NOTES.md` for the Kconfig-emulation fix and build/deploy state |
| `prebuilt/` | the exact deployed `.ko` set + `Image` (md5 `da253ed6`) + `dtbs/` (board dtb md5 `de54b62e`, `boot.scr`/`boot.cmd`) |
| `rootfs-overlay/etc/` | Gentoo rootfs config we changed: `conf.d/modules` (`modules="sunxidrm aic8800_fdrv aic8800_btlpm"`), `modules-load.d/gpu.conf` (`sunxidrm`), `init.d/aic8800-bt` (BT attach service) |

The Imagination GPU driver (powervr) port lives in its own repository.

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

## Where everything lives locally (workstation `~/`)

| path | what |
|---|---|
| `~/orangepi4pro-linux/` | THIS repo (backup/restore package) |
| `~/a733-kernel/` | standalone copy of the kernel git repo (branch `a733-gpu`, 21 commits on upstream `f47d22362`, HEAD `00ba42eb2`) — full working tree, buildable |
| `~/gpu-open/work/mainline/linux` | the live kernel working tree used for board builds (same content as `~/a733-kernel` HEAD + any in-flight edits) |
| `~/gpu-open/work/mainline/build` | kernel build tree (`.config`, Image, Module.symvers) |
| `~/gpu-open/work/aic-port/` | working dir for the AIC8800 port (`wfix/`, `vendor-src/`) |
| `~/gpu-open/work/sunxi-drm-port/src` | live sunxi-drm port tree (backed up here as `sunxi-drm-port/`) |
| `~/gpu-open/apercel` | **separate project** (powervr/BXM GPU driver, github `TumRedSun/apercel`) — do not touch from this repo |

Board side: NVMe rootfs is mounted on the (SD-booted) board at
`/mnt/nvme-root`; modules live in
`/mnt/nvme-root/lib/modules/7.3.0-ge369c7b14bbe-dirty/extra/` (real dir
`7.3.0-g80c82777a58b-dirty`, `ge369c7b14bbe` is a symlink). UART boot
logs are collected in `~/asdasd` (check md5 before reading — stale-log
trap).
