# Künye

**[Türkçe](README.md)** · English

An open-source **patient wristband, barcode and label printer** for Pardus and
other Debian-based GNU/Linux systems.

Hospitals usually print wristbands, lab tube labels, medication labels and file
labels with licensed Windows software such as BarTender or NiceLabel. Künye does
the same job on Pardus for free. *Künye* is what Turkish hospital staff call a
patient identification wristband.

![Main window (sample data, not real patients)](docs/ekran-goruntuleri/02-bileklik.png)

> **Status: early development (0.1).** Label rendering, barcodes and the
> interface are covered by automated tests, but Künye **has not been tried on a
> real label printer yet.** Print and scan a test label on your own printer
> before using it with patients.

The interface and the documentation are in Turkish, as the program is written
for Turkish hospitals. The source code is commented in Turkish as well.

## Highlights

- Ready-made templates: adult and infant wristbands, lab tube, medication/IV
  label, patient file label. Custom templates are plain JSON.
- Every label is rendered to a 1-bit bitmap at the printer's resolution, so
  Turkish characters print correctly on any printer and the preview matches
  the printout exactly.
- Code 128 and QR codes; every built-in template's barcodes are decoded with
  zbar in the test suite at 203 and 300 dpi.
- Zebra printers over TCP port 9100 or a raw CUPS queue (ZPL `^GF` with Z64
  compression); other thermal printers through their CUPS driver.
- Batch printing from CSV (`;`/`,`, UTF-8 or Windows-1254).
- Turkish national ID numbers can be masked on the label (`*******8901`).
  Nothing is sent anywhere except the selected printer.
- GTK 4 + libadwaita desktop app and a command line tool.

## Installation

```sh
curl -fsSL https://raw.githubusercontent.com/muratGursel/kunye/main/install.sh | sudo sh
```

or download `kunye_*_all.deb` from
[Releases](https://github.com/muratGursel/kunye/releases) and run
`sudo apt install ./kunye_*_all.deb`.

Printers are configured in `/etc/kunye/yazicilar.json` or
`~/.config/kunye/yazicilar.json`; see [docs/YAZICILAR.md](docs/YAZICILAR.md)
for the format.

## License

GPL-3.0-or-later. BarTender, NiceLabel and Zebra are trademarks of their
respective owners; this project is not affiliated with them.
