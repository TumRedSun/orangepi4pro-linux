# USB network and serial console on the blue OTG port

Connect the board's blue OTG port to a PC with a USB cable. The PC sees a USB network
adapter and a serial port. The board answers on `10.55.0.1` and gives the PC an address
by DHCP, so `ssh root@10.55.0.1` works over the cable alone.

Needs kernel patch 0051 (USB0 in peripheral mode) and the `dnsmasq-base` package.

| File | Install as |
|---|---|
| `opi-usb-gadget` | `/usr/local/sbin/opi-usb-gadget` (mode 755) |
| `opi-usb-gadget.service` | `/etc/systemd/system/`, enable it |
| `85-opi-usb-gadget-managed.rules` | `/etc/udev/rules.d/` |
| `usb-gadget.nmconnection` | `/etc/NetworkManager/system-connections/` (mode 600) |

Also enable `serial-getty@ttyGS0.service` for a login prompt on the PC's `/dev/ttyACM0`.

While the port is a USB device, a USB drive plugged into it does not work.
Tested on an Orange Pi 4 Pro with Armbian trixie: high-speed link, ping about 2 ms, SSH works.
