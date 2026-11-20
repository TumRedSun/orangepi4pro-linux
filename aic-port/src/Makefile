# AIC8800D80 SDIO Wi-Fi for the Orange Pi 4 Pro on mainline Linux.
# Build: make -C /lib/modules/$(uname -r)/build M=$PWD modules
export CONFIG_AIC_WLAN_SUPPORT := m
export CONFIG_AIC8800_WLAN_SUPPORT := m
export CONFIG_AIC_INTF_SDIO := y
# Keep the vendor's Allwinner build options. The sunxi-rf calls are removed:
# on mainline the device tree powers the chip.
export CONFIG_AW_BSP := y
export CONFIG_AIC8800_BTLPM_SUPPORT := m

obj-m += aic8800_bsp/
obj-m += aic8800_fdrv/
obj-m += aic8800_btlpm/
