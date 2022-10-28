# 1.0.14

- Fix `_image_pattern` not to match image refs with brackets in captions

# 1.0.13

- Update to mkdocs 1.3.0
- Replaced `pages` to `nav` in config generation due to [github.com/mkdocs/mkdocs/pull/2652](https://github.com/mkdocs/mkdocs/pull/2652)

# 1.0.12

-   Do not re-raise an exception of the same type as raised, raise `RuntimeError` instead, it’s needed to avoid non-informative error messages.

# 1.0.11

-   Get captions for pages from workingdir instead of src_dir

# 1.0.10

-   Fix pattern for heading detection.

# 1.0.9

-   Allow the first heading to be located not in the beginning of a document.

# 1.0.8

-   Escape control characters (double quotation marks, dollar signs, backticks) that may be used in system shell commands.

# 1.0.7

-   Provide compatibility with Foliant 1.0.8.

# 1.0.6

-   Provide compatibility with Foliant 1.0.7.

# 1.0.5

-   Require MkDocs 1.0.4.

# 1.0.4

-   Provide customizable default names for untitled nested groups of chapters.

# 1.0.3

-   Add logs.
-   Update for Foliant 1.0.4: Pass logger to spinner.
-   Require Foliant 1.0.4.

# 1.0.2

-   Add `use_headings` and `slug` options for MkDocs backend.
-   Fix inappropriate translation of image URLs into local paths in MkDocs preprocessor.

# 1.0.1

-   Add `ghp` target for GitHub Pages deploy with `mkdocs gh-deploy`.
