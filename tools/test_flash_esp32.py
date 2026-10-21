"""Protect flashing boundaries, file integrity and deterministic port selection."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
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

    @unittest.skipUnless(os.name == 'nt', 'Windows file-sharing semantics')
    def test_result_save_recovers_from_a_real_windows_open_reader(self):
        with tempfile.TemporaryDirectory() as temporary:
            job=flasher.FlashJob(temporary)
            with job.reportfile.open('rb') as reader:
                # Reproduce the reported failure with an actual Windows handle.
                blocked=job.folder/'probe.tmp';blocked.write_text('{}',encoding='utf-8')
                with self.assertRaises(PermissionError):blocked.replace(job.reportfile)
                release=threading.Timer(.06,reader.close);release.start()
                try:job.update(phase='connect')
                finally:release.join()
            self.assertEqual(json.loads(job.reportfile.read_text(encoding='utf-8'))['phase'],'connect')
            self.assertFalse((job.folder/'result.tmp').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows access denied semantics')
    def test_permanent_result_denial_stays_visible_and_preserves_the_old_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            job=flasher.FlashJob(temporary);before=job.reportfile.read_bytes()
            with job.reportfile.open('rb'),patch.object(flasher.time,'sleep'):
                with self.assertRaises(PermissionError):job.update(phase='write')
            self.assertEqual(job.reportfile.read_bytes(),before)

    def test_snapshot_cannot_mutate_the_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            job=flasher.FlashJob(temporary);job.update(details={'port':'COM4'})
            view=job.snapshot();view['details']['port']='another'
            self.assertEqual(job.snapshot()['details']['port'],'COM4')

    def test_names_use_utf8_bytes_and_preserve_spaces_inside(self):
        self.assertIsNone(flasher.validate_name(None))
        self.assertEqual(flasher.validate_name('  小 樱  '), '小 樱')
        self.assertEqual(flasher.validate_name('樱'*10+'AB'), '樱'*10+'AB')
        for name in ('樱'*11, 'a'*33, '', '  ', 'head\nfoot', 'a\x00b', 42):
            with self.subTest(name=repr(name)), self.assertRaises(ValueError):
                flasher.validate_name(name)

    def identity_state(self, job, name=None):
        return {'serial_port':'COM4', 'device_id':job.report['target_device_id'],
                'flash_id':job.id, 'device_name':name or job.report['target_device_id'],
                'configuration_hotspot':name or job.report['target_device_id']}

    def test_custom_name_is_sent_to_board_and_internal_id_stays_random(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = flasher.FlashJob(temporary)
            state = self.identity_state(job, '小樱')
            with patch('device_lab.SerialLink') as serial, patch.object(flasher, 'boot_status', return_value=state) as boot:
                serial.return_value.exchange.return_value = {'ok':True}
                self.assertEqual(flasher.set_identity('COM4',job,'manifest-version',5,'小樱'),state)
            serial.return_value.exchange.assert_called_once_with(
                {'cmd':'flash_identity','suffix':job.suffix,'flash_id':job.id,'name':'小樱'},timeout=3)
            boot.assert_called_once_with('COM4','manifest-version',timeout=5,device_id='AI-Doll-'+job.suffix)
            self.assertNotEqual(state['device_id'], state['device_name'])
            serial.return_value.close.assert_called_once()

    def test_random_name_omits_custom_field_and_verifies_hotspot_after_reboot(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = flasher.FlashJob(temporary)
            state = self.identity_state(job)
            with patch('device_lab.SerialLink') as serial, patch.object(flasher, 'boot_status', return_value=state):
                serial.return_value.exchange.side_effect = TimeoutError('reboot acknowledgement lost')
                self.assertEqual(flasher.set_identity('COM4',job,'manifest-version',5),state)
            self.assertNotIn('name',serial.return_value.exchange.call_args.args[0])

    def test_wrong_name_or_flash_id_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = flasher.FlashJob(temporary)
            for changes in ({'device_name':'old'}, {'configuration_hotspot':'old'}, {'flash_id':'old'}):
                state = dict(self.identity_state(job,'小樱'), **changes)
                with self.subTest(changes=changes), patch('device_lab.SerialLink') as serial, \
                     patch.object(flasher, 'boot_status', return_value=state):
                    serial.return_value.exchange.return_value = {'ok':True}
                    with self.assertRaises(RuntimeError):
                        flasher.set_identity('COM4',job,'manifest-version',5,'小樱')

    def test_device_rejection_does_not_proceed_to_boot_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = flasher.FlashJob(temporary)
            with patch('device_lab.SerialLink') as serial, patch.object(flasher,'boot_status') as boot:
                serial.return_value.exchange.return_value = {'error':'unsupported name'}
                with self.assertRaisesRegex(RuntimeError,'unsupported name'):
                    flasher.set_identity('COM4',job,'manifest-version',5,'小樱')
                boot.assert_not_called()

    def test_custom_hotspot_is_not_used_as_pairing_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            job=flasher.FlashJob(folder/'flash')
            state=self.identity_state(job,'小樱')
            config=folder/'device-private.json'
            config.write_text(json.dumps({'device_id':'AI-Doll-old','history_path':'keep.db',
                                          'calibration_note':'keep'}),encoding='utf-8')
            with patch('device_lab.CONFIG',config),patch('device_lab.SerialLink') as serial:
                serial.return_value.exchange.return_value={'ap_ssid':'小樱','mcp_token':'fixture-token'}
                self.assertTrue(flasher.refresh_pairing({'device_id':'AI-Doll-old'},state))
            saved=json.loads(config.read_text(encoding='utf-8'))
            self.assertEqual(saved['device_id'],job.report['target_device_id'])
            self.assertEqual(saved['ap_ssid'],'小樱')
            self.assertEqual(saved['history_path'],'keep.db')
            self.assertEqual(saved['calibration_note'],'keep')

    def run_flash(self, factory=False, probe='Detected flash size: 4MB\nMAC: aa:bb:cc:dd:ee:ff', boot_error=None, name=None, state_changes=None):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        args=SimpleNamespace(images=ROOT/'firmware/prebuilt',port='COM4',baud=460800,factory=factory,boot_timeout=5,name=name)
        job=flasher.FlashJob(root/'build/flash')
        state={'serial_port':'COM4','firmware':'test','device_id':job.report['target_device_id'],
               'configuration_url':'http://192.168.4.1/','configuration_hotspot':name or job.report['target_device_id'],
               'device_name':name or job.report['target_device_id'],
               'config_ap_open':True,'sensor_mode':'sensor','physical_outputs_enabled':False,
               'wifi_connected':False,'factory_profile':'physical-ch0-v1','flash_id':job.id}
        state.update(state_changes or {})
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

    def test_factory_defaults_require_real_input_and_disarmed_outputs(self):
        for changes in ({'sensor_mode':'simulation'}, {'physical_outputs_enabled':True},
                        {'factory_profile':'safe-manual-v1'}):
            with self.subTest(changes=changes):
                result,_,_=self.run_flash(factory=True,state_changes=changes)
                self.assertEqual(result['status'],'failed')
                self.assertIn('默认状态',result['error'])

    def test_named_flash_keeps_random_pairing_id_and_records_actual_hotspot(self):
        result,_,job=self.run_flash(name='小樱')
        self.assertEqual(result['status'],'success')
        self.assertEqual(result['device_id'],'AI-Doll-'+job.suffix)
        self.assertEqual(result['configuration_hotspot'],'小樱')
        self.assertEqual(result['naming_mode'],'custom')

    def test_invalid_name_never_accesses_board(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(flasher,'ROOT',Path(temporary)):
            with patch.object(flasher,'pause_collector') as pause, patch.object(flasher,'run_tool') as tool:
                result=flasher.flash(SimpleNamespace(name='a'*33))
            self.assertEqual(result['status'],'failed')
            pause.assert_not_called();tool.assert_not_called()

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
