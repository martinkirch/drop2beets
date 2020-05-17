def on_item(item, path):
    """
    This example sets the "Genre" tag at importation depending on which folder
    the file has been dropped in.
    It assumes that the dropbox contains folders like:

    /home/me/my-beets-dropbox/
    ├── Rock
    ├── Rap
    ├── Pop
    ├── Instrumental
    └── Classical

    Dropping a file in "Instrumental" would import it with `genre:Instrumental`.
    The tag value will match the folder name, and you could create as many as
    you want.

    Dropping a file in the root folder `my-beets-dropbox` would do nothing
    because of the test on the 3 first lines. In that case we could also just
    `return item` to still import it and leave `genre` untouched.
    """
    if not path:
        _logger.info("No sub-folder, leaving the file for manual import")
        return None

    # remove first /
    path = path[1:]
    path_parts = path.split('/')
    custom_tags = {}

    if len(path_parts) == 1:
        custom_tags['genre'] = path_parts[0]

    return custom_tags
