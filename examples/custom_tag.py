def on_item(item, path):
    """
    In this example we'd like to set a flexible attribute
    (see http://beets.io/blog/flexattr.html), only for files
    dropped in a sub-folder. Others will be imported without modification.
    
    This assumes my dropbox is arranged as follows:

    /home/me/my-beets-dropbox/
    └── mood
         ├── good
         ├── bad
         ├── ugly
         └── whatever
    
    """

    # remove first /
    path = path[1:]
    path_parts = path.split('/')

    if len(path_parts) == 2 and path_parts[0] == "mood":
        return {'mood': path_parts[1]}
    else:
        return {}
