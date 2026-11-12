"""Exercise real firmware imports and Release downloads without touching USB."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import flash_esp32
import flash_sources as sources


class Response(io.BytesIO):
    def __init__(self, data=b'', url=''):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class FirmwareSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.cache = Path(self.temporary.name) / 'sources'
        self.files = {name: (flash_esp32.ROOT/'firmware/prebuilt'/name).read_bytes()
                      for name in sources.FILES}

    def archive(self, files=None, prefix='AI_Doll/firmware/prebuilt/'):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as package:
            for name, data in (self.files if files is None else files).items():
                package.writestr(prefix + name, data)
            package.writestr('../../outside.txt', b'never extract this')
        stream.seek(0)
        return stream

    def test_import_firmware_or_full_project_zip_only_reads_five_files(self):
        for prefix in ('', 'firmware/prebuilt/', 'AI_Doll/firmware/prebuilt/'):
            with self.subTest(prefix=prefix):
                folder = sources.prepare_zip(self.archive(prefix=prefix), self.cache)
                self.assertEqual({p.name for p in folder.iterdir()}, sources.FILES)
                metadata = sources.describe(folder, 'local', 'fixture')
                self.assertEqual(metadata['firmware'], json.loads(self.files[sources.MANIFEST])['firmware'])
                self.assertEqual(metadata['source_id'], hashlib.sha256(self.files[sources.MANIFEST]).hexdigest())
        self.assertFalse((Path(self.temporary.name)/'outside.txt').exists())

    def test_loose_file_selection_is_validated_before_use(self):
        data = {'files': [dict(name=name, data=base64.b64encode(raw).decode())
                          for name, raw in self.files.items()]}
        folder = sources.prepare_upload(data, self.cache)
        self.assertEqual((folder/'firmware.bin').read_bytes(), self.files['firmware.bin'])
        for bad in ({'files': data['files'][:-1]}, {'files': [data['files'][0]] * 5},
                    {'files': [dict(name='../../firmware.bin', data='AA==')]},
                    {'files': [dict(name='firmware.bin', data='not base64!')]}):
            with self.subTest(bad=str(bad)[:80]), self.assertRaises(ValueError):
                sources.prepare_upload(bad, self.cache)

    def test_corrupt_incomplete_or_wrong_chip_archive_never_survives_validation(self):
        corrupt = dict(self.files, **{'firmware.bin': b'corrupt'})
        missing = {name: raw for name, raw in self.files.items() if name != 'boot_app0.bin'}
        wrong = json.loads(self.files[sources.MANIFEST])
        wrong['chip'] = 'esp32s3'
        invalid_sets = [corrupt, missing,
                        dict(self.files, **{sources.MANIFEST: json.dumps(wrong).encode()}),
                        dict(self.files, **{sources.MANIFEST: b'[]'})]
        for files in invalid_sets:
            with self.subTest(files=list(files)), self.assertRaises(ValueError):
                sources.prepare_zip(self.archive(files), self.cache)
        self.assertFalse(self.cache.exists() and any(self.cache.iterdir()))
        with self.assertRaises(ValueError):
            sources.prepare_zip(io.BytesIO(b'not a ZIP'), self.cache)

    def test_two_manifest_sets_are_ambiguous(self):
        stream = self.archive()
        with zipfile.ZipFile(stream, 'a') as package:
            package.writestr('other/FLASH_MANIFEST.json', self.files[sources.MANIFEST])
        with self.assertRaisesRegex(ValueError, '一套'):
            sources.prepare_zip(stream, self.cache)

    def test_latest_release_uses_public_pages_and_prefers_firmware_asset(self):
        prefix = '/SunRichardSKT/ai-doll-mcp/releases/download/v9.8.7/'
        links = ''.join('<a href="' + prefix + name + '">asset</a>' for name in (
            'AI_Doll_Code_v9.8.7.zip', 'AI_Doll_Firmware_v9.8.7.zip', 'SHA256SUMS.txt'))
        with patch.object(sources, 'open_github', side_effect=[
                Response(url=sources.REPOSITORY+'/releases/tag/v9.8.7'),
                Response(links.encode())]) as network:
            release = sources.latest_release()
        self.assertEqual(release['asset_name'], 'AI_Doll_Firmware_v9.8.7.zip')
        self.assertEqual(network.call_args_list[0].args[0], sources.REPOSITORY+'/releases/latest')
        self.assertIn('/releases/expanded_assets/', network.call_args_list[1].args[0])
        self.assertTrue(all('api.github.com' not in c.args[0] for c in network.call_args_list))

    def test_latest_release_without_a_checksum_is_not_selectable(self):
        with patch.object(sources, 'open_github', side_effect=[
                Response(url=sources.REPOSITORY+'/releases/tag/v9'), Response(b'')]):
            with self.assertRaisesRegex(ValueError, '缺少'):
                sources.latest_release()

    def test_download_verifies_published_archive_and_inner_images(self):
        raw = self.archive().getvalue()
        release = dict(asset_name='AI_Doll_Firmware_v9.zip', checksums_url='fixture-sums', download_url='fixture-zip')
        for checksum, succeeds in ((hashlib.sha256(raw).hexdigest(), True), ('0' * 64, False)):
            with patch.object(sources, 'open_github', side_effect=[
                    Response((checksum + '  ' + release['asset_name'] + '\n').encode()), Response(raw)]):
                if succeeds:
                    folder = sources.download_release(release, self.cache)
                    flash_esp32.validate_images(folder)
                else:
                    before = set(self.cache.iterdir())
                    with self.assertRaisesRegex(ValueError, 'SHA-256'):
                        sources.download_release(release, self.cache)
                    self.assertEqual(set(self.cache.iterdir()), before)

    def test_cli_latest_check_and_local_check_never_flash(self):
        release = dict(tag='v9', asset_name='fixture.zip')
        with patch('sys.argv', ['flash_esp32.py', '--latest', '--check']), \
             patch.object(sources, 'latest_release', return_value=release), \
             patch.object(sources, 'download_release', return_value=flash_esp32.ROOT/'firmware/prebuilt'), \
             patch.object(flash_esp32, 'flash') as write, patch('sys.stdout', new_callable=io.StringIO):
            flash_esp32.main()
            write.assert_not_called()
        archive = Path(self.temporary.name)/'firmware.zip'
        archive.write_bytes(self.archive().getvalue())
        with patch('sys.argv', ['flash_esp32.py', '--images', str(archive), '--check']), \
             patch.object(flash_esp32, 'ROOT', Path(self.temporary.name)), \
             patch.object(flash_esp32, 'flash') as write, patch('sys.stdout', new_callable=io.StringIO):
            flash_esp32.main()
            write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
