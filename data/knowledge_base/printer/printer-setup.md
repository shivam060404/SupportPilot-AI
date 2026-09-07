---
title: Printer Setup and Troubleshooting Guide
category: Printer
source: IT Infrastructure Team
last_updated: 2026-08-01
access_level: ALL_EMPLOYEES
---

# Printer Setup and Troubleshooting

## Adding a Network Printer

### Windows
1. Open **Settings → Bluetooth & devices → Printers & scanners**.
2. Click **Add device**. Windows will search for printers on the network.
3. If your printer appears, click it and follow the prompts.
4. If not found: click **Add manually** → **Add a printer using a TCP/IP address or hostname**.
5. Enter the printer's IP address (available on the printer's control panel or from IT).
6. Windows will install the driver automatically from Windows Update.

### macOS
1. Open **System Settings → Printers & Scanners**.
2. Click **+** to add a printer.
3. Select the printer from the list, or enter its IP under the **IP** tab.
4. Choose the correct driver or **AirPrint** for supported printers.

## Common Printer Issues

### Printer Shows as "Offline"
1. Ensure the printer is powered on and has paper.
2. Check that you are connected to the company network (or VPN for remote).
3. On Windows: right-click the printer → **See what's printing** → **Printer menu** → uncheck **Use Printer Offline**.
4. Restart the Print Spooler: press Win+R, type `services.msc`, find **Print Spooler**, right-click → **Restart**.
5. If still offline, remove the printer and re-add it.

### Print Jobs Stuck in Queue
1. Open **Printers & Scanners → your printer → Open print queue**.
2. Cancel all pending jobs (right-click → Cancel for each).
3. If jobs won't cancel: stop the Print Spooler service (see above), then delete files in `C:\Windows\System32\spool\PRINTERS\`, restart the service.

### Poor Print Quality / Missing Ink
1. Run the printer's built-in maintenance page (usually in the printer's control panel menu).
2. For network printers, this is managed by IT — raise a ticket for toner/ink replacement.
3. For personal desk printers: replace cartridge or contact your manager for a replacement.

### Cannot Print from macOS to Network Printer
- Ensure the printer supports IPP or uses a PCL/PostScript driver.
- Try printing a test page from System Settings first.
- Some printers require a Bonjour or vendor-specific driver — contact IT for the installer.

## Supported Printers
Our standard fleet is HP LaserJet and Canon imageRunner. All are network-attached and managed by IT. If you need to add a non-standard printer, raise a ticket.

## Escalation
For printer hardware issues (paper jams, physical damage), or if you need a new printer installed on your floor, raise an IT ticket.
