# ORGBRO X1 SPP protocol notes

These notes document only the information needed for interoperability with an
independently created text-label application. Command meanings that have not
been confirmed are deliberately left unnamed.

## Transport

- Bluetooth Classic Serial Port Profile (SPP)
- Windows exposes the paired printer as a COM port
- 9600 baud is used when opening the virtual serial port

## Packet format

```text
64 CMD SEQ LEN_LO LEN_HI PAYLOAD... 00 00 00 00 9B
```

- `CMD`: one-byte command
- `SEQ`: one-byte sequence number
- `LEN_LO LEN_HI`: payload length in little-endian order
- the packet ends with four zero bytes followed by `9B`

## Session prefix

```text
CMD 12, sequence 01, no payload
CMD 11, sequence 02, no payload
CMD 72, sequence 03, payload 01
```

The printer returns status data between these stages. A short delay is required
before beginning the print job.

## Print job observed for a 12 x 40 mm label

```text
CMD 0A, payload 19
CMD 09, payload 09
CMD 03, payload 02 20 03
CMD 02, payload 09 00
CMD 00, raster data in blocks of at most 288 bytes
CMD 03, payload 01 20 03
```

Sequence numbers increase across all packets.

The two-byte payload of `CMD 02` acts as a little-endian print-head position
value. The observed default was `09 00`. A calibration adjustment produced
`0B 00`. Reversing the default to `00 09` changes the numeric value from 9
to 2304 and causes roughly 288 mm of unwanted feed.

## Raster

- 96 dots across the print head
- 280 rows along the label
- 1 bit per pixel
- most-significant bit first within each byte
- set bits produce black pixels
- 12 bytes per row
- 3360 raster bytes in total

The logical 280 x 96 label image is rotated 90 degrees before transmission.

## Transfer pacing

Observed RFCOMM writes used chunks up to 255 bytes. A practical replay uses a
short pause and status read after each chunk to avoid overrunning the printer's
small receive buffer.

## Scope

No vendor application code, artwork, accounts, cloud services, device
addresses, serial numbers, or diagnostic archives are included in this
repository.
