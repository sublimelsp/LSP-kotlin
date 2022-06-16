import sublime

from LSP.plugin import AbstractPlugin, register_plugin, unregister_plugin
from LSP.plugin.core.typing import Any, Optional, Tuple, Union

from shutil import which, copyfileobj
from urllib.request import urlopen
from urllib.error import URLError
import os
import stat
import re
import zipfile

TAG = '1.3.0'

LSP_KOTLIN_BASE_URL = 'https://github.com/fwcd/kotlin-language-server/releases/download/{tag}/server.zip'
SETTINGS_FILENAME = 'LSP-kotlin.sublime-settings'

LIBRAR_DIR = 'lib'
DATA_DIR = 'data'
SESSION_NAME = 'kotlin'


RE_VER = re.compile(r'Version\s+((?:\d+\.){2}\d+)')


class Kotlin(AbstractPlugin):
    @classmethod
    def name(cls):
        return SESSION_NAME

    @classmethod
    def basedir(cls) -> str:
        return os.path.join(cls.storage_path(), __package__)

    @classmethod
    def server_version(cls) -> str:
        return TAG

    @classmethod
    def current_server_version(cls) -> Optional[str]:
        try:
            with open(os.path.join(cls.basedir(), 'VERSION'), 'r') as fp:
                return fp.read()
        except:
            return None

    @classmethod
    def get_kotlin_language_server_binary(cls) -> str:
        binary = 'kotlin-language-server.bat' if sublime.platform() == 'windows' else 'kotlin-language-server'
        command = get_setting(
            'command', [os.path.join(cls.basedir(), 'bin', binary)]
        )
        kotlin_binary = command[0].replace('${storage_path}', cls.storage_path())
        if sublime.platform() == 'windows' and not kotlin_binary.endswith('.bat'):
            kotlin_binary = kotlin_binary + '.bat'
        return kotlin_binary

    @classmethod
    def _is_kotlin_language_server_installed(cls) -> bool:
        return _is_binary_available(cls.get_kotlin_language_server_binary())

    @classmethod
    def _is_java_installed(cls) -> bool:
        return _is_binary_available('java')

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        return not cls._is_kotlin_language_server_installed() or (
            cls.server_version() != cls.current_server_version()
        )

    @classmethod
    def install_or_update(cls) -> None:
        os.makedirs(cls.basedir(), exist_ok=True)
        download_kotlin_language_server(tag=cls.server_version(), dst=cls.basedir())
        with open(os.path.join(cls.basedir(), 'VERSION'), 'w') as fp:
            fp.write(cls.server_version())

        _make_executable(binary=cls.get_kotlin_language_server_binary())


def download_kotlin_language_server(tag: Union[str, None], dst: str) -> None:
    if tag is None:
        return

    download_uri = LSP_KOTLIN_BASE_URL.format(tag=tag)
    try:
        with urlopen(download_uri) as response, open(os.path.join(dst, 'server.zip'), 'wb') as out_file:
            copyfileobj(response, out_file)
            
        _extract_zip(src=os.path.join(dst, 'server.zip'), dst=dst)
    except URLError as ex:
        raise ex
    except Exception as ex:
        raise ex
        

def _make_executable(binary: str) -> None:
    st = os.stat(binary)
    os.chmod(binary, st.st_mode | stat.S_IEXEC)


def _extract_zip(src: str, dst: str) -> None:
    with zipfile.ZipFile(src, 'r') as zip_ref:
        zip_ref.extractall(dst)


def _is_binary_available(path) -> bool:
    return bool(which(path))


def to_int(value: Optional[str]) -> int:
    if value is None:
        return 0
    return int(value)


def get_setting(key: str, default=None) -> Any:
    settings = sublime.load_settings('LSP-kotlin.sublime-settings')
    return settings.get(key, default)


def plugin_loaded():
    register_plugin(Kotlin)


def plugin_unloaded():
    unregister_plugin(Kotlin)