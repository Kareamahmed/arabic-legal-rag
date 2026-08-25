from helper.config import Settings, get_settings
from pathlib import Path


class BaseController:
    def __init__(self):
        self.app_setting: Settings = get_settings()
        self.data_path = Path.cwd().parent / "src" / "assets" / "data" / "corpus.json"
