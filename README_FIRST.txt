MAD VENTURES CLAUDE CODE OPERATING ENVIRONMENT V4.4.1
DELIVERY-CORRECTED RELEASE

READ THIS FILE FIRST.

WHY THIS RELEASE EXISTS
-----------------------
The earlier V4.4 archive contained the environment, but most of the core project
payload was inside project/.claude. macOS Finder hides folders whose names begin
with a period, which can make the package appear empty or incomplete. The earlier
installer also ran the exhaustive release validator before installation and could
look stalled.

V4.4.1 corrects the delivery experience without changing the approved FounderOS
engineering doctrine:

1. A visible inspection copy is included at VISIBLE_PROJECT_TEMPLATE.
2. The canonical install payload remains under project/.claude.
3. INSTALL_MAC.command provides a Finder-friendly guided installation.
4. INSTALL_WINDOWS.ps1 provides a PowerShell entry point.
5. Installers use a fast integrity preflight by default.
6. Full exhaustive validation remains available with --full-validation or
   -FullValidation.
7. PACKAGE_CONTENTS.txt lists every packaged file, including hidden paths.
8. Both ZIP and TAR.GZ distributions are supplied; TAR.GZ is recommended on macOS
   when preserving Unix executable permissions matters.

MACOS — EASIEST INSTALL
-----------------------
1. Extract the TAR.GZ or ZIP.
2. Open the extracted MADVentures-Claude-Code-Environment-v4.4.1 folder.
3. Right-click INSTALL_MAC.command and choose Open.
4. Select the target repository when prompted.
5. The installer opens the installed repository .claude folder when finished.

macOS shortcut to show hidden files in Finder:
  Command + Shift + .

WINDOWS — EASIEST INSTALL
-------------------------
1. Extract the ZIP.
2. Open PowerShell in the extracted folder.
3. Run:

   Set-ExecutionPolicy -Scope Process Bypass
   .\INSTALL_WINDOWS.ps1 -ProjectPath 'C:\path\to\repository'

TERMINAL INSTALL
----------------
macOS/Linux/WSL:

  bash scripts/install.sh /absolute/path/to/repository \
    --profile auto \
    --install-python-control-plane

Windows PowerShell:

  .\scripts\install.ps1 \
    -ProjectPath 'C:\absolute\path\to\repository' \
    -Profile auto \
    -InstallPythonControlPlane

BILLING DEFAULT
---------------
The Python control plane defaults to native `claude -p` using the Claude Code
subscription login already active on the machine. It does not require an
ANTHROPIC_API_KEY and fails closed when an API/provider credential could override
the intended subscription lane.

AUTHORITATIVE FILE
------------------
Use only the V4.4.1 archive and checksum supplied together. Older V4.4 files are
superseded for delivery and installation.
