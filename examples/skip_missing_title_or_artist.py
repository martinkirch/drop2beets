def on_item(item, path):
    """
    In this example, we just check that the incoming file has non-empty
    "Artist" and "Title" tags - otherwise, it's not imported and left in the folder.
    """
    if not item.artist.strip() or not item.title.strip():
        _logger.error("Missing artist or title tag")
        return None

    return item
