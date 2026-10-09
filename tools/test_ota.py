import copy
import hashlib
import unittest
from ota_device import validate_image, OtaClient


class ImageValidationTests(unittest.TestCase):
    def setUp(self):
        self.image = bytearray(512)
        self.image[0] = 0xe9
        self.image[12] = 5
        self.image[32:36] = bytes.fromhex('3254cdab')
        self.manifest = {'target': 'ai-doll-supermini-v1', 'chip': 'esp32c3', 'firmware': 'doll-lab-2.6.0',
                         'images': [{'file': 'firmware.bin', 'bytes': 512,
                                     'sha256': hashlib.sha256(self.image).hexdigest()}]}

    def test_valid_application(self):
        self.assertEqual(validate_image(self.image, self.manifest)['bytes'], 512)

    def test_mismatched_bytes_hash_chip_target_and_duplicates(self):
        for field, value in [('bytes', 513), ('bytes', True), ('sha256', '0' * 64)]:
            manifest = copy.deepcopy(self.manifest)
            manifest['images'][0][field] = value
            with self.assertRaises(ValueError):
                validate_image(self.image, manifest)
        for field, value in [('target', 'other'), ('chip', 'esp32'), ('firmware', '')]:
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = value
            with self.assertRaises(ValueError):
                validate_image(self.image, manifest)
        self.manifest['images'].append(self.manifest['images'][0])
        with self.assertRaises(ValueError):
            validate_image(self.image, self.manifest)

    def test_bootloader_or_other_chip_rejected_even_with_valid_digest(self):
        for offset, value in [(0, 0), (12, 0), (32, 0)]:
            image = self.image[:]
            image[offset] = value
            manifest = copy.deepcopy(self.manifest)
            manifest['images'][0]['sha256'] = hashlib.sha256(image).hexdigest()
            with self.assertRaises(ValueError):
                validate_image(image, manifest)

    def test_no_public_or_malformed_host(self):
        for host in ['example.com', '8.8.8.8', '0.0.0.0', '224.1.2.3', '::1', '127.0.0.1/path']:
            with self.assertRaises(ValueError):
                OtaClient(host, {})


if __name__ == '__main__':
    unittest.main()
