from shutil import rmtree, copytree
from pathlib import Path
from subprocess import run, PIPE, STDOUT, CalledProcessError

from yaml import dump

from foliant.utils import spinner
from foliant.backends.base import BaseBackend


class Backend(BaseBackend):
    targets = ('site', 'mkdocs')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._mkdocs_config = self.config.get('backend_config', {}).get('mkdocs', {})
        self._mkdocs_site_dir_name = f'{self.get_slug()}.mkdocs'
        self._mkdocs_project_dir_name = f'{self._mkdocs_site_dir_name}.src'

        self.required_preprocessors_after = {
            'mkdocs': {
                'mkdocs_project_dir_name': self._mkdocs_project_dir_name
            }
        },

    def _get_command(self, mkdocs_site_path: Path) -> str:
        '''Generate ``mkdocs build`` command to build the site.

        :param mkdocs_site_path: Path to the output directory for the site
        '''

        components = [self._mkdocs_config.get('binary_path', 'mkdocs')]
        components.append('build')
        components.append(f'-d {mkdocs_site_path}')

        return ' '.join(components)

    def make(self, target: str) -> str:
        with spinner(f'Making {target} with MkDocs', self.quiet):
            try:
                mkdocs_project_path = self.working_dir / self._mkdocs_project_dir_name

                config = self._mkdocs_config.get('mkdocs.yml', {})

                if 'site_name' not in config and self._mkdocs_config.get('use_title', True):
                    config['site_name'] = self.config['title']

                if 'pages' not in config and self._mkdocs_config.get('use_chapters', True):
                    config['pages'] = self.config['chapters']

                with open(mkdocs_project_path/'mkdocs.yml', 'w', encoding='utf8') as mkdocs_config:
                    dump(
                        config,
                        mkdocs_config,
                        default_flow_style=False
                    )

                if target == 'mkdocs':
                    rmtree(self._mkdocs_project_dir_name, ignore_errors=True)
                    copytree(mkdocs_project_path, self._mkdocs_project_dir_name)

                    return self._mkdocs_project_dir_name

                elif target == 'site':
                    try:
                        mkdocs_site_path = Path(self._mkdocs_site_dir_name).absolute()
                        run(
                            self._get_command(mkdocs_site_path),
                            shell=True,
                            check=True,
                            stdout=PIPE,
                            stderr=STDOUT,
                            cwd=mkdocs_project_path
                        )

                        return self._mkdocs_site_dir_name

                    except CalledProcessError as exception:
                        raise RuntimeError(f'Build failed: {exception.output.decode()}')

                else:
                    raise ValueError(f'MkDocs cannot make {target}')

            except Exception as exception:
                raise type(exception)(f'Build failed: {exception}')
