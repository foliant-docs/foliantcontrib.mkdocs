import re
from shutil import move, copy
from pathlib import Path
from os.path import relpath
from uuid import uuid1

from foliant.preprocessors.base import BasePreprocessor


class Preprocessor(BasePreprocessor):
    defaults = {'mkdocs_project_dir_name': 'mkdocs'}

    _image_pattern = re.compile(r'\!\[(?P<caption>.*?)\]\((?P<path>((?!:\/\/).)+)\)')

    def _collect_images(self, content: str, md_file_path: Path) -> str:
        '''Find images outside the source directory, copy them into the source directory,
        and replace the paths in the source.

        This is necessary because MkDocs can't deal with images outside the project's doc_dir.

        :param content: Markdown content
        :param md_file_path: Path to the Markdown file with content ``content``

        :returns: Markdown content with image paths pointing within the source directory
        '''

        self.logger.debug(f'Looking for images in {md_file_path}.')

        def _sub(image):
            image_caption = image.group('caption')
            image_path = (md_file_path.parent / Path(image.group('path'))).resolve()

            self.logger.debug(f'Detected image: caption="{image_caption}", path={image_path}')

            if self.working_dir.resolve() not in image_path.parents:
                self.logger.debug('Image outside source directory.')

                self._collected_imgs_path.mkdir(exist_ok=True)

                collected_img_path = (
                    self._collected_imgs_path/f'{image_path.stem}_{str(uuid1())}'
                ).with_suffix(image_path.suffix)

                copy(image_path, collected_img_path)

                self.logger.debug(f'Image copied to {collected_img_path}')

                rel_img_path = Path(relpath(collected_img_path, md_file_path.parent)).as_posix()

            else:
                self.logger.debug('Image inside source directory.')
                rel_img_path = Path(relpath(image_path, md_file_path.parent)).as_posix()

            img_ref = f'![{image_caption}]({rel_img_path})'

            self.logger.debug(f'Replacing with: {img_ref}')

            return img_ref

        return self._image_pattern.sub(_sub, content)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._collected_imgs_path = self.working_dir / f'_img_{str(uuid1())}'

        self.logger = self.logger.getChild('mkdocs')

        self.logger.debug(f'Preprocessor inited: {self.__dict__}')

    def apply(self):
        for markdown_file_path in self.working_dir.rglob('*.md'):
            with open(markdown_file_path, encoding='utf8') as markdown_file:
                content = markdown_file.read()

            processed_content = self._collect_images(content, markdown_file_path)

            if processed_content:
                with open(markdown_file_path, 'w', encoding='utf8') as markdown_file:
                    markdown_file.write(processed_content)

        mkdocs_project_path = self.working_dir / self.options['mkdocs_project_dir_name']
        mkdocs_tmp_project_path = self.working_dir / str(uuid1())
        mkdocs_src_path = mkdocs_tmp_project_path / 'docs'
        mkdocs_src_path.mkdir(parents=True)

        for item in self.working_dir.glob('*'):
            if item.name == mkdocs_tmp_project_path.name:
                continue
            else:
                move(str(item), str(mkdocs_src_path))

        move(str(mkdocs_tmp_project_path), str(mkdocs_project_path))

        self.logger.debug(f'Moved {mkdocs_tmp_project_path} to {mkdocs_project_path}')
