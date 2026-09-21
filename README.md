# ORGBRO X1 Text Labels

An unofficial, independent Windows application for printing simple one-, two-
or three-line text labels on the ORGBRO X1 label printer.

The program works locally without an account or cloud service. It connects to
an already paired printer through its Bluetooth Classic serial port (SPP).

> This project is not affiliated with, endorsed by, or supported by ORGBRO,
> XEasyLabel, or their respective owners.

## Features

- one to three text lines
- automatic font sizing
- print preview
- direct printing through a Windows COM port
- remembers the last entered text locally
- button to clear all fields
- no network or cloud connection

## Requirements

- Windows 10 or Windows 11
- ORGBRO X1 paired through Bluetooth Classic
- the outgoing serial COM port created by Windows
- Python 3.11 or newer when running from source

## Running from source

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src\x1_label.py
```

Select the X1 serial port in the application, enter up to three lines, check
the preview, and choose **Etikett drucken**.

The last text is stored locally in:

```text
%APPDATA%\ORGBRO-X1-Textetiketten\settings.json
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Building the Windows executable

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed --name ORGBRO-X1-Textetiketten src\x1_label.py
```

## Technical background

The printer uses a proprietary packet protocol over Bluetooth Classic SPP. The
interoperability information obtained by observing normal communication with a
lawfully used printer is documented in [docs/protocol.md](docs/protocol.md).

## Deutsch

Dies ist ein inoffizielles, unabhängiges Windows-Programm zum Drucken einfacher
Textetiketten mit dem ORGBRO X1. Es arbeitet vollständig lokal und benötigt
weder Benutzerkonto noch Cloud-Dienst. Nach der Bluetooth-Kopplung wird der von
Windows angelegte serielle COM-Anschluss ausgewählt.

Die Anwendung unterstützt ein bis drei Zeilen, automatische Schriftgröße,
Vorschau, lokale Speicherung des zuletzt verwendeten Textes und einen Knopf zum
Leeren aller Felder.

## License

The original source code in this repository is released under the MIT License.
Third-party packages retain their respective licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
