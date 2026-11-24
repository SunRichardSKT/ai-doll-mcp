"""Bundle layout and record preservation for the production station."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import flash_esp32
from package_factory import publish_bundle


class FactoryPackageTests(unittest.TestCase):
    def test_update_consolidates_entries_without_deleting_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);staged=root/'staged';destination=root/'installed'
            (staged/'_internal').mkdir(parents=True)
            (staged/'AI_Doll_Factory.exe').write_bytes(b'new-gui')
            (staged/'_internal/esptool-worker.exe').write_bytes(b'new-worker')
            (staged/'使用说明.txt').write_text('one guide',encoding='utf-8')
            records=destination/'build/factory-check'
            records.mkdir(parents=True)
            (records/'completed.json').write_bytes(b'original production result')
            for name in ('先读我.txt','使用说明.md','esptool-worker.exe'):
                (destination/name).write_bytes(b'obsolete')
            publish_bundle(staged,destination)
            self.assertEqual((records/'completed.json').read_bytes(),b'original production result')
            self.assertEqual((destination/'_internal/esptool-worker.exe').read_bytes(),b'new-worker')
            self.assertEqual([p.name for p in destination.glob('*.exe')],['AI_Doll_Factory.exe'])
            self.assertFalse((destination/'先读我.txt').exists())
            self.assertFalse((destination/'使用说明.md').exists())

    def test_stage_cannot_overwrite_production_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);staged=root/'staged';destination=root/'installed'
            (staged/'build').mkdir(parents=True)
            with self.assertRaises(ValueError):publish_bundle(staged,destination)

    def test_frozen_flasher_uses_the_internal_worker(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable=Path(temporary)/'AI_Doll_Factory.exe'
            process=SimpleNamespace(stdout=iter(['esptool worker\n']),wait=lambda:0)
            with patch.object(flash_esp32.sys,'frozen',True,create=True), \
                 patch.object(flash_esp32.sys,'executable',str(executable)), \
                 patch.object(flash_esp32.subprocess,'Popen',return_value=process) as popen:
                flash_esp32.run_tool(['--help'],Path(temporary)/'flash.log')
            self.assertEqual(Path(popen.call_args.args[0][0]),executable.parent/'_internal/esptool-worker.exe')


if __name__=='__main__':unittest.main()
