# LSP-kotlin

Kotlin support for Sublime's LSP plugin.

Uses [Kotlin Language Server][kotlin-language-server-repo] to provide validation, formatting and other features for Kotlin files. See linked repository for more information.

### Prerequisites

*   Java must be installed and configured in your `PATH`

### Installation

*   Install [LSP][lsp-repo], [LSP-kotlin][lsp-kotlin] and [Kotlin][kotlin-syntax] from Package Control.
*   Restart Sublime.

### Configuration

Open configuration file using command palette with `Preferences: LSP-kotlin Settings` command or opening it from the Sublime menu (`Preferences > Package Settings > LSP > Servers > LSP-kotlin`).

## Settings

Configure the default Kotlin language server ('kotlin-language-server'). The language server doesn't contain customizable settings at the moment.

[lsp-repo]: https://packagecontrol.io/packages/LSP

[lsp-kotlin]: https://packagecontrol.io/packages/LSP-kotlin

[packagedev-repo]: https://packagecontrol.io/packages/PackageDev

[kotlin-language-server-repo]: https://github.com/fwcd/kotlin-language-server

[kotlin-syntax]: https://github.com/vkostyukov/kotlin-sublime-package
