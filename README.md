# snopyrator: a command line tool and library for the SN Operator


## ℹ️ Information

SNOpyrator is a versatile Python package that allows you to manage and control the SN Operator from [Epilogue](https://www.epilogue.co/) via the command line. It currently supports **Super Nintendo** and **Super Famicom** games !

SNOpyrator is also available as a **library** so that you can integrate it into your own projects!

## ⬇️ Installation

```bash
pip install snopyrator
```

## 🕹️ Usage

### As a CLI tool

Each flag is optional. Running `snopyrator` without any flags simply outputs the cartridge info. Here is an example of all the available flags or options.

```bash
snopyrator \
    --dump-rom rom.sfc              # dump the ROM to rom.sfc file \
    --dump-save save.sav            # dump the RAM (save) to file \
    --write-save save_backup.sav    # read the file save_backup.sav and upload it to the cartridge RAM (save) \
```

### As a library

For detailed information on utilising SNOpyrator as a **library**, please refer to the [DOC.md](DOC.md) file.
