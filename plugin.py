from __future__ import annotations

from shutil import rmtree, which
from urllib.request import urlopen
import os
import subprocess
import tarfile
import zipfile

from LSP.plugin import AbstractPlugin, register_plugin, unregister_plugin
import sublime

# Pinned Kotlin LSP release. Renovate keeps this in sync with the releases at
# https://github.com/Kotlin/kotlin-lsp (see renovate.json).
VERSION = '262.9593.0'

SETTINGS_FILENAME = 'LSP-kotlin.sublime-settings'
SESSION_NAME = 'kotlin'

# Server binary looked up on the PATH (e.g. installed via `brew install JetBrains/utils/kotlin-lsp`).
BINARY_NAME = 'kotlin-lsp'

# The default "command" references this variable; additional_variables() resolves it to the
# PATH binary when available, otherwise to our downloaded copy. Keep in sync with the
# LSP-kotlin.sublime-settings "command".
SERVER_PATH_VARIABLE = '${server_path}'

# JetBrains distributes the standalone server as per-platform archives on their CDN.
DOWNLOAD_URL = 'https://download-cdn.jetbrains.com/language-server/kotlin-server/{version}/{archive}'

# Directory (inside the package storage) the downloaded server is normalized into.
SERVER_DIRNAME = 'server'


class Kotlin(AbstractPlugin):
    @classmethod
    def name(cls) -> str:
        return SESSION_NAME

    @classmethod
    def basedir(cls) -> str:
        return os.path.join(cls.storage_path(), str(__package__))

    @classmethod
    def server_dir(cls) -> str:
        return os.path.join(cls.basedir(), SERVER_DIRNAME)

    @classmethod
    def managed_binary(cls) -> str:
        binary = 'intellij-server.bat' if sublime.platform() == 'windows' else 'intellij-server'
        return os.path.join(cls.server_dir(), 'bin', binary)

    @classmethod
    def current_server_version(cls) -> str | None:
        try:
            with open(os.path.join(cls.basedir(), 'VERSION')) as fp:
                return fp.read().strip()
        except OSError:
            return None

    @classmethod
    def additional_variables(cls) -> dict[str, str] | None:
        # Resolve ${server_path}: prefer a kotlin-lsp already on the PATH (e.g. from
        # Homebrew), otherwise fall back to the copy we download and manage ourselves.
        return {'server_path': which(BINARY_NAME) or cls.managed_binary()}

    @classmethod
    def _uses_managed_server(cls) -> bool:
        """Whether the resolved command will launch our own downloaded server.

        True only when the default ``${server_path}`` command is in effect (the user has
        not overridden ``command``) and no ``kotlin-lsp`` is available on the PATH.
        """
        command = sublime.load_settings(SETTINGS_FILENAME).get('command') or []
        if SERVER_PATH_VARIABLE not in command:
            return False
        return which(BINARY_NAME) is None

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        if not cls._uses_managed_server():
            return False
        return not os.path.isfile(cls.managed_binary()) or VERSION != cls.current_server_version()

    @classmethod
    def install_or_update(cls) -> None:
        os.makedirs(cls.basedir(), exist_ok=True)
        archive = _archive_name(VERSION)
        archive_path = os.path.join(cls.basedir(), archive)
        _download(DOWNLOAD_URL.format(version=VERSION, archive=archive), archive_path)
        sublime.status_message('LSP-kotlin: extracting Kotlin LSP server…')
        extracted_root = _extract(archive_path, cls.basedir(), VERSION)
        # Normalize kotlin-server-<version>/ -> server/ so the launch path is stable.
        if os.path.isdir(cls.server_dir()):
            rmtree(cls.server_dir())
        os.rename(extracted_root, cls.server_dir())
        os.remove(archive_path)
        with open(os.path.join(cls.basedir(), 'VERSION'), 'w') as fp:
            fp.write(VERSION)
        sublime.status_message('LSP-kotlin: Kotlin LSP server ready.')


def _archive_name(version: str) -> str:
    suffix = '-aarch64' if sublime.arch() == 'arm64' else ''
    platform = sublime.platform()
    if platform == 'osx':
        extension = '.sit'
    elif platform == 'windows':
        extension = '.win.zip'
    else:
        extension = '.tar.gz'
    return 'kotlin-server-{version}{suffix}{extension}'.format(
        version=version, suffix=suffix, extension=extension
    )


def _download(url: str, dst: str) -> None:
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
                    sublime.status_message(
                        'LSP-kotlin: downloading Kotlin LSP server… {}%'.format(read * 100 // total)
                    )


def _extract(archive_path: str, dst: str, version: str) -> str:
    """Extract the server archive into ``dst`` and return the extracted root directory."""
    if archive_path.endswith('.tar.gz'):
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(dst)
    elif archive_path.endswith('.sit'):
        # The macOS archive is a zip that contains symlinks (the bundled JBR). Python's
        # zipfile turns symlinks into plain files and drops executable bits, which breaks
        # the runtime, so use the system unzip (as Homebrew does) to preserve both.
        subprocess.check_call(['unzip', '-q', '-o', archive_path, '-d', dst])
    else:  # .win.zip - Windows build, no unix symlinks or permission bits to preserve
        with zipfile.ZipFile(archive_path) as zip_ref:
            zip_ref.extractall(dst)
    return os.path.join(dst, 'kotlin-server-{}'.format(version))


def plugin_loaded() -> None:
    register_plugin(Kotlin)


def plugin_unloaded() -> None:
    unregister_plugin(Kotlin)
