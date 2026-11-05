# Windows 11 Declutter

Two registry files that turn off ads, tips, Widgets, Copilot and other extras in Windows 11, and turn them back on again, for anyone who wants a quieter desktop.

## What it does
- Turns off ads and suggestions: Start menu recommendations, lock screen "fun facts", Settings suggestions, "tips and suggestions" pop-ups, File Explorer sync provider ads, and the welcome and "Finish setting up your device" screens after updates.
- Turns off Widgets (news and weather), hides the search box on the taskbar, and removes web (Bing) results from Start menu search.
- Turns off the older Copilot sidebar and asks Windows to remove the Copilot app (on Pro, Enterprise and Education; see Settings and options).
- Stops Windows from installing suggested apps by itself, and turns off the touchscreen swipe-in from the screen edges.
- Turns off the advertising ID and "tailored experiences" (offers based on diagnostic data).
- `windows11_declutter_undo.reg` puts every one of these settings back to normal Windows behavior.

## What you need
- Windows 11. Most settings also work on Windows 10. The Copilot and Widgets lines only matter on Windows 11.
- An administrator account. Some lines change settings for the whole computer, so Windows asks for permission.
- No other programs. Registry Editor is part of Windows.

## Install
1. Download this repository (green **Code** button, then **Download ZIP**) and unzip it.
2. The two files are in the `system` folder: `windows11_declutter.reg` and `windows11_declutter_undo.reg`.

## How to use
1. Optional but wise: create a restore point first. Press the **Windows** key, type `Create a restore point`, open it, and click **Create**.
2. Double-click `windows11_declutter.reg`.
3. Click **Yes** when Windows asks "Do you want to allow this app to make changes to your device?".
4. Click **Yes** when Registry Editor asks if you want to continue.
5. You see "The keys and values contained in ... have been successfully added to the registry". Click **OK**.
6. Sign out and sign back in (or restart) so every change takes effect.

You can open either file in Notepad (right-click, **Open with > Notepad**) to read it first. Each section has a comment that says what it does.

## Settings and options
| Setting in the file | What it changes | Same as this switch in Settings |
|---|---|---|
| `AllowEdgeSwipe` | Touchscreen swipe from the screen edges | (policy only) |
| `DisableSearchBoxSuggestions` | Web results in Start menu search | (policy only) |
| `SearchboxTaskbarMode` = 0 | Hides the taskbar search box | Personalization > Taskbar > Search > **Hide** |
| `AllowNewsAndInterests` | Widgets board and its taskbar button | (policy only) |
| `TurnOffWindowsCopilot` | The older Copilot sidebar | (policy only) |
| `RemoveMicrosoftCopilotApp` | Removes the Copilot app | (policy only) |
| `SilentInstalledAppsEnabled` | Apps installed without asking | (none) |
| `RotatingLockScreenOverlayEnabled`, `SubscribedContent-338387Enabled` | Lock screen fun facts and tips | Personalization > Lock screen |
| `SubscribedContent-338389Enabled`, `SoftLandingEnabled` | "Tips and suggestions" notifications | System > Notifications > Additional settings |
| `SubscribedContent-338393Enabled`, `-353694Enabled`, `-353696Enabled` | Suggested content in the Settings app | Privacy & security > General |
| `SubscribedContent-310093Enabled` | Welcome experience after updates | System > Notifications > Additional settings |
| `ScoobeSystemSettingEnabled` | "Finish setting up your device" screen | System > Notifications > Additional settings |
| `Start_IrisRecommendations` | Start menu recommendations for tips, shortcuts and new apps | Personalization > Start |
| `Start_AccountNotifications` | Account notifications in the Start menu | Personalization > Start |
| `ShowSyncProviderNotifications` | OneDrive and other ads in File Explorer | File Explorer > Options > View |
| `AdvertisingInfo` `Enabled` | Advertising ID | Privacy & security > General |
| `TailoredExperiencesWithDiagnosticDataEnabled` | Tailored experiences | Privacy & security > Diagnostics & feedback |

To skip a setting, open the `.reg` file in Notepad and delete its line (or put `;` at the start of the line), then save.

**About the Copilot app.** Microsoft added the "Remove Microsoft Copilot app" policy in 2026. It works on Windows 11 Pro, Enterprise and Education, not Home. Windows only removes the app if it came with Windows (you did not install it yourself) and has not been opened for a while. If those rules are not met, nothing happens and you can uninstall Copilot from **Settings > Apps > Installed apps**.

## Safety notes
- These files change the Windows registry. Only the settings listed above are changed. Nothing is deleted from your files, and nothing is sent anywhere.
- Lines under `HKEY_LOCAL_MACHINE` and `...\Policies\...` act like company policies. Some Settings switches may show "Some of these settings are managed by your organization" or be grayed out. That is normal and goes away after the undo file.
- **To undo:** double-click `windows11_declutter_undo.reg`, answer **Yes** twice, then sign out and back in. The undo file turns the tips and ads switches back **on**, which is how Windows normally has them. If you had turned some of them off yourself before, turn those off again in Settings.
- The undo file does not reinstall the Copilot app. Get it again from the Microsoft Store if you want it.
- A restore point (step 1 of How to use) lets you go back to the exact state from before.

## Troubleshooting
- **"Cannot import ... Not all data was successfully written to the registry"**: Windows protects a few settings and refuses changes to them. All other lines were still applied. You can change the refused setting by hand in the Settings app.
- **Nothing seems to change**: sign out and back in, or restart. Some changes only load at sign-in.
- **The Copilot app is still there**: see "About the Copilot app" above. On Windows 11 Home, uninstall it in **Settings > Apps > Installed apps**.
- **A setting is grayed out in Settings**: a policy line from this file controls it. Run the undo file to give control back to Settings.

## How it works
A `.reg` file is a plain text list of registry keys and values that Registry Editor (`regedit.exe`) imports when you double-click it. `dword:00000000` sets a value to 0 (off) and `dword:00000001` to 1 (on), and `"Name"=-` removes a value so Windows goes back to its default. The values under `SOFTWARE\Policies` are the same ones that Group Policy writes. The values under `CurrentVersion\ContentDeliveryManager`, `Explorer\Advanced`, `AdvertisingInfo` and `Privacy` are the same ones the Settings app changes when you flip its switches.
