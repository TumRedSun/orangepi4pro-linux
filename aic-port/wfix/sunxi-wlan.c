// SPDX-License-Identifier: GPL-2.0
/*
 * Minimal counterpart of sunxi's bsp sunxi-wlan driver, providing only
 * the power/scan/irq primitives needed by the AIC8800 drivers:
 *   - sunxi_wlan_set_power()   (gpio power sequence)
 *   - sunxi_wlan_get_bus_index()
 *   - sunxi_mmc_rescan_card()  (retrigger mmc host slot detection)
 *   - sunxi_wlan_get_oob_irq(int *irq_flags, int *wakup_enable)
 */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/of.h>
#include <linux/gpio/consumer.h>
#include <linux/irq.h>
#include <linux/delay.h>
#include <linux/mmc/host.h>
#include <linux/mmc/card.h>
#include <linux/slab.h>
#include <linux/mutex.h>
#include <linux/device/bus.h>
#include <linux/of_platform.h>

struct sunxi_wlan {
	struct platform_device *pdev;
	struct gpio_desc *regon;
	struct gpio_desc *hostwake;
	int bus_index;
	struct device *mmc_dev;
	bool power_state;
};

static DEFINE_MUTEX(sunxi_mutex);
static struct sunxi_wlan *wlan_data;

void *sunxi_wlan_get_mmc_drvdata(void)
{
	struct sunxi_wlan *data = wlan_data;
	if (!data || !data->mmc_dev)
		return NULL;
	return dev_get_drvdata(data->mmc_dev);
}
EXPORT_SYMBOL_GPL(sunxi_wlan_get_mmc_drvdata);

void sunxi_mmc_rescan_card(unsigned id)
{
	struct sunxi_wlan *data = wlan_data;
	if (!data || !data->mmc_dev) {
		pr_err("sunxi-wlan: no mmc device for scan\n");
		return;
	}
	if (id != (unsigned)data->bus_index)
		return;
	{
		struct mmc_host *mmc = dev_get_drvdata(data->mmc_dev);
		if (mmc)
			mmc_detect_change(mmc, msecs_to_jiffies(20));
	}
}
EXPORT_SYMBOL_GPL(sunxi_mmc_rescan_card);

void sunxi_wlan_set_power(bool on_off)
{
	struct sunxi_wlan *data = wlan_data;

	if (!data)
		return;

	mutex_lock(&sunxi_mutex);
	if (on_off != data->power_state) {
		gpiod_direction_output(data->regon, on_off ? 1 : 0);
		mdelay(on_off ? 50 : 10);
		data->power_state = on_off;
	}
	mutex_unlock(&sunxi_mutex);
}
EXPORT_SYMBOL_GPL(sunxi_wlan_set_power);

int sunxi_wlan_get_bus_index(void)
{
	if (!wlan_data)
		return -EINVAL;
	return wlan_data->bus_index;
}
EXPORT_SYMBOL_GPL(sunxi_wlan_get_bus_index);

int sunxi_wlan_get_oob_irq(int *irq_flags, int *wakup_enable)
{
	int irq_num;

	if (!wlan_data || !wlan_data->hostwake) {
		if (irq_flags) *irq_flags = 0;
		if (wakup_enable) *wakup_enable = 0;
		return 0;
	}

	irq_num = gpiod_to_irq(wlan_data->hostwake);
	if (irq_num < 0) {
		if (irq_flags) *irq_flags = 0;
		if (wakup_enable) *wakup_enable = 0;
		return 0;
	}

	if (irq_flags)
		*irq_flags = IRQF_TRIGGER_HIGH;
	if (wakup_enable)
		*wakup_enable = 1;
	return irq_num;
}
EXPORT_SYMBOL_GPL(sunxi_wlan_get_oob_irq);

static int sunxi_wlan_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct device_node *mnode = NULL;
	struct platform_device *mpdev = NULL;
	struct sunxi_wlan *data;
	u32 busnum = 0;

	data = devm_kzalloc(dev, sizeof(struct sunxi_wlan), GFP_KERNEL);
	if (!data)
		return -ENOMEM;
	data->pdev = pdev;

	data->regon = devm_gpiod_get_optional(dev, "wlan-regon", GPIOD_OUT_LOW);
	if (IS_ERR(data->regon)) {
		int ret = PTR_ERR(data->regon);
		return ret;
	}
	data->hostwake = devm_gpiod_get_optional(dev, "wlan-hostwake", GPIOD_IN);
	if (IS_ERR(data->hostwake))
		data->hostwake = NULL;

	if (device_property_read_u32(dev, "wlan_busnum", &busnum) == 0)
		data->bus_index = busnum;

	mnode = of_parse_phandle(dev->of_node, "wlan_mmc", 0);
	if (mnode) {
		mpdev = of_find_device_by_node(mnode);
		if (mpdev) {
			data->mmc_dev = &mpdev->dev;
			pr_info("sunxi-wlan: rescan target %s\n", dev_name(&mpdev->dev));
		} else {
			pr_err("sunxi-wlan: mmc dev not found\n");
		}
		of_node_put(mnode);
	} else {
		data->bus_index = -EINVAL;
	}

	platform_set_drvdata(pdev, data);
	wlan_data = data;

	return 0;
}

static void sunxi_wlan_remove(struct platform_device *pdev)
{
	wlan_data = NULL;
}

static const struct of_device_id sunxi_wlan_dt_match[] = {
	{ .compatible = "allwinner,sunxi-wlan" },
	{},
};
MODULE_DEVICE_TABLE(of, sunxi_wlan_dt_match);

static struct platform_driver sunxi_wlan_driver = {
	.probe = sunxi_wlan_probe,
	.remove = sunxi_wlan_remove,
	.driver = {
		.name = "sunxi-wlan",
		.of_match_table = sunxi_wlan_dt_match,
	},
};

module_platform_driver(sunxi_wlan_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("sunxi wlan power/scan helper for AIC8800");
