"""Protect flashing boundaries, file integrity and deterministic port selection."""
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import flash_esp32 as flasher
from service_lifecycle import ServiceLease

from flash_esp32 import ROOT, validate_images, select_port


class FlashTests(unittest.TestCase):
    def test_delivery_images(self):
        manifest, pairs = validate_images(ROOT/'firmware/prebuilt')
        self.assertEqual(manifest['chip'], 'esp32c3')
        self.assertEqual(pairs[::2], ['0x0','0x8000','0xe000','0x10000'])

    def test_corruption_and_nvs_boundary_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            for source in (ROOT/'firmware/prebuilt').glob('*.bin'):
                shutil.copyfile(source,path/source.name)
            source = ROOT/'firmware/prebuilt/FLASH_MANIFEST.json'
            manifest = json.loads(source.read_text(encoding='utf-8'))
            (path/'FLASH_MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8')
            firmware = path/'firmware.bin'
            raw = firmware.read_bytes(); firmware.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            with self.assertRaisesRegex(ValueError,'SHA-256'): validate_images(path)
            firmware.write_bytes(raw)
            manifest['images'][1]['offset']='0x9000'
            (path/'FLASH_MANIFEST.json').write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'地址'): validate_images(path)

    def test_ambiguous_ports_require_selection(self):
        port = lambda name,vid: SimpleNamespace(device=name,vid=vid)
        ports = [port('COM1',None),port('COM4',0x303a)]
        self.assertEqual(select_port(ports),'COM4')
        ports.append(port('COM5',0x303a))
        with self.assertRaises(ValueError): select_port(ports)
        self.assertEqual(select_port(ports,'COM5'),'COM5')
        with self.assertRaises(ValueError): select_port(ports,'COM8')

    def test_every_attempt_has_an_independent_suffix_and_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            jobs=[flasher.FlashJob(temporary) for _ in range(12)]
            self.assertEqual(len({j.suffix for j in jobs}),12)
            for job in jobs:
                self.assertTrue(job.logfile.exists())
                self.assertEqual(json.loads(job.reportfile.read_text())['target_device_id'],'AI-Doll-'+job.suffix)

    def run_flash(self, factory=False, probe='Detected flash size: 4MB\nMAC: aa:bb:cc:dd:ee:ff', boot_error=None):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        args=SimpleNamespace(images=ROOT/'firmware/prebuilt',port='COM4',baud=460800,factory=factory,boot_timeout=5)
        job=flasher.FlashJob(root/'build/flash')
        state={'serial_port':'COM4','firmware':'test','device_id':job.report['target_device_id'],
               'configuration_url':'http://192.168.4.1/','configuration_hotspot':job.report['target_device_id'],
               'config_ap_open':True,'sensor_mode':'simulation','physical_outputs_enabled':False,
               'wifi_connected':False,'factory_profile':'safe-manual-v1','flash_id':job.id}
        with patch.object(flasher,'ROOT',root), patch.object(flasher,'pause_collector',return_value=False), \
             patch.object(flasher,'capture_existing',return_value={}), patch.object(flasher,'select_port',return_value='COM4'), \
             patch.object(flasher,'run_tool',return_value=probe) as tool, \
             patch.object(flasher,'boot_status',return_value=state,side_effect=boot_error), \
             patch.object(flasher,'set_identity',return_value=state), patch.object(flasher,'refresh_pairing',return_value=False):
            result=flasher.flash(args,job)
        return result,tool,job

    def test_standard_flash_does_not_erase_and_verifies_new_identity(self):
        result,tool,job=self.run_flash()
        self.assertEqual(result['status'],'success')
        self.assertTrue(result['identity_verified'])
        self.assertFalse(result['full_erase'])
        calls=[c.args[0] for c in tool.call_args_list]
        self.assertFalse(any('erase_flash' in c for c in calls))
        self.assertEqual(result['device_id'],'AI-Doll-'+job.suffix)

    def test_factory_explicitly_erases_before_writing(self):
        result,tool,_=self.run_flash(factory=True)
        self.assertEqual(result['status'],'success')
        calls=[c.args[0] for c in tool.call_args_list]
        self.assertIn('erase_flash',calls[1]);self.assertIn('write_flash',calls[2])

    def test_wrong_chip_capacity_never_writes(self):
        result,tool,job=self.run_flash(probe='Detected flash size: 8MB')
        self.assertEqual(result['status'],'failed');self.assertEqual(tool.call_count,1)
        self.assertIn('4MB',job.logfile.read_text(encoding='utf-8'))

    def test_write_success_is_not_boot_success(self):
        result,_,job=self.run_flash(boot_error=RuntimeError('启动未确认'))
        self.assertEqual(result['status'],'failed');self.assertTrue(result['write_hash_verified'])
        self.assertFalse(result['boot_verified']);self.assertFalse(result['identity_verified'])
        self.assertIn('启动未确认',job.logfile.read_text(encoding='utf-8'))

    def test_bad_images_leave_a_failure_report_without_touching_device(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(flasher,'ROOT',Path(temporary)):
            args=SimpleNamespace(images=Path(temporary)/'missing',factory=False)
            job=flasher.FlashJob()
            with patch.object(flasher,'pause_collector') as pause:
                result=flasher.flash(args,job)
            self.assertEqual(result['status'],'failed');pause.assert_not_called()
            self.assertTrue(job.logfile.read_text(encoding='utf-8'))

    def test_another_process_cannot_flash_concurrently(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(flasher,'ROOT',Path(temporary)):
            root=Path(temporary);(root/'build').mkdir()
            with ServiceLease(root/'build/flash-active.lock'),patch.object(flasher,'_flash') as run:
                result=flasher.flash(SimpleNamespace())
                self.assertEqual(result['status'],'failed');run.assert_not_called()


if __name__ == '__main__': unittest.main()
