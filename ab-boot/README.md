# A/B kernel slots with automatic fallback

Test a new kernel without reflashing. A kernel that fails to load, panics or hangs falls
back to the last good kernel on its own. This works with the vendor U-Boot 2018.

## Layout

| Partition | Contents |
|---|---|
| 1, FAT | `boot.scr`, `trial.txt`, and the slots `good/`, `trial/`, `prev/`, each with `Image`, `board.dtb` and `slot.txt` |
| 2, Btrfs | One root subvolume per slot. `slot.txt` names it, for example `subvol=@` |

Each slot has its own root snapshot, so the fallback kernel always has its own modules.

## How a trial works

1. `opi-slot try linux-image.deb linux-dtb.deb` snapshots the running root, installs the
   kernel into the snapshot, fills `trial/`, and writes `trial=armed` to `trial.txt`.
2. On the next boot U-Boot rewrites `trial.txt` to `trial=tried`, then boots the trial slot.
3. `opi-slot-confirm.service` promotes the trial when `multi-user.target` is reached and a
   network route exists. The old good slot becomes `prev`.
4. A trial that panics reboots after 10 s (`panic=10`). A later hang reboots through the
   systemd watchdog (`watchdog.conf`). Either way `trial=tried` makes U-Boot boot `good`.

A hang before the watchdog starts still needs one power cycle.

## Commands

```
opi-slot status      # booted slot and the slot contents
opi-slot try IMAGE.deb DTB.deb
opi-slot rollback    # swap good and prev, then reboot
opi-slot clean       # delete root snapshots that no slot uses
```

Files copied onto a running trial land in the trial's root snapshot, not in the good one.

## Vendor U-Boot limits

- `fatwrite` only writes plain names in the top directory. A leading `/` becomes part of the
  name, and paths in subdirectories are not written. That is why the state is `trial.txt`.
- There is no `bootcount`, so the boot script keeps the state itself.
- A kernel started by hand from the U-Boot prompt hangs early. Only the boot script works.

## Building the image

`build-image.sh` runs as root in an unprivileged container. It takes the ext4 root from an
Armbian edge image, adds the kernel packages and these tools, and writes `boot.fat` and
`root.btrfs`. First-login answers (`/in/extra/not_logged_in_yet`) and an SSH key
(`/in/extra/authorized_keys`) are optional; an image with them is private.
