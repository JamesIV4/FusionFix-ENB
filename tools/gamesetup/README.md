# Stock CE ENB setup

Use [the stock-only setup](../../docs/ENBCompatibility.md).
`Invoke-StockENBTest.ps1` installs or restores the exact stock shader cache,
stock-targeted aliases and ASI while preserving non-shader settings/content.
It also removes known retired modern aliases and bridge assets with backups.

`Test-StockENBSetup.ps1` exercises the migration and exact restoration inside a
new synthetic build directory. It never runs the game.

The old modern-material, postfx-bridge, extended-tree and mixed-package helpers
have been removed. Historical research commands are not current instructions.
