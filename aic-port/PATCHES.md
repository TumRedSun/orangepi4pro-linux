# AIC8800 port fixes (kernel 7.3, aarch64)

The patched vendor sources lived in `/tmp` and were wiped; this file
documents every fix so the port can be reproduced from `vendor-src/`.
Target kernel: mainline 7.3.0 (`e369c7b14` in the patch series), no
MODVERSIONS, no module signing.

Board: OrangePi 4 Pro (Allwinner A733 / SUN60IW2), wifi+bt = AIC8800 on
SDIO bus 1 (mmc1).

## Module load order

```
sunxi-wlan.ko  ->  aic8800_bsp.ko  ->  aic8800_fdrv.ko
                                ->  aic8800_btlpm.ko
```

`modules.dep` entry: `extra/aic8800_fdrv.ko: extra/aic8800_bsp.ko extra/sunxi-wlan.ko`

## 1. New helper module `sunxi-wlan` (see `wfix/`)

Out-of-tree module, single `.c`. Exports:

- `sunxi_wlan_set_power(int bus_index, bool on)`
- `sunxi_wlan_get_bus_index(void)`
- `sunxi_wlan_get_oob_irq(int *irq, int *flags)`
- `sunxi_wlan_get_mmc_drvdata(int bus_index)` — returns `struct mmc_host *`
- `sunxi_mmc_rescan_card(unsigned id)` — wraps `mmc_detect_change`

DT-driven: reads `wlan-regon-gpios`, `wlan-hostwake-gpios`, `wlan_busnum`,
and the `wlan_mmc` phandle to reach the mmc host. Nodes live in
`kernel/patches/0021-*.patch` (root-level `sunxi-wlan` + `btlpm` nodes in
the board dts).

Gotcha: never pass a `struct fwnode_handle *` to `printk` with the `%pfw`
fancy format — it IABT-oopses this kernel at probe ("Unable to handle
kernel execute from non-executable memory" in `sunxi_mmc_driver+0x28`).
Use `dev_name(dev)` instead.

## 2. `aic8800_bsp` (aicsdio.c)

1. Power-on path looked the host up with removed `of_find_node_by_type("sdc%d")`.
   Replace with `sunxi_wlan_get_mmc_drvdata(sunxi_wlan_get_bus_index())`.
2. Mainline `sunxi-mmc.c` does `platform_set_drvdata(pdev, mmc)` (line ~1375),
   so the helper returns the `mmc_host` directly — do NOT deref
   `*(host->private)` (that was the vendor-bsp trick on 5.15).

## 3. `aic8800_fdrv` (rwnx_*)

1. `rwnx_msg_tx.c`: `strncpy(req->error, msg, sizeof(req->error))` ->
   `strscpy(req->error, msg, sizeof(req->error))` (gcc-14 -Werror).
2. `rwnx_main.c`: `cfg80211_probe_status()` is now 8-arg; pass `link_id = -1`.
3. `rwnx_main.c`: remove `.probe_client` from `struct cfg80211_ops`
   (dropped in mainline).
4. Cookie semantics: `mgmt_tx()` / `remain_on_channel()` must pass the
   cookie **by value** (not by pointer); thread the result back through
   `roc_elem->cookie` (`rwnx_defs.h` + `rwnx_main.c` + `rwnx_msg_rx.c`).
5. TDLS: `ieee80211_mgmt.u.action` is flattened per-action unions now —
   `mgmt->u.action.<n>.…` with the outer `.action_code`.
6. `wlan_get_oob_irq()` wiring goes through the helper (above), not the
   vendor sunxi-rf module.

## 4. `aic8800_btlpm`

Legacy `gpio_request`/`gpio_set_value` API is gone -> convert to
`devm_gpiod_get`/`gpiod_set_raw_value`; UART serial must be resolved from
the `serial0`/`serial1` aliases, not the vendor `of_alias` helpers.

## Deploy layout (on the NVMe rootfs)

```
/lib/modules/7.3.0-ge369c7b14bbe-dirty/extra/
    aic8800_bsp.ko aic8800_btlpm.ko aic8800_fdrv.ko sunxi-wlan.ko
    (+ cec.ko, drm_display_helper.ko and the drm chain for sunxidrm —
     built from the mainline tree: drivers/media/cec/core,
     drivers/gpu/drm/display; the sunxi-drm driver itself lives in
     its own repo)
/etc/conf.d/modules = "sunxidrm aic8800_fdrv aic8800_btlpm"
```

Note: `sunxi-wlan` must NOT be in `conf.d/modules` — it is pulled in
automatically by `modprobe aic8800_fdrv` via `modules.dep`.

DTB md5 at last deploy: `de54b62e` (wlan nodes included), Image md5 `da253ed6`.
