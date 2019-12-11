
import threading
from .Tools import Tools
from time import time
from resources.config import config


class ThreadedUserProcess(threading.Thread):

    def __init__(self, user):
        threading.Thread.__init__(self)
        self.user = user
        self.runtime = 0

    def run(self):
        start_time = time()
        if config['verbose_username']:
            print("Processing user: {0}".format(self.user.uid))
        self.user.folder_size = Tools().get_folder_size(folder_path=self.user.folder_path)
        self.runtime = time() - start_time

    def join(self):
        return self.user
