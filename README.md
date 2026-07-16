# LSP-kotlin

Kotlin support for Sublime's LSP plugin.

Uses the official [Kotlin LSP][kotlin-lsp-repo] from JetBrains to provide completion,
diagnostics, formatting and other features for Kotlin files. See the linked repository for
more information. Note that the server is currently in **alpha**.

### Prerequisites

None — the server is downloaded and managed automatically (it bundles its own Java runtime,
so a separate JDK is **not** required).

> [!NOTE]
> The server is a large download: roughly **390 MB**, expanding to about **1.2 GB** on disk.
> It is fetched once, on first use, and reused afterwards.

If you would rather manage the server yourself (or share one copy across editors), install the
`kotlin-lsp` CLI so it is available on your `PATH` and LSP-kotlin will use it instead of
downloading its own copy:

- **Homebrew:** `brew install JetBrains/utils/kotlin-lsp`
- **Manual:** download the standalone zip from the [releases page][kotlin-lsp-releases],
  unpack it, `chmod +x kotlin-lsp.sh`, and symlink it onto your `PATH` as `kotlin-lsp`
  (e.g. `ln -s $KOTLIN_LSP_DIR/kotlin-lsp.sh $HOME/.local/bin/kotlin-lsp`).

### Installation

- Install [LSP][lsp-repo] and [LSP-kotlin][lsp-kotlin] from Package Control.
- Install a Kotlin syntax so `.kt`/`.kts` files get the `source.kotlin` scope that this
  package attaches to — Sublime Text has none built in. Install [Kotlin][kotlin-syntax] from
  Package Control; despite the shared name, it is the maintained `guille/sublime-kotlin`
  package, **not** the abandoned `vkostyukov/kotlin-sublime-package`.
- Restart Sublime and open a Kotlin file — the server downloads on first use.

### Configuration

Open the configuration file using the command palette with the `Preferences: LSP-kotlin Settings`
command or from the Sublime menu (`Preferences > Package Settings > LSP > Servers > LSP-kotlin`).

The default `command` is `["${server_path}", "--stdio"]`, where `${server_path}` resolves to a
`kotlin-lsp` binary on your `PATH` if one is found (e.g. from Homebrew), and otherwise to the
managed copy that is downloaded into the package's storage directory. To force a specific
server, replace `${server_path}` with an absolute path:

```json
{
	"command": ["/opt/homebrew/bin/kotlin-lsp", "--stdio"]
}
```

## Settings

The language server doesn't expose customizable settings at the moment.

[lsp-repo]: https://packagecontrol.io/packages/LSP
[lsp-kotlin]: https://packagecontrol.io/packages/LSP-kotlin
[kotlin-lsp-repo]: https://github.com/Kotlin/kotlin-lsp
[kotlin-lsp-releases]: https://github.com/Kotlin/kotlin-lsp/releases
[kotlin-syntax]: https://github.com/guille/sublime-kotlin
