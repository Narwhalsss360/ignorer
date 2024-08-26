from sys import argv
from os import getcwd
from typing import Callable, Optional, Self
from dataclasses import dataclass, field
from pathlib import Path
from json import loads
from datetime import datetime
from requests import get, RequestException, Response
from npycli import Command


TRUTHY: tuple[str] = tuple(s.casefold() for s in ('y', 'yes', 'true', '1'))
FALSY: tuple[str] = tuple(s.casefold() for s in ('n', 'no', 'false', '0'))


def bool_parser(text: str) -> bool:
    prepped: str = text.strip().casefold()
    if prepped in TRUTHY:
        return True
    elif prepped in FALSY:
        return False
    raise ValueError(f'{prepped} is neither truthy nor falsy.')


@dataclass
class Config:
    CONFIG_PATH: Path = Path.home() / ".config" / "ignorer.cfg.json"
    CURRENT: Optional[Self] = None
    local_paths: list[str] = field(default_factory=list)

    def current() -> Self:
        if Config.CURRENT is not None:
            return Config.CURRENT

        if Config.CONFIG_PATH.exists():
            with open(Config.CONFIG_PATH, 'r', encoding='utf-8') as cfg_file:
                Config.CURRENT = Config(**loads(cfg_file.read()))
                return Config.current()

        Config.CURRENT = Config()
        return Config.current()

    @staticmethod
    def load_from(path: str) -> Self:
        with open(path, 'r', encoding='utf-8') as cfg_file:
            Config.CURRENT = Config(**loads(cfg_file.read()))
            return Config.CURRENT

    @property
    def paths_with_cwd(self) -> list[str]:
        return [getcwd()] + self.local_paths


def fetch_local(name: str) -> Optional[str | Exception]:
    match: Callable[[Path], bool] = lambda path: path.suffix.casefold() == '.gitignore'.casefold() and path.stem == name
    matched_path: Optional[Path] = None
    for str_path in Config.current().paths_with_cwd:
        path: Path = Path(str_path)

        if path.is_dir():
            for file_path in path.glob('*'):
                if match(file_path):
                    matched_path = file_path
                    break
        elif path.is_file():
            if match(path):
                matched_path = path
                break

    if matched_path is None:
        return None
    with open(matched_path, 'r', encoding='utf-8') as source:
        return source.read()


def fetch_github(name: str) -> Optional[str | Exception]:
    if not name.endswith('.gitignore'):
        name = f'{name}.gitignore'
    try:
        response: Response = get(f'https://raw.githubusercontent.com/github/gitignore/main/{name}')
    except RequestException as req_exc:
        return req_exc

    if not response.ok:
        return None
    return response.text


OFFLINE_RESOLUTION_ORDER: list[Callable[[str], Optional[str | Exception]]] = [
    fetch_local,
]

ONLINE_RESOLUTION_ORDER: list[Callable[[str], Optional[str | Exception]]] = [
    fetch_github,
]

DEFAULT_OUT: str = '.gitignore'
SOURCE_FILE_PREFIX = f'# ignorer {datetime.now().isoformat()} === Generated source ignore file. ===\n\n'
SOURCE_FILE_SUFFIX = f'# ignorer {datetime.now().isoformat()} === Generated source ignore file. ===\n'


def ignore(*templates: str, out: Optional[str] = None, offline: bool = False, append: bool = False,
           cfg_path: Optional[str] = None) -> None:
    if cfg_path is not None:
        Config.load_from(cfg_path)

    if offline:
        resolution_order: list[Callable[[str], Optional[str | Exception]]] = OFFLINE_RESOLUTION_ORDER
        print('Offline mode.')
    else:
        resolution_order: list[Callable[[str], Optional[str | Exception]]
                               ] = OFFLINE_RESOLUTION_ORDER + ONLINE_RESOLUTION_ORDER

    def resolve(name: str) -> Optional[str | Exception]:
        for fetcher in resolution_order:
            result: Optional[str | Exception] = fetcher(name)
            if isinstance(result, str):
                return result
        return None

    if out is None:
        out = DEFAULT_OUT

    if Path(out).exists():
        if Path(out).is_dir():
            print(f'Error: {out} is an existing directory.')
            return
        if not append:
            print(f'Error: {out} already exists. use append=true to append to this file.')
            return

    source: str = SOURCE_FILE_PREFIX
    for template in templates:
        if template.endswith('.gitignore'):
            template = template[:-1 * len('.gitignore')]
        result: Optional[str | Exception] = resolve(template)
        if result is None or isinstance(result, Exception):
            msg: str = f'Template {template} not found.'
            if result is not None:
                msg += f' {result}'
            msg += ' Continue (or quit)?'

            if not bool_parser(input(msg)):
                return

        print(f'Using {template}.')
        source += f'# ignorer === TEMPLATE {template} START ===\n'
        source += f'{result}{"" if result.endswith('\n') else "\n"}'
        source += f'# ignorer === TEMPLATE {template} END ===\n\n'
    source += SOURCE_FILE_SUFFIX

    with open(out, 'a' if append else 'w', encoding='utf-8') as source_file:
        source_file.write(source)
    print(out)


def main() -> None:
    cmd: Command = Command.create(ignore, 'ignorer', None, help='Create ignore source')
    if len(argv) == 1:
        print(cmd.details)
    else:
        cmd(argv[1:], {bool: bool_parser})


if __name__ == '__main__':
    main()
