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

        self._mkdocs_site_dir_name = f'{self._mkdocs_config.get("slug", self.get_slug())}.mkdocs'

        self._mkdocs_project_dir_name = f'{self._mkdocs_site_dir_name}.src'

        self.required_preprocessors_after = {
            'mkdocs': {
                'mkdocs_project_dir_name': self._mkdocs_project_dir_name
            }
        },

        self.logger = self.logger.getChild('mkdocs')

        self.logger.debug(f'Backend inited: {self.__dict__}')

    def _escape_control_characters(self, source_string: str) -> str:
        '''Escape control characters such as double quotation mark, dollar sign, backtick
        to use them in system shell commands.

        :param source_string: String that contains control characters

        :returns: String with control characters escaped by backslash
        '''

        escaped_string = source_string.replace('"', "\\\"").replace('$', "\\$").replace('`', "\\`")

        return escaped_string

    def _get_build_command(self, mkdocs_site_path: Path) -> str:
        '''Generate ``mkdocs build`` command to build the site.

        :param mkdocs_site_path: Path to the output directory for the site
        '''

        components = [self._mkdocs_config.get('mkdocs_path', 'mkdocs')]
        components.append('build')
        components.append(f'-d "{self._escape_control_characters(str(mkdocs_site_path))}"')

        command = ' '.join(components)

        self.logger.debug(f'Build command: {command}')

        return command

    def _get_ghp_command(self) -> str:
        '''Generate ``mkdocs gh-deploy`` command to deploy the site to GitHub Pages.'''

        components = [self._mkdocs_config.get('mkdocs_path', 'mkdocs')]
        components.append('gh-deploy')

        command = ' '.join(components)

        self.logger.debug(f'GHP upload command: {command}')

        return command

    def _get_page_with_optional_heading(self, page_file_path: str) -> str or Dict:
        '''Get the content of first heading of source Markdown file, if the file
        contains any headings. Return a data element of ``pages`` section
        of ``mkdocs.yml`` file.

        :param page_file_path: path to source Markdown file

        :returns: Unchanged file path or a dictionary: content of first heading, file path
        '''

        self.logger.debug(f'Looking for the first heading in {page_file_path}')

        if page_file_path.endswith('.md'):
            page_file_full_path = self.working_dir /\
                self._mkdocs_project_dir_name / 'docs' / page_file_path

            with open(page_file_full_path, encoding='utf8') as page_file:
                content = page_file.read()

                headings_found = re.search(
                    r'^\#{1,6}\s+(.+?)(?:\s+\{\#\S+\})?\s*$',
                    content,
                    flags=re.MULTILINE
                )

                if headings_found:
                    first_heading = headings_found.group(1)
                    self.logger.debug(f'Heading found: {first_heading}')
                    return {first_heading: page_file_path}

        self.logger.debug(f'No heading found, returning original file path.')

        return page_file_path

    def _get_pages_with_headings(self, pages: Dict) -> Dict:
        '''Update ``pages`` section of ``mkdocs.yml`` file with the content
        of top-level headings of source Markdown files.

        param pages: Dictionary with the data of ``pages`` section

        returns: Updated dictionary
        '''

        def _recursive_process_pages(pages_subset, parent_is_dict):
            if isinstance(pages_subset, dict):
                new_pages_subset = {}
                for key, value in pages_subset.items():
                    if not key:
                        key = self._mkdocs_config.get('default_subsection_title', '…')

                    new_pages_subset[key] = _recursive_process_pages(value, True)

            elif isinstance(pages_subset, list):
                new_pages_subset = []
                for item in pages_subset:
                    new_pages_subset.append(_recursive_process_pages(item, False))

            elif isinstance(pages_subset, str):
                if not parent_is_dict:
                    new_pages_subset = self._get_page_with_optional_heading(pages_subset)

                else:
                    new_pages_subset = pages_subset

            else:
                new_pages_subset = pages_subset

            return new_pages_subset

        new_pages = _recursive_process_pages(pages, False)

        self.logger.debug(f'All pages with their headings: {new_pages}')

        return new_pages

    def make(self, target: str) -> str:
        with spinner(f'Making {target} with MkDocs', self.logger, self.quiet, self.debug):
            try:
                mkdocs_project_path = self.working_dir / self._mkdocs_project_dir_name

                config = self._mkdocs_config.get('mkdocs.yml', {})

                self.logger.debug(f'Backend config: {config}')

                if 'site_name' not in config and self._mkdocs_config.get('use_title', True):
                    config['site_name'] = self.config['title']

                if 'pages' not in config and self._mkdocs_config.get('use_chapters', True):
                    config['nav'] = self.config['chapters']

                if self._mkdocs_config.get('use_headings', True):
                    config['nav'] = self._get_pages_with_headings(config['nav'])

                self.logger.debug(f'mkdocs.yml: {config}')

                with open(mkdocs_project_path/'mkdocs.yml', 'w', encoding='utf8') as mkdocs_config:
                    self.logger.debug(f'Saving mkdocs.yml into {mkdocs_project_path}')
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
                        mkdocs_process = run(
                            self._get_build_command(mkdocs_site_path),
                            shell=True,
                            check=True,
                            stdout=PIPE,
                            stderr=STDOUT,
                            cwd=mkdocs_project_path
                        )

                        mkdocs_output = mkdocs_process.stdout.decode()
                        success_build_marker = 'Documentation built in'

                        if success_build_marker not in mkdocs_output:
                            raise RuntimeError(f'MkDocs cannot make {target}\nmkdocs logs:\n {mkdocs_output}')

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
                raise RuntimeError(f'Build failed: {exception}')
