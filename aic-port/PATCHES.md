# AIC8800D80 port for mainline Linux 7.4

`src/` holds the ported drivers. `vendor-src/` is the untouched vendor tree.

Build against a configured kernel tree:

```
make -C <kernel> M=$PWD/aic-port/src modules
```

This produces `aic8800_bsp.ko`, `aic8800_fdrv.ko` and `aic8800_btlpm.ko`.

## Changes from the vendor sources

- **Power:** the sunxi-rf calls are gone. The device tree powers the chip through `vmmc-supply`,
  with WL_REG_ON (PM1) as the regulator enable. The `sunxi-wlan` helper in `wfix/` is no longer used.
- **Interrupts:** the driver uses the in-band SDIO interrupt, with no host-wake IRQ.
- **cfg80211 7.4:** key callbacks take `enum nl80211_key_type`. Cookies for `mgmt_tx` and
  `remain_on_channel` are chosen by cfg80211 and stored by the driver. `probe_client` is removed.
- **Other API updates:** `strncpy`, `ndo_do_ioctl`, `cfg80211_probe_status` and the flattened
  `ieee80211_mgmt` action fields.
- **Bluetooth:** firmware low-power mode is off (`lpm_enable = 0`).
- **`aic8800_btlpm`:** uses the gpiod API and the `bt-wake-gpios` and `bt-hostwake-gpios` properties.
  It no longer touches the UART port, which the tty layer owns.

The vendor `aic_bsp_helper.c`, which embeds prebuilt binaries, is not included in `src/`.

## Runtime

Firmware comes from `armbian-firmware`, linked as `/lib/firmware/aic8800d80`.
Armbian's `aic8800-bluetooth` service attaches Bluetooth on `ttyS1` at 1.5 Mbaud.
