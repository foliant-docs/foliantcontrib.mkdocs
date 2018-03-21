import re

from shutil import rmtree, copytree
from pathlib import Path
from typing import Dict
from subprocess import run, PIPE, STDOUT, CalledProcessError

from yaml import dump

from foliant.utils import spinner
from foliant.backends.base import BaseBackend


class Backend(BaseBackend):
    targets = ('site', 'mkdocs', 'ghp')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._mkdocs_config = self.config.get('backend_config', {}).get('mkdocs', {})

        overridden_slug = self._mkdocs_config.get('slug', None)

        if overridden_slug:
            self._mkdocs_site_dir_name = f'{overridden_slug}.mkdocs'

        else:
            self._mkdocs_site_dir_name = f'{self.get_slug()}.mkdocs'

        self._mkdocs_project_dir_name = f'{self._mkdocs_site_dir_name}.src'

        self.required_preprocessors_after = {
            'mkdocs': {
                'mkdocs_project_dir_name': self._mkdocs_project_dir_name
            }
        },

    def _get_build_command(self, mkdocs_site_path: Path) -> str:
        '''Generate ``mkdocs build`` command to build the site.

        :param mkdocs_site_path: Path to the output directory for the site
        '''

        components = [self._mkdocs_config.get('mkdocs_path', 'mkdocs')]
        components.append('build')
        components.append(f'-d {mkdocs_site_path}')

        return ' '.join(components)

    def _get_ghp_command(self) -> str:
        '''Generate ``mkdocs gh-deploy`` command to deploy the site to GitHub Pages.'''

        components = [self._mkdocs_config.get('mkdocs_path', 'mkdocs')]
        components.append('gh-deploy')

        return ' '.join(components)

    def _get_page_with_optional_heading(self, page_file_path: str) -> str or Dict:
        is_path_to_markdown_file = re.match("^\S+\.md$", page_file_path)

        if is_path_to_markdown_file:
            page_file_full_path = self.project_path / self.config['src_dir'] / page_file_path

            with open(page_file_full_path, encoding='utf8') as page_file:
                content = page_file.read()
                headings_found = re.search("^#+\s+(.+)$", content, flags=re.MULTILINE)

                if headings_found:
                    first_heading = headings_found.group(1)
                    return {first_heading: page_file_path}

        return page_file_path

    def _get_pages_with_headings(self, pages: Dict) -> Dict:

        def _sub(data_object, parent_is_dict):
            if isinstance(data_object, dict):
                new_data_object = {}
                for key, value in data_object.items():
                    new_data_object[key] = _sub(value, True)

            elif isinstance(data_object, list):
                new_data_object = []
                for item in data_object:
                    new_data_object.append(_sub(item, False))

            elif isinstance(data_object, str):
                if parent_is_dict == False:
                    new_data_object = self._get_page_with_optional_heading(data_object)

                else:
                    new_data_object = data_object

            else:
                new_data_object = data_object

            return new_data_object

        new_pages = _sub(pages, False)

        return new_pages

    def make(self, target: str) -> str:
        with spinner(f'Making {target} with MkDocs', self.quiet):
            try:
                mkdocs_project_path = self.working_dir / self._mkdocs_project_dir_name

                config = self._mkdocs_config.get('mkdocs.yml', {})

                if 'site_name' not in config and self._mkdocs_config.get('use_title', True):
                    config['site_name'] = self.config['title']

                if 'pages' not in config and self._mkdocs_config.get('use_chapters', True):
                    config['pages'] = self.config['chapters']

                if self._mkdocs_config.get('use_headings', True):
                    config['pages'] = self._get_pages_with_headings(config['pages'])

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
                            self._get_build_command(mkdocs_site_path),
                            shell=True,
                            check=True,
                            stdout=PIPE,
                            stderr=STDOUT,
                            cwd=mkdocs_project_path
                        )

                        return self._mkdocs_site_dir_name

                    except CalledProcessError as exception:
                        raise RuntimeError(f'Build failed: {exception.output.decode()}')

                elif target == 'ghp':
                    try:
                        mkdocs_site_path = Path(self._mkdocs_site_dir_name).absolute()
                        process = run(
                            self._get_ghp_command(),
                            shell=True,
                            check=True,
                            stdout=PIPE,
                            stderr=STDOUT,
                            cwd=mkdocs_project_path
                        )
                        ghp_url = process.stdout.decode().splitlines()[-1].split(': ')[-1]

                        return ghp_url

                    except CalledProcessError as exception:
                        raise RuntimeError(
                            f'GitHub Pages deploy failed: {exception.output.decode()}'
                        )

                else:
                    raise ValueError(f'MkDocs cannot make {target}')

            except Exception as exception:
                raise type(exception)(f'Build failed: {exception}')
