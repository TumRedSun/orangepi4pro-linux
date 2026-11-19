#!/bin/bash
# Build the A/B Btrfs image from an Armbian edge image. Runs as root in an unprivileged container.
#   /in/armbian.img   the source Armbian image (ext4 root at 32 MiB)
#   /in/debs          linux-image and linux-dtb packages to put in the good slot
#   /ab               this directory
#   /in/extra         optional: not_logged_in_yet (Armbian presets), authorized_keys
#   /out              the result: boot.fat and root.btrfs
set -euo pipefail
S=/stage/root/@
F=/stage/fat
DTB=sun60i-a733-orangepi-4-pro-armbian.dtb
ID="${PARTID:?}"
rm -rf /stage; mkdir -p "$S" "$F/good"
debugfs -R "rdump / $S" "/in/armbian.img?offset=33554432" 2> /dev/null
[[ -x "$S/usr/bin/systemctl" ]] || { echo "rootfs extraction failed"; exit 1; }

# Kernel: modules into the root, Image and DTB into the good slot.
rm -rf "$S"/usr/lib/modules/*
# Keep /lib -> usr/lib: plain extraction would replace that symlink with a directory.
unpack() { dpkg-deb --fsys-tarfile "$1" | tar -x --keep-directory-symlink -C "$2"; }
unpack /in/debs/linux-image-*.deb "$S"
mkdir -p /stage/dtb
unpack /in/debs/linux-dtb-*.deb /stage/dtb
ver="$(ls "$S/boot" | sed -n 's/^vmlinuz-//p' | head -1)"
cp "$S/boot/vmlinuz-$ver" "$F/good/Image"
cp "/stage/dtb/boot/dtb-$ver/allwinner/$DTB" "$F/good/board.dtb"
printf 'subvol=@\n' > "$F/good/slot.txt"
find "$S/boot" -mindepth 1 -delete
sed "s/PARTID/$ID/" /ab/boot.cmd > "$F/boot.cmd"
cp /in/boot.scr "$F/boot.scr"

# Mounts: Btrfs root (the subvolume comes from the kernel command line) and the FAT slots.
grep -vE '[[:space:]]/[[:space:]]|[[:space:]]/boot[[:space:]]' "$S/etc/fstab" > /stage/fstab || true
{
	echo "PARTUUID=$ID-02 / btrfs defaults,noatime,compress=zstd:1 0 0"
	echo "PARTUUID=$ID-01 /boot vfat defaults,noatime,umask=0022 0 2"
	cat /stage/fstab
} > "$S/etc/fstab"

# Slot tools, first-boot growth, watchdog.
install -m 755 /ab/opi-slot "$S/usr/local/sbin/opi-slot"
install -m 644 /ab/opi-slot-confirm.service /ab/opi-growroot.service "$S/etc/systemd/system/"
mkdir -p "$S/etc/systemd/system/multi-user.target.wants" "$S/etc/systemd/system.conf.d"
ln -sfn /etc/systemd/system/opi-slot-confirm.service "$S/etc/systemd/system/multi-user.target.wants/opi-slot-confirm.service"
ln -sfn /etc/systemd/system/opi-growroot.service "$S/etc/systemd/system/multi-user.target.wants/opi-growroot.service"
ln -sfn /dev/null "$S/etc/systemd/system/armbian-resize-filesystem.service"
install -m 644 /ab/watchdog.conf "$S/etc/systemd/system.conf.d/watchdog.conf"
[[ -x "$S/usr/bin/btrfs" ]] || { echo "btrfs-progs missing in the rootfs"; exit 1; }
for l in bin lib sbin; do [[ -L "$S/$l" ]] || { echo "/$l is not a symlink"; exit 1; }; done
[[ -e "$S/lib/ld-linux-aarch64.so.1" && -e "$S/sbin/init" ]] || { echo "init or the loader is missing"; exit 1; }

if [[ -f /in/extra/not_logged_in_yet ]]; then
	install -m 600 /in/extra/not_logged_in_yet "$S/root/.not_logged_in_yet"
fi
if [[ -f /in/extra/authorized_keys ]]; then
	install -d -m 700 "$S/root/.ssh"
	install -m 600 /in/extra/authorized_keys "$S/root/.ssh/authorized_keys"
fi

mkdir -p /out
rm -f /out/root.btrfs /out/boot.fat
truncate -s 6G /out/root.btrfs
mkfs.btrfs -q -f -L armbi_root -r /stage/root --subvol rw:@ /out/root.btrfs
truncate -s 256M /out/boot.fat
mkfs.vfat -F 32 -n BOOT /out/boot.fat > /dev/null
mcopy -s -i /out/boot.fat "$F"/* ::/
chown "$OWNER" /out/root.btrfs /out/boot.fat
echo "kernel $ver, root files $(find "$S" | wc -l)"
mdir -/ -i /out/boot.fat ::/ | grep -E 'Image|dtb|slot|boot' | head -8
