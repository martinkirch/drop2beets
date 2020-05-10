import logging
import os

from beets import config
from beets.plugins import BeetsPlugin

_logger = logging.getLogger("drop2beets")


class Drop2BeetsPlugin(BeetsPlugin):
    def __init__(self):
        super(Drop2BeetsPlugin, self).__init__()
        self.register_listener('import_begin', self.on_import_begin)
        self.register_listener('import_task_created', self.on_import_task_created)
        self.register_listener('item_imported', self.on_item_imported)
        self.attributes = None
        self.basepath_len = len(self.config['dropbox_path'].get())
        self.custom_function = self.config['custom_function'].get()

    def on_import_begin(self, session):
        session.config['singletons'] = True
        config['import']['quiet'] = True
        self.attributes = None

    def on_import_task_created(self, task, session):
        path = str(task.item.path, 'utf-8', 'ignore')
        folder = os.path.dirname(path)
        dropbox_path = folder[self.basepath_len:]
        self.attributes = self.custom_function(task.item, dropbox_path)
        if self.attributes is None:
            return []
        else:
            return [task]

    def on_item_imported(self, lib, item):
        if self.attributes:
            _logger.info("Applying %s", self.attributes)
            item.update(self.attributes)
