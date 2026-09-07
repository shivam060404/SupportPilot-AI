---
title: Email Setup and Outlook Troubleshooting Guide
category: Email
source: Collaboration Team
last_updated: 2026-08-15
access_level: ALL_EMPLOYEES
---

# Email Setup and Outlook Troubleshooting

## Initial Email Setup

### Outlook Desktop (Windows)
1. Open Outlook. If no account is configured, the setup wizard will launch automatically.
2. Enter your company email address (`firstname.lastname@company.com`) and click **Connect**.
3. When prompted, enter your company password and approve the MFA request on your phone.
4. Outlook will configure itself using Autodiscover. This may take 2–5 minutes.
5. Once configured, your inbox should sync within 10 minutes.

### Outlook Desktop (macOS)
1. Open Outlook and select **Add Account** from the top menu.
2. Enter your company email and click **Continue**.
3. Select **Microsoft 365** as the account type.
4. Complete MFA authentication in the browser window that opens.

### Outlook Mobile (iOS/Android)
1. Download "Microsoft Outlook" from the App Store or Google Play.
2. Open the app and tap **Add Account**.
3. Enter your company email address and follow the prompts.
4. Approve the MFA notification.

## Common Outlook Issues

### Outlook Not Syncing / Stuck on "Updating"
1. Check your internet connection.
2. Click **Send/Receive All Folders** (F9 on Windows).
3. Close and reopen Outlook.
4. If still stuck: go to **File → Account Settings → Account Settings**, select your account, click **Repair**.
5. If repair fails: remove the account and re-add it following the setup steps above.

### Cannot Send Emails ("Mailbox Full")
- Your mailbox has a 50 GB quota. Check usage at **File → Info → Mailbox Settings**.
- Archive old emails to a local .pst file or OneDrive Archive.
- Contact IT to request a temporary quota increase (approved for legitimate business use).

### Outlook Opens in Safe Mode or Crashes
1. Close Outlook fully.
2. Hold **Ctrl** while opening Outlook to launch in Safe Mode. If it works, an add-in is the cause.
3. Disable add-ins: **File → Options → Add-ins → Manage COM Add-ins → Go**.
4. Uncheck all add-ins, click OK, restart Outlook, then re-enable them one by one.

### Outlook Password Prompt Keeps Appearing
- Your password may have expired. Reset at `https://password.company.com`.
- In Windows Credential Manager: search "Credential Manager" → Windows Credentials → find Microsoft Office entries → remove them, then re-enter credentials.

### Calendar Not Showing Colleagues' Availability
- Ensure you are connected to the company network (VPN if remote).
- Go to **File → Open & Export → Other User's Folder** and verify permissions.
- Contact IT if free/busy information is missing for your team.

## Escalation
If these steps don't resolve the issue, raise an IT ticket with:
- Your email address
- Outlook version (File → Office Account → About Outlook)
- Operating system version
- Screenshot of any error messages
