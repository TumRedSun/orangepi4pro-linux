#include <linux/fb.h>
#include <drm/drm_device.h>

int sunxi_fbdev_init(struct drm_device *drm, void *out_state, int de_id)
{
	return 0;
}

struct fb_info *sunxi_get_fb_info(int fb_id)
{
	return NULL;
}

int sunxi_fb_pan_display(struct fb_var_screeninfo *var, struct fb_info *info)
{
	return 0;
}
