---
title: Microsoft 365 / Office Application Troubleshooting
category: Application
source: Collaboration Team
last_updated: 2026-08-10
access_level: ALL_EMPLOYEES
---

# Microsoft 365 Troubleshooting Guide

## Activation Issues

### "Product Deactivated" or License Error
1. Open any Office application (Word, Excel, Outlook).
2. Go to **File → Account**.
3. Click **Sign In** and use your company email (`firstname.lastname@company.com`).
4. If already signed in: click **Sign Out**, then sign back in.
5. If the error persists, click **Fix my Account** (shown when a license issue is detected).
6. Restart the application after licensing updates.

### Office Asks for Activation After Windows Update
- Windows updates occasionally reset license caches.
- Run the Office Activation Troubleshooter: **Settings → Update & Security → Troubleshoot → Additional troubleshooters → Office**.

## OneDrive Issues

### Files Not Syncing
1. Check the OneDrive icon in the system tray. Click it for status.
2. If it shows a red X or pause icon: click the icon → **Help & Settings → Resume syncing**.
3. Check available disk space — OneDrive requires at least 500 MB free.
4. Files with names containing special characters (`< > : " / \ | ? *`) cannot sync. Rename them.
5. Restart OneDrive: click the icon → **Help & Settings → Quit OneDrive**, then reopen from Start menu.

### "Files On-Demand" — Cannot Open Files Offline
- Right-click the file/folder → **Always keep on this device** to download a local copy.
- For offline work, download required files before disconnecting.

## Microsoft Teams Issues

### Cannot Join Meetings / Audio Not Working
1. Test audio/video: in Teams, click your profile picture → **Settings → Devices**.
2. Ensure the correct microphone and speakers are selected.
3. If using a headset, check that it's set as the default device in **Windows Sound Settings**.
4. For in-meeting issues: click the three-dot menu → **Device settings** to switch mid-call.

### Teams is Slow or Crashes
1. Clear Teams cache: close Teams fully. Open File Explorer → `%appdata%\Microsoft\Teams`. Delete the contents of the `Cache`, `blob_storage`, `databases`, `GPUCache`, `IndexedDB`, `Local Storage`, and `tmp` folders. Restart Teams.
2. Try the Teams Web version (`https://teams.microsoft.com`) to check if it's an app-specific issue.
3. Ensure your Windows/macOS is up to date.

### Cannot Access a SharePoint Site
- Your manager must grant you access. Contact them first.
- After access is granted, wait up to 1 hour for propagation.
- Clear your browser cache and cookies for `*.sharepoint.com`.

## Excel / Word Crashes or Hangs
1. Open the application in Safe Mode: hold **Ctrl** while opening the app.
2. If it works in Safe Mode, an add-in is the culprit. Disable add-ins: **File → Options → Add-ins**.
3. Repair Office: **Settings → Apps → Microsoft 365 → Modify → Quick Repair**.
4. If repair doesn't help, run **Online Repair** (requires internet, takes 15–20 minutes).

## Escalation
For licensing issues affecting your entire team, or if Quick/Online Repair fails, raise an IT ticket including:
- Your Office version (File → Account → About)
- The exact error message or screenshot
- Steps you have already tried
