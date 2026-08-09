VISIBLE PROJECT TEMPLATE — INSPECTION COPY

The actual installer source is project/.claude, which macOS Finder hides because its name begins with a period.
This directory is a generated, visible mirror so every agent, skill, workflow, hook, rule, and setting can be inspected normally.

Mapping during installation:
  VISIBLE_PROJECT_TEMPLATE/CLAUDE_FOLDER_CONTENTS  ->  <repository>/.claude
  REPOSITORY_ROOT_FILES/mcp.example.json          ->  <repository>/.mcp.example.json
  REPOSITORY_ROOT_FILES/gitignore.fragment.txt    ->  appended to <repository>/.gitignore

Do not manually install from this mirror. Use INSTALL_MAC.command, INSTALL_WINDOWS.ps1, or scripts/install.*.
The release validator verifies this mirror against the canonical hidden source before packaging.
