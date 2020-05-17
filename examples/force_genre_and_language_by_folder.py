def on_item(item, path):
    """
    This is a variant of `force_genre_by_folder.py` where we may also force
    the `language` using a sub-subfolder.
    It assumes that the dropbox contains folders like:

    /home/me/my-beets-dropbox/
    ├── Rock
         └── fra
    ├── Rap
         └── fra
         └── eng
    ├── Pop
         └── fra
    ├── Instrumental
    └── Classical

    The first level of folders will force the genre.
    For example, sropping a file in `Instrumental` would import it with `genre:Instrumental`.
    The tag value will match the folder name, and you could create as many as you want.
    The sub-level is optional and may be used to force the `language` tag;
    again the value we put in the tag will be the folder's name
    (we test that this name is only 3 characters, just in case someone drops accidently a folder).
    So dropping a file in `Rap/fra` would import it with `genre:Rap` and
    `language:fra`.

    Dropping a file in the root folder `my-beets-dropbox` would do nothing
    because of the test on the 3 first lines. In that case we could also just
    `return {}` to still import it and leave tags untouched.
    """
    if not path:
        _logger.info("No sub-folder, leaving the file for manual import")
        return None

    # remove first /
    path = path[1:]
    path_parts = path.split('/')
    custom_tags = {}

    if len(path_parts) >= 1:
        custom_tags['genre'] = path_parts[0]

    if len(path_parts) >= 2 and len(path_parts[1]) == 3:
        custom_tags['language'] = path_parts[1]

    return custom_tags
