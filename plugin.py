from __future__ import annotations

from pathlib import Path
from shutil import rmtree
from typing import Any, Dict, TypeAlias, TypedDict
from urllib.request import urlopen
import os
import subprocess
import tarfile
import zipfile

from LSP.plugin import (
    Error,
    LspPlugin,
    LspWindowCommand,
    OnPreStartContext,
    Promise,
    Request,
    notification_handler,
    request_handler,
)
from LSP.protocol import LSPErrorCodes, MessageActionItem, ShowMessageRequestParams
from typing_extensions import Never, override
import sublime

# Pinned Kotlin LSP release. Renovate keeps this in sync with the releases at
# https://github.com/Kotlin/kotlin-lsp (see renovate.json).
VERSION = '263.4702.0'

# Server binary looked up on the PATH (e.g. installed via `brew install JetBrains/utils/kotlin-lsp`).
BINARY_NAME = 'kotlin-lsp'

# JetBrains distributes the standalone server as per-platform archives on their CDN.
DOWNLOAD_URL = 'https://download-cdn.jetbrains.com/language-server/kotlin-server/{version}/{archive}'

# Message request actions that only work in the VS Code extension, e.g. "Configure…" opens VS Code settings.
VSCODE_ONLY_ACTION_TITLES = {'Configure…', 'Configure...'}

CHOOSE_BUILD_TOOL_MESSAGE = 'LSP-kotlin: Run "LSP-kotlin: Choose Build Tool" to start project import.'


class BlockedWorkspaceFolder(TypedDict):
    folderUri: str
    reason: str
    candidates: list[str]
    dismissed: bool


class WorkspaceImportStatus(TypedDict):
    blockedFolders: list[BlockedWorkspaceFolder]


class WorkspaceImportStatusRequest:
    Type = 'intellij/workspaceImportStatus'
    Params: TypeAlias = Dict[str, Never]
    Response: TypeAlias = WorkspaceImportStatus

    @classmethod
    def create(cls) -> Request[Params, Response]:
        return Request(cls.Type, {})


class WorkspaceImportStatusNotification:
    Type = 'intellij/workspaceImportStatus'


class ReloadWorkspaceRequest:
    Type = 'intellij/reloadWorkspace'
    Params: TypeAlias = Dict[str, Any]
    Response: TypeAlias = None

    @classmethod
    def create(cls, params: Params) -> Request[Params, Response]:
        return Request(cls.Type, params)


class Kotlin(LspPlugin):

    _live_import_status_received = False
    _import_prompt_dismissed = False

    @classmethod
    @override
    def on_pre_start_async(cls, context: OnPreStartContext) -> None:
        server_path = context.configuration.root_settings.get('server_path')
        if not server_path or server_path == 'auto':
            cls.install_server()
            server_path = str(cls.managed_binary())
        context.variables.update({'server_path': server_path})
        build_tool = context.configuration.root_settings.get('build_tool')
        if isinstance(build_tool, str):
            build_tools = {folder.uri(): build_tool for folder in context.workspace_folders}
            context.configuration.initialization_options.set('buildTools', build_tools)

    @override
    def on_initialized_async(self) -> None:
        if session := self.weaksession():
            # Seeds the state in case the server published it before our handler could see it.
            session.send_request_task(WorkspaceImportStatusRequest.create()).then(
                lambda status: self._handle_workspace_import_status(status, live=False))

    @request_handler('window/showMessageRequest')
    def on_window_show_message_request(self, params: ShowMessageRequestParams) -> Promise[MessageActionItem | None]:
        if not (session := self.weaksession()) or not (manager := session.manager()):
            return Promise.resolve(None)
        if actions := params.get('actions'):
            params['actions'] = [action for action in actions if action['title'] not in VSCODE_ONLY_ACTION_TITLES]
        return manager.handle_message_request(session.config.name, params)

    @notification_handler(WorkspaceImportStatusNotification.Type)
    def on_workspace_import_status(self, params: WorkspaceImportStatus) -> None:
        self._handle_workspace_import_status(params, live=True)

    def _handle_workspace_import_status(self, status: WorkspaceImportStatus | Error, *, live: bool) -> None:
        if not (session := self.weaksession()) or isinstance(status, Error):
            return
        if live:
            self._live_import_status_received = True
        elif self._live_import_status_received:
            # A live notification is newer than the answer to the initial request.
            return
        conflicts = [f for f in status.get('blockedFolders', []) if f.get('reason') == 'ambiguousBuildSystem']
        session.set_config_status_async('build tool required' if conflicts else '')
        dismissed = any(f.get('dismissed') for f in conflicts)
        newly_dismissed = dismissed and not self._import_prompt_dismissed
        self._import_prompt_dismissed = dismissed
        if newly_dismissed:
            session.window.status_message(CHOOSE_BUILD_TOOL_MESSAGE)

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
        binary = 'intellij-server.exe' if sublime.platform() == 'windows' else 'intellij-server'
        return cls.server_dir() / 'bin' / binary


class LspKotlinReloadWorkspaceCommand(LspWindowCommand):
    """Reload the workspace. When the build tool is ambiguous, the server asks which one to import."""

    def run(self) -> None:
        sublime.set_timeout_async(self._run_async)

    def _run_async(self) -> None:
        if not (session := self.session()):
            return
        params = {'initializationOptions': session.config.initialization_options.get()}
        session.send_request_task(ReloadWorkspaceRequest.create(params)).then(_on_reload_done)


def _on_reload_done(result: None | Error) -> None:
    if not isinstance(result, Error):
        sublime.status_message('LSP-kotlin: workspace reloaded')
    elif result.code not in (LSPErrorCodes.RequestCancelled, LSPErrorCodes.ServerCancelled):
        sublime.error_message(f'LSP-kotlin: failed to reload the workspace: {result}')


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
        # Unlike the other archives it has no top-level kotlin-server-<version>/ folder.
        with zipfile.ZipFile(archive_path) as zip_ref:
            zip_ref.extractall(dst / f'kotlin-server-{version}')
    return dst / f'kotlin-server-{version}'


def plugin_loaded() -> None:
    Kotlin.register()


def plugin_unloaded() -> None:
    Kotlin.unregister()
