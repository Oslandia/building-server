from os import listdir, path
from string import strip


dir_path = path.dirname(path.realpath(__file__))

__all__ = [s[:-3] for s in listdir(dir_path) if s.endswith(".py")]
