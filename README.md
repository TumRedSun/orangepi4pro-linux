# OrangePi 4 Pro mainline Linux bringup

Backup of the mainline-kernel port for the OrangePi 4 Pro (Allwinner
A733 / SUN60IW2). Target: mainline Linux **7.4-rc3+** (`666539eecdf4`,
2026-11-16), aarch64, NVMe rootfs (Gentoo/OpenRC), serial console on ttyS0.

> **This fork** rebases the kernel series from `f47d22362` (7.3.0) onto
> `666539eecdf4`. See [Rebase to 7.4-rc3](#rebase-to-74-rc3) for what changed.
> It also adds patches 0023–0035: **working Ethernet**, a **Debian SD-card
> boot**, the **BL31 memory reservation**, the **AXP318W PMIC driver** and the
> **26 MHz crystal fix** (see
> [SD-card boot and Ethernet](#sd-card-boot-and-ethernet-patches-00230035)).
> The `prebuilt/` artifacts and the module paths below still describe the
> **7.3** build deployed on the board.

## Layout

| path | what |
|---|---|
| `kernel/patches/` | patch series (35) on top of upstream `666539eecdf4` (torvalds/linux), ordered — apply with `git am` |
| `rootfs-overlay-debian-sd/` | Debian 13 SD-card setup for the mainline kernel: U-Boot script and `powervr` blacklist |
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
git init linux && cd linux
git fetch --depth=1 https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git 666539eecdf4db623f5e3c3e55cf9f2dfad24aa4
git checkout FETCH_HEAD
git am /path/to/kernel/patches/*.patch
cp /path/to/configs/a733-orangepi4pro.config .config
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j$(nproc) Image dtbs modules
```

On this base the kernel release is `7.4.0-rc3-g<sha>`. The deployed 7.3 build
had vermagic `7.3.0-ge369c7b14bbe-dirty` (Image md5 `da253ed6`), DTB
`sun60i-a733-orangepi-4-pro.dtb` (md5 `de54b62e`).

## Rebase to 7.4-rc3

The series was rebased from `f47d22362` onto `666539eecdf4` (7.4-rc3+, 2026-11-16).

**Verified:**
- the 22 patches `git am` cleanly onto a fresh `666539eecdf4`
- `olddefconfig` with `configs/a733-orangepi4pro.config` keeps every A733 option
- `Image dtbs modules` build with **0 errors and 0 warnings** (aarch64-linux-gnu-gcc 15.2): 1707 modules, `Image` about 44 MB
- the rebuilt `sun60i-a733-orangepi-4-pro.dtb` decompiles **identical** to the deployed `prebuilt/dtbs/` one

**Not verified:** booting it. Nothing here has run on a board yet.

**What changed:**

| Patch | Change |
|---|---|
| 0002 pinctrl | The main A733 PIO driver, its register layout (upstream `SUNXI_PINCTRL_NCAT3_REG_LAYOUT`, offsets identical) and the shared binding `allwinner,sun55i-a523-pinctrl.yaml` are **upstream now**. The patch keeps only the R-PIO driver (`allwinner,sun60i-a733-r-pinctrl`), with `SUNXI_PINCTRL_NEW_REG_LAYOUT` renamed to `NCAT2_REG_LAYOUT` (same bit). |
| 0005 bindings | The private A733 pinctrl binding is dropped. Its fix (main PIO has **10** IRQ banks, matching the driver's `irq_banks = 10`; upstream required 11) is carried into the shared upstream binding. |
| 0011 bindings | `snps,dwmac.yaml` keeps both `sun50i-h616-emac1` (upstream) and `sun60i-a733-gmac0`. |
| 0017 debug | `init/main.c` S8 marker kept after upstream's moved `after_dashes` block. |
| 0020 grab-bag | Uses upstream's main PIO and `devm_kzalloc_obj(s)`, keeping the `a733_pcie_snap` trace points and the **R-PIO IRQ_CTRL/STATUS access skip** (needed so PCIe outbound TLPs keep working). The DWC `skip_speed_change` guard now wraps the upstream-renamed `LINK_WIDTH_SPEED_CTRL`/`SPEED_CHANGE`. |
| 0022 (new) | `pcie-sun60i-a733.c` follows mainline's renamed DWC port-logic macros (all values identical, mapped by definition). |

**Behavior difference to test:** the main PIO now uses upstream's `io_bias_cfg_variant = BIAS_VOLTAGE_PIO_POW_MODE_SEL` and `irq_read_needs_mux = true`. The old private driver used `BIAS_VOLTAGE_PIO_POW_MODE_CTL` with a 0x08 control offset. Check IO-voltage-sensitive peripherals (SD, eMMC, Wi-Fi SDIO) on the board.

**Config drift:** `olddefconfig` turns `CONFIG_DRM_PANEL` from `y` to `m` and adds new upstream symbols. Nothing A733-specific changed.

**Out-of-tree modules:** these need work before they load on 7.4.
- `sunxi-drm-port/` **does not build on 7.4 yet**:
  - `drm/drm_fb_helper.h` moved to `drm/clients/drm_fbdev_helper.h` (an include fix)
  - mainline also removed `drm_plane_funcs.reset` / `drm_crtc_funcs.reset` (now `.atomic_create_state`), `__drm_atomic_helper_{plane,crtc}_reset` and `drm_simple_encoder_init`
  - the vendor driver's subclassed-state reset functions need a real port, so **HDMI is unavailable on this base** until then
- `aic-port/`: not rebuilt, because the patched sources were lost (see `aic-port/PATCHES.md`). It must be rebuilt for the new vermagic.

## SD-card boot and Ethernet (patches 0023–0035)

Tested on an OrangePi 4 Pro booting Debian 13 (Orange Pi OS trixie server
image) from an SD card, with the kernel built from this series. Works: SD
rootfs, serial console, NVMe, **Ethernet** (100 Mb/s link, limited by the
switch used; DHCP, ping and SSH). Gigabit, HDMI, Wi-Fi/BT and the GPU were
not tested or don't work yet.

| Patch | What |
|---|---|
| 0023 dts | GMAC0 resets: `stmmaceth` = `RST_BUS_GMAC0_AXI`, `ahb` = `RST_BUS_GMAC0` (vendor BSP roles), so stmmac no longer pulses the bus reset after the glue was programmed |
| 0024 dwmac-sun60i | write the syscfg register **after** ungating the bus clock and releasing the bus reset (it stayed at reset value `0x8000` = internal EPHY), and enable the `phy` 25 MHz clock |
| 0025 pinctrl | A733 `GPIO_POW_MOD_SEL` has a 2-bit field per bank (`11` = 1.8 V); the generic code wrote 1 bit with inverted meaning. No effect unless a `vcc-pX-supply` is set |
| 0026 clk | the bringup clock trace prints at `pr_debug`, not `KERN_EMERG` (it flooded the console with SD card-detect polling) |
| 0027 dts | new `sun60i-a733-orangepi-4-pro-sd.dts` (below) |
| 0028 dtsi | reserve the vendor BL31 secure monitor at `0x48000000` (16 MiB, `no-map`). Without it Linux can allocate over BL31, and U-Boot can move an initrd onto it (the board then hangs after "Starting kernel") |
| 0029–0033 mfd, regulator | AXP318W PMIC support from the upstream series by Andre Przywara and Jerome Brunet, taken from [armbian/build#10712](https://github.com/armbian/build/pull/10712). 0033 is rebased onto 7.4 |
| 0034 clk | `pll-ref` and the RTC `hosc` run from a new `dcxo` clock, set to 26 MHz on this board, so PLL-derived rates are correct |
| 0035 dts | the SD dts uses the AXP318W: `SWOUT1` powers the Ethernet PHY and `SWOUT2` the SD card |

**`sun60i-a733-orangepi-4-pro-sd.dts`** (the NVMe board dts is unchanged):
- **SD:** PF0–PF5 muxed; `uart0` no longer claims PF2/PF4 (SD lines); `broken-cd` (PF6 card-detect caused an RCU stall); `vmmc` from PMIC `SWOUT2` (else "no support for card's volts").
- **GPU:** disabled. udev autoloads `powervr.ko` and the board hangs about 8 s into boot.
- **Ethernet (YT8531C):**
  - `snps,clk-csr = <4>` (the CSR clock is 200 MHz AHB; the auto choice gave a 12.5 MHz MDC)
  - `phy-handle`
  - PHY reset on **PH16**: the board dts's PA14 doesn't exist, since the A733 has no port A
  - `motorcomm,clk-out-frequency-hz = <125000000>` (the GMAC's TX clock comes from the PHY)
  - `phy-mode = "rgmii-id"` with `rx-internal-delay-ps = <1900>` and `tx-internal-delay-ps = <150>`, matching the vendor kernel's PHY registers
- **PMIC:** AXP318W at `0x36` on S-TWI0 (`i2c@7083000`, PL0/PL1). Only `SWOUT1` (`dc1sw1`, `VCC-3V3-PHY`, which boot0 leaves off) and `SWOUT2` (`dc1sw2`) are described, both always on. The vendor BSP calls this chip AXP8191.

**Tested with patches 0029–0035** on an OrangePi 4 Pro running Armbian trixie
(`edge`): the kernel powers the PHY with no userspace help, and Ethernet gets
a 100 Mb/s link with DHCP and working ping. `pll-ref` reads 24 MHz, `pll-peri0`
2400 MHz, the PHY clock 25 MHz and the SD clock 50 MHz. The RTC `DCXO_CTRL`
frequency select reads 2 (26 MHz).

Booting with an initrd (for example Armbian) through the vendor U-Boot
also needs, in the boot script, `setenv fdt_high 0xffffffff` and
`setenv initrd_high 0xffffffff`, and a DTB with free space (`dtc -p`): U-Boot
writes `bootargs` and the initrd range into `/chosen` and hangs with
`FDT_ERR_NOSPACE` otherwise. Armbian `edge` images for this board work this
way (github.com/ijiki16/build, branch `sun60iw2-mainline-edge`).

Other findings, not fixed here:
- Schematic OPi 4 Pro v1.3.2 shows the YT8531C with its own crystal, but this board takes the SoC's 25 MHz fanout (PH15), as the vendor dts says.

Patches 0023–0028, 0034 and 0035 were written with the help of an AI coding
assistant (Claude). Their commit messages say what was tested, and they carry
no `Signed-off-by`. Patches 0029–0033 keep their upstream authors and sign-offs.

## Nightly builds

`.github/workflows/nightly.yml` runs at 03:30 UTC nightly: pins upstream
`666539eecdf4`, applies the patch series, cross-builds `Image` + dtb +
`modules`, then publishes a rolling `nightly` release with the artifacts.


Board side: NVMe rootfs is mounted on the (SD-booted) board at
`/mnt/nvme-root`; modules live in
`/mnt/nvme-root/lib/modules/7.3.0-ge369c7b14bbe-dirty/extra/` (real dir
`7.3.0-g80c82777a58b-dirty`, `ge369c7b14bbe` is a symlink). UART boot
logs are collected in `~/asdasd` (check md5 before reading — stale-log
trap).
