from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from urllib.request import urlopen
import os
import subprocess
import tarfile
import zipfile

from LSP.plugin import LspPlugin, OnPreStartContext
from typing_extensions import override
import sublime

# Pinned Kotlin LSP release. Renovate keeps this in sync with the releases at
# https://github.com/Kotlin/kotlin-lsp (see renovate.json).
VERSION = '262.9593.0'

# Server binary looked up on the PATH (e.g. installed via `brew install JetBrains/utils/kotlin-lsp`).
BINARY_NAME = 'kotlin-lsp'

# JetBrains distributes the standalone server as per-platform archives on their CDN.
DOWNLOAD_URL = 'https://download-cdn.jetbrains.com/language-server/kotlin-server/{version}/{archive}'


class Kotlin(LspPlugin):

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        server_path = context.configuration.root_settings.get('server_path')
        if not server_path or server_path == 'auto':
            cls.install_server()
            server_path = str(cls.managed_binary())
        context.variables.update({'server_path': server_path})

    @classmethod
    def install_server(cls) -> None:
        version_file_path = cls.plugin_storage_path / "VERSION"
        if version_file_path.is_file() and version_file_path.read_text(encoding="utf-8") == VERSION:
            return
        try:
            if cls.plugin_storage_path.is_dir():
                rmtree(cls.plugin_storage_path)
            cls.plugin_storage_path.mkdir(exist_ok=True, parents=True)
            archive = _archive_name(VERSION)
            archive_path = cls.plugin_storage_path / archive
            _download(DOWNLOAD_URL.format(version=VERSION, archive=archive), archive_path)
            sublime.status_message('LSP-kotlin: extracting Kotlin LSP server…')
            extracted_root = _extract(archive_path, cls.plugin_storage_path, VERSION)
            # Normalize kotlin-server-<version>/ -> server/ so the launch path is stable.
            if cls.server_dir().is_dir():
                rmtree(cls.server_dir())
            os.rename(extracted_root, cls.server_dir())
            os.remove(archive_path)
            version_file_path.write_text(VERSION, encoding='utf-8')
            sublime.status_message('LSP-kotlin: Kotlin LSP server ready.')
        except BaseException:
            rmtree(cls.plugin_storage_path, ignore_errors=True)
            raise

    @classmethod
    def server_dir(cls) -> Path:
        return cls.plugin_storage_path / 'server'

    @classmethod
    def managed_binary(cls) -> Path:
        binary = 'intellij-server.bat' if sublime.platform() == 'windows' else 'intellij-server'
        return cls.server_dir() / 'bin' / binary


def _archive_name(version: str) -> str:
    suffix = '-aarch64' if sublime.arch() == 'arm64' else ''
    platform = sublime.platform()
    if platform == 'osx':
        extension = '.sit'
    elif platform == 'windows':
        extension = '.win.zip'
    else:
        extension = '.tar.gz'
    return f'kotlin-server-{version}{suffix}{extension}'


def _download(url: str, dst: Path) -> None:
    with urlopen(url) as response:  # noqa: S310 - trusted JetBrains CDN over https
        total = int(response.headers.get('Content-Length') or 0)
        read = 0
        with open(dst, 'wb') as out_file:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out_file.write(chunk)
                read += len(chunk)
                if total:
                    sublime.status_message(f'LSP-kotlin: downloading Kotlin LSP server… {read * 100 // total}%')


def _extract(archive_path: Path, dst: Path, version: str) -> Path:
    """Extract the server archive into ``dst`` and return the extracted root directory."""
    if str(archive_path).endswith('.tar.gz'):
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(dst)
    elif str(archive_path).endswith('.sit'):
        # The macOS archive is a zip that contains symlinks (the bundled JBR). Python's
        # zipfile turns symlinks into plain files and drops executable bits, which breaks
        # the runtime, so use the system unzip (as Homebrew does) to preserve both.
        subprocess.check_call(['unzip', '-q', '-o', archive_path, '-d', dst])
    else:  # .win.zip - Windows build, no unix symlinks or permission bits to preserve
        with zipfile.ZipFile(archive_path) as zip_ref:
            zip_ref.extractall(dst)
    return dst / f'kotlin-server-{version}'


def plugin_loaded() -> None:
    Kotlin.register()


def plugin_unloaded() -> None:
    Kotlin.unregister()
