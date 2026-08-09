# Open Me First — V4.4.1 Delivery-Corrected Release

The environment is present. The earlier delivery was misleading on macOS because the core Claude Code template is stored in `project/.claude`, and Finder hides dot-prefixed folders.

## What changed in V4.4.1

- Added `VISIBLE_PROJECT_TEMPLATE/`, a generated inspection mirror of the hidden canonical template.
- Added `INSTALL_MAC.command` and `INSTALL_WINDOWS.ps1` as obvious top-level launchers.
- Added `VERIFY_PACKAGE.command` and a fast cryptographic install-time validator.
- Added `PACKAGE_CONTENTS.txt`, which lists hidden and visible package members.
- Changed installers to run a fast integrity preflight by default; exhaustive release validation remains opt-in.
- Added a macOS-friendly `tar.gz` distribution alongside the universal ZIP.

No FounderOS role, governance, model-routing, agent, skill, workflow, hook, or Python control-plane policy was removed in this delivery correction.

## macOS

Right-click **`INSTALL_MAC.command`** and choose **Open**. Select the repository to receive the environment. The installer opens the resulting `.claude` folder when complete.

To reveal dotfolders manually in Finder, press **Command + Shift + .**

## Windows

Open PowerShell in the extracted folder and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\INSTALL_WINDOWS.ps1 -ProjectPath 'C:\path\to\repository'
```

## Verify without installing

macOS/Linux/WSL:

```bash
python3 scripts/quick-validate.py
```

Windows:

```powershell
python .\scripts\quick-validate.py
```

For the exhaustive release suite:

```bash
python3 scripts/validate-config.py
```
