"""Read manifest-based ZIP/TAR deliveries without extracting untrusted members."""
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


class TarDelivery:
    def __init__(self, path):
        self.archive = tarfile.open(path, 'r:gz')
        members = self.archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            self.archive.close(); raise ValueError('Duplicate archive member')
        for member in members:
            name = PurePosixPath(member.name)
            if not member.isfile() or member.size > 100_000_000 or name.is_absolute() or '..' in name.parts:
                self.archive.close(); raise ValueError('Unsafe server archive member')

    def __enter__(self): return self
    def __exit__(self, *args): self.archive.close()
    def namelist(self): return self.archive.getnames()
    def testzip(self): return None
    def read(self, name):
        with self.archive.extractfile(name) as member: return member.read()


def open_delivery(path):
    if zipfile.is_zipfile(path): return zipfile.ZipFile(path)
    return TarDelivery(path)
