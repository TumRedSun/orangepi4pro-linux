#!/usr/bin/python3 -I
"""Hardware tests for the Orange Pi 4 Pro on the mainline kernel. Run as root on the board.

Results:
    PASS  the feature works
    FAIL  the feature is present and broken
    SKIP  the test needs something that is not connected
    GAP   the kernel does not support the feature yet

Exit status: 0 no FAIL, 1 at least one FAIL, 2 not run as root.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time

DT = "/sys/firmware/devicetree/base"
RESULTS = []
TESTS = []


class Outcome(Exception):
    def __init__(self, status, detail=""):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def skip(detail):
    raise Outcome("SKIP", detail)


def gap(detail):
    raise Outcome("GAP", detail)


def ok(detail=""):
    raise Outcome("PASS", detail)


def check(condition, detail):
    if not condition:
        raise Outcome("FAIL", detail)


def test(group, name, disruptive=False):
    def add(func):
        TESTS.append((group, name, func, disruptive))
        return func
    return add


def read(path, default=""):
    try:
        with open(path, errors="replace") as handle:
            return handle.read().strip().strip("\0")
    except OSError:
        return default


def sh(command, timeout=30):
    try:
        done = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL, check=False)
        return done.returncode, done.stdout + done.stderr
    except subprocess.TimeoutExpired:
        return 124, ""


def dmesg():
    return sh("dmesg")[1]


def dt_nodes(pattern):
    return glob.glob(f"{DT}/soc/{pattern}")


def dt_enabled(pattern):
    return [n for n in dt_nodes(pattern) if read(f"{n}/status", "okay") in ("okay", "ok")]


def clk(name):
    return read(f"/sys/kernel/debug/clk/{name}/clk_rate")


def default_gateway(dev):
    match = re.search(r"default via (\S+)", sh(f"ip -4 route show dev {dev}")[1])
    return match.group(1) if match else ""


def ipv4(dev):
    match = re.search(r"inet (\S+)/", sh(f"ip -4 addr show {dev}")[1])
    return match.group(1) if match else ""


# System
@test("system", "mainline 7.x kernel")
def t_kernel():
    release = os.uname().release
    check(release.startswith("7."), release)
    ok(release)


@test("system", "all 8 CPU cores online")
def t_cpus():
    online = read("/sys/devices/system/cpu/online")
    check(online == "0-7", f"online: {online}")
    ok(online)


@test("system", "systemd reached running")
def t_systemd():
    state = sh("systemctl is-system-running")[1].strip()
    failed = sh("systemctl --failed --no-legend --plain")[1].strip()
    check(state == "running", f"{state}; {failed[:160]}")


@test("system", "no kernel crash in the log")
def t_oops():
    hits = re.findall(r"Unable to handle|Internal error|Call trace|Kernel panic|soft lockup|hung_task", dmesg())
    check(not hits, f"{len(hits)} lines, first: {hits[0] if hits else ''}")


@test("system", "BL31 memory is reserved")
def t_bl31():
    check(os.path.isdir(f"{DT}/reserved-memory/bl31@48000000"), "no reserved-memory node")


# Clocks and power
@test("power", "board clock rates")
def t_clocks():
    wanted = {"dcxo": "26000000", "pll-ref": "24000000", "pll-peri0": "2400000000"}
    wrong = {k: clk(k) for k, v in wanted.items() if clk(k) != v}
    check(not wrong, str(wrong))


@test("power", "AXP318W PMIC is bound")
def t_pmic():
    check(os.path.exists("/sys/bus/i2c/drivers/axp20x-i2c/0-0036"), "driver not bound")


@test("power", "board regulators")
def t_regulators():
    names = {read(p) for p in glob.glob("/sys/class/regulator/regulator.*/name")}
    missing = {"vcc-3v3-phy", "vcc-3v3-sd", "vcc-pg", "vcc-pm", "vcc-wifi"} - names
    check(not missing, f"missing {sorted(missing)}")


# CPU frequency and temperature
@test("cpu", "frequency scaling")
def t_cpufreq():
    policies = glob.glob("/sys/devices/system/cpu/cpufreq/policy*")
    if not policies:
        gap("no cpufreq policy")
    check(len(policies) == 2, f"{len(policies)} policies")
    ok(", ".join(f"{os.path.basename(p)} max {int(read(p + '/cpuinfo_max_freq')) // 1000} MHz" for p in sorted(policies)))


@test("cpu", "frequency changes under load")
def t_cpufreq_load():
    policies = sorted(glob.glob("/sys/devices/system/cpu/cpufreq/policy*"))
    if not policies:
        gap("no cpufreq policy")
    load = subprocess.Popen(["sh", "-c", "while :; do :; done"])
    try:
        time.sleep(2)
        seen = {int(read(f"{p}/scaling_cur_freq", "0")) for p in policies}
    finally:
        load.kill()
        load.wait()
    check(max(seen) > 0, "no frequency reported")
    ok(f"{max(seen) // 1000} MHz")


@test("cpu", "CPU clock rate is reported")
def t_cpu_clock():
    rates = {name: int(clk(name) or 0) for name in ("cpu-l", "cpu-b")}
    check(all(rates.values()), str(rates))
    ok(", ".join(f"{k} {v // 1000000} MHz" for k, v in rates.items()))


@test("cpu", "temperature sensors")
def t_thermal():
    zones = glob.glob("/sys/class/thermal/thermal_zone*")
    if not zones:
        gap("no thermal zone")
    temps = {read(z + "/type"): int(read(z + "/temp", "0")) / 1000 for z in zones}
    bad = {k: v for k, v in temps.items() if not 5 <= v <= 100}
    check(not bad, f"out of range: {bad}")
    ok(", ".join(f"{k} {v:.0f}C" for k, v in sorted(temps.items())))


# SD card
@test("storage", "SD card is the root device")
def t_root():
    source = sh("findmnt -no SOURCE /")[1].strip()
    check("mmcblk2" in source, source)
    ok(source)


@test("storage", "SD card read speed")
def t_sd_read():
    code, out = sh("dd if=/dev/mmcblk2 of=/dev/null bs=1M count=64 iflag=direct 2>&1", 60)
    check(code == 0, out[-120:])
    match = re.search(r"([\d.,]+) ([MG])B/s", out)
    speed = float(match.group(1).replace(",", ".")) * (1000 if match.group(2) == "G" else 1)
    check(speed > 5, f"{speed} MB/s")
    ok(f"{speed:.0f} MB/s")


@test("storage", "SD card write and read back")
def t_sd_write():
    path = "/var/tmp/opi4pro-test.bin"
    data = os.urandom(16 * 1024 * 1024)
    try:
        with open(path, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        sh(f"echo 3 > /proc/sys/vm/drop_caches; sync")
        with open(path, "rb") as handle:
            check(hashlib.sha256(handle.read()).digest() == hashlib.sha256(data).digest(), "data differs")
    finally:
        if os.path.exists(path):
            os.unlink(path)


@test("storage", "no SD card errors in the log")
def t_sd_errors():
    hits = re.findall(r"mmc2.*(?:error|timeout|crc)|mmcblk2.*error|I/O error", dmesg(), re.I)
    check(not hits, hits[0] if hits else "")


# PCIe and NVMe
@test("storage", "PCIe link")
def t_pcie():
    if not dt_enabled("pcie@*"):
        gap("PCIe is not enabled")
    devices = glob.glob("/sys/bus/pci/devices/*")
    check(devices, "no PCI device")
    ok(f"{len(devices)} devices")


@test("storage", "NVMe drive read speed")
def t_nvme():
    drives = sorted(glob.glob("/sys/block/nvme*n1"))
    if not drives:
        skip("no NVMe drive")
    name = os.path.basename(drives[0])
    code, out = sh(f"dd if=/dev/{name} of=/dev/null bs=1M count=256 iflag=direct 2>&1", 60)
    check(code == 0, out[-120:])
    ok(out.strip().splitlines()[-1].split(",")[-1].strip())


# Ethernet
@test("ethernet", "PHY driver and link")
def t_eth_link():
    check(read("/sys/class/net/eth0/carrier") == "1", "no carrier")
    phy = os.path.basename(os.path.realpath("/sys/class/net/eth0/phydev/driver"))
    check("YT8531" in phy, phy)
    ok(f"{read('/sys/class/net/eth0/speed')} Mb/s")


@test("ethernet", "stable MAC address from the SoC ID")
def t_eth_mac():
    mac = read("/sys/class/net/eth0/address")
    check(int(mac[:2], 16) & 2 and not int(mac[:2], 16) & 1, mac)
    check("ethernet" in sh("dmesg | grep -i 'random MAC' || echo ethernet")[1], "kernel used a random MAC")
    ok(mac)


@test("ethernet", "gateway answers")
def t_eth_gw():
    if not ipv4("eth0"):
        skip("eth0 has no address")
    gateway = default_gateway("eth0")
    check(gateway, "no default route")
    check(sh(f"ping -I eth0 -c 3 -W 2 {gateway}")[0] == 0, f"{gateway} does not answer")


@test("ethernet", "no packet errors")
def t_eth_errors():
    stats = {k: int(read(f"/sys/class/net/eth0/statistics/{k}", "0")) for k in ("rx_errors", "tx_errors", "rx_crc_errors")}
    check(not any(stats.values()), str(stats))


@test("ethernet", "link recovers after down and up", disruptive=True)
def t_eth_cycle():
    if not ipv4("wlan0"):
        skip("needs Wi-Fi as the second connection")
    gateway = default_gateway("eth0")
    sh("ip link set eth0 down; sleep 3; ip link set eth0 up", 15)
    for _ in range(30):
        time.sleep(2)
        if ipv4("eth0") and sh(f"ping -I eth0 -c 1 -W 2 {gateway or '192.168.1.1'}")[0] == 0:
            ok()
    check(False, "eth0 did not recover in 60 s")


# Wi-Fi
@test("wifi", "AIC8800 driver and interface")
def t_wifi_if():
    check(os.path.isdir("/sys/module/aic8800_fdrv"), "driver not loaded")
    check(os.path.isdir("/sys/class/net/wlan0"), "no wlan0")
    ok(read("/sys/class/net/wlan0/address"))


@test("wifi", "SDIO runs at 50 MHz")
def t_wifi_sdio():
    ios = read("/sys/kernel/debug/mmc0/ios")
    match = re.search(r"actual clock:\s+(\d+)", ios)
    check(match and match.group(1) == "50000000", match.group(1) if match else "no clock")


@test("wifi", "scan finds networks")
def t_wifi_scan():
    for _ in range(5):
        count = len(re.findall(r"^BSS ", sh("iw dev wlan0 scan", 20)[1], re.M))
        if count:
            ok(f"{count} networks")
        time.sleep(3)
    check(False, "no network found")


@test("wifi", "connected and gateway answers")
def t_wifi_link():
    link = sh("iw dev wlan0 link")[1]
    if "Connected" not in link:
        skip("not connected to a network")
    gateway = default_gateway("wlan0")
    check(gateway and sh(f"ping -I wlan0 -c 3 -W 3 {gateway}")[0] == 0, "gateway does not answer")
    ok(re.search(r"freq: (\d+)", link).group(1) + " MHz")


# Bluetooth
def bt_ready():
    return sh("sleep 1 | btmgmt info", 8)[1]


@test("bluetooth", "service is active")
def t_bt_service():
    check(sh("systemctl is-active aic8800-bluetooth")[1].strip() == "active", "service is not active")


@test("bluetooth", "BlueZ can use the controller")
def t_bt_mgmt():
    info = bt_ready()
    check(re.search(r"^hci0", info, re.M), "no hci0 in btmgmt")
    ok(read("/sys/class/bluetooth/hci0/address"))


@test("bluetooth", "scan receives advertisements")
def t_bt_scan():
    sniff = subprocess.Popen(["timeout", "14", "btmon"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    sh("(echo 'scan on'; sleep 10; echo 'scan off') | timeout 12 bluetoothctl", 15)
    out = sniff.communicate(timeout=20)[0]
    count = out.count("Advertising Report")
    if not count:
        skip("no Bluetooth device nearby")
    ok(f"{count} advertisements")


# Display
@test("display", "HDMI driver and DRM device")
def t_hdmi():
    check(os.path.isdir("/sys/module/sunxidrm"), "driver not loaded")
    check(os.path.exists("/dev/dri/card0"), "no /dev/dri/card0")


@test("display", "monitor mode and framebuffer")
def t_monitor():
    connector = "/sys/class/drm/card0-HDMI-A-1"
    if read(f"{connector}/status") != "connected":
        skip("no monitor connected")
    check(os.path.exists("/dev/fb0"), "no /dev/fb0")
    ok(read(f"{connector}/modes").splitlines()[0])


# Features still being added
@test("usb", "USB host controllers")
def t_usb():
    if not dt_nodes("usb@*"):
        gap("no USB nodes in the device tree")
    hubs = glob.glob("/sys/bus/usb/devices/usb*")
    check(hubs, "no USB root hub")
    ok(f"{len(hubs)} root hubs")


@test("usb", "USB storage read")
def t_usb_storage():
    if not dt_nodes("usb@*"):
        gap("no USB nodes in the device tree")
    disks = [d for d in glob.glob("/sys/block/sd*") if "/usb" in os.path.realpath(d)]
    if not disks:
        skip("no USB disk connected")
    name = os.path.basename(disks[0])
    code, out = sh(f"dd if=/dev/{name} of=/dev/null bs=1M count=64 iflag=direct 2>&1", 60)
    check(code == 0, out[-120:])
    ok(out.strip().splitlines()[-1].split(",")[-1].strip())


@test("peripherals", "SPI-NOR flash reads the same data twice")
def t_spi():
    if not dt_nodes("spi@*"):
        gap("no SPI nodes in the device tree")
    check(os.path.exists("/dev/mtd0"), "no MTD device")
    sums = {sh("dd if=/dev/mtd0 bs=64k count=16 2>/dev/null | sha256sum")[1] for _ in range(2)}
    check(len(sums) == 1, "reads differ")
    ok(f"{int(read('/sys/class/mtd/mtd0/size')) // 1048576} MB")


@test("peripherals", "SPI-NOR flash is read-only")
def t_spi_ro():
    if not dt_nodes("spi@*"):
        gap("no SPI nodes in the device tree")
    flags = int(read("/sys/class/mtd/mtd0/flags", "0x400"), 16)
    check(not flags & 0x400, f"writeable, flags {flags:#x}")


@test("peripherals", "real-time clock")
def t_rtc():
    check(os.path.exists("/sys/class/rtc/rtc0"), "no rtc0")
    first = int(read("/sys/class/rtc/rtc0/since_epoch", "0"))
    time.sleep(2.2)
    second = int(read("/sys/class/rtc/rtc0/since_epoch", "0"))
    check(second > first > 0, f"{first} then {second}")


@test("peripherals", "hardware random number generator")
def t_rng():
    if not (dt_nodes("crypto@*") or dt_nodes("ce@*")):
        gap("no crypto engine in the device tree")
    check(os.path.exists("/dev/hwrng"), "no /dev/hwrng")


@test("peripherals", "PWM controllers")
def t_pwm():
    if not dt_nodes("pwm@*"):
        gap("no PWM nodes in the device tree")
    check(glob.glob("/sys/class/pwm/pwmchip*"), "no PWM chip")


@test("peripherals", "ADC")
def t_adc():
    if not dt_nodes("adc@*"):
        gap("no ADC nodes in the device tree")
    raw = read("/sys/bus/iio/devices/iio:device0/in_voltage0_raw")
    check(raw.isdigit() and int(raw) <= 4095, f"raw value: {raw!r}")
    ok(f"channel 0 raw {raw}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--disruptive", action="store_true", help="also run tests that interrupt the network")
    parser.add_argument("--only", help="run one group")
    parser.add_argument("--json", help="write the results to this file")
    args = parser.parse_args()
    if os.geteuid() != 0:
        print("run as root")
        return 2
    sh("mountpoint -q /sys/kernel/debug || mount -t debugfs debugfs /sys/kernel/debug")

    for group, name, func, disruptive in TESTS:
        if args.only and group != args.only:
            continue
        if disruptive and not args.disruptive:
            continue
        start = time.monotonic()
        try:
            func()
            status, detail = "PASS", ""
        except Outcome as outcome:
            status, detail = outcome.status, outcome.detail
        except Exception as error:  # a broken test must not stop the run
            status, detail = "FAIL", f"{type(error).__name__}: {error}"
        RESULTS.append({"group": group, "test": name, "status": status, "detail": detail,
                        "seconds": round(time.monotonic() - start, 1)})
        print(f"{status:4}  {group:11} {name}" + (f"  ({detail})" if detail else ""), flush=True)

    counts = {s: sum(r["status"] == s for r in RESULTS) for s in ("PASS", "FAIL", "SKIP", "GAP")}
    print("RESULT " + " ".join(f"{k}={v}" for k, v in counts.items()))
    if args.json:
        with open(args.json, "w") as handle:
            json.dump({"kernel": os.uname().release, "time": time.strftime("%F %T"), "counts": counts,
                       "results": RESULTS}, handle, indent=1)
    return 1 if counts["FAIL"] else 0


sys.exit(main())
