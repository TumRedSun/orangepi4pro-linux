/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * Vendor systrace hooks, compiled out in this out-of-tree port.
 * sunxi_drm_trace.c is not built, so real tracepoints would leave undefined
 * symbols on kernels with CONFIG_TRACEPOINTS=y.
 */
#ifndef _SUNXI_DRM_TRACE_H_
#define _SUNXI_DRM_TRACE_H_

#define SUNXIDRM_TRACE_END(name)		do { (void)(name); } while (0)
#define SUNXIDRM_TRACE_BEGIN(name)		do { (void)(name); } while (0)
#define SUNXIDRM_TRACE_FUNC()			do { } while (0)
#define SUNXIDRM_TRACE_INT(name, value)		do { (void)(name); (void)(value); } while (0)
#define SUNXIDRM_TRACE_INT_F(name, value)	do { (void)(name); (void)(value); } while (0)
#define SUNXIDRM_TRACE_INT2(name, id, value)	do { (void)(name); (void)(id); (void)(value); } while (0)

#endif /* _SUNXI_DRM_TRACE_H_ */
