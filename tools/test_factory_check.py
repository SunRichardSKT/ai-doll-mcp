"""Continuous production readings, source selection and flash identity handoff."""
import csv
import json
from pathlib import Path
import queue
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from factory_check import CAPTURE_FRAMES, LiveReadings, Station, monitor_sensors, prepare_source, save_record
from flash_esp32 import ROOT, validate_name
from service_lifecycle import ServiceLease, ServiceAlreadyRunning


class LiveTests(unittest.TestCase):
    def frame(self, tick=200, raw=None, **fields):
        return dict(source='sensor', raw=raw if raw is not None else [50] * 8,
                    uptime_ms=tick, device_id='device', boot_id='boot', **fields)

    def test_simultaneous_press_and_high_baseline_never_pause(self):
        readings = LiveReadings()
        readings.feed(self.frame(raw=[2000] * 8))
        rows = readings.feed(self.frame(tick=60000, raw=[4095] * 8))
        self.assertTrue(all(r['minimum'] == 2000 and r['maximum'] == 4095 for r in rows))
        self.assertTrue(all('passed' not in r for r in rows))
        rows = readings.feed(self.frame(tick=120000, raw=[1] * 8))
        self.assertTrue(all(r['minimum'] == 1 and r['maximum'] == 4095 and r['last'] == 1 for r in rows))

    def test_invalid_simulated_and_stale_samples_rejected(self):
        for change in [dict(source='simulation'), dict(raw=[1]), dict(raw=[True] * 8), dict(raw=[4096] * 8)]:
            frame = self.frame()
            frame.update(change)
            with self.assertRaises(ValueError):
                LiveReadings().feed(frame)
        readings = LiveReadings()
        readings.feed(self.frame())
        with self.assertRaises(ValueError):
            readings.feed(self.frame())

    def test_uptime_wrap_is_supported(self):
        readings = LiveReadings()
        readings.feed(self.frame(tick=2**32 - 20))
        readings.feed(self.frame(tick=20))
        self.assertEqual(readings.samples, 2)

    def monitor(self, frames, report=None):
        cancel = threading.Event()
        report = report if report is not None else {}
        state = dict(device_id='device', boot_id='boot', firmware='test', factory_sample_revision=1)
        def emit(kind, value):
            if kind == 'sample':
                cancel.set()
        with patch('factory_check.SerialLink') as serial:
            serial.return_value.exchange.side_effect = [state, *frames]
            monitor_sensors('COM9', cancel, emit, report)
            serial.return_value.close.assert_called_once()
        return report

    def test_manual_stop_records_readings_without_certifying_sensors(self):
        report = self.monitor([self.frame(raw=[900] * 8)])
        self.assertEqual(report['status'], 'observed')
        self.assertEqual(report['sample_count'], 1)
        self.assertNotIn('sensor_passed', report)

    def test_reboot_and_wrong_identity_rejected(self):
        frame = self.frame()
        frame['boot_id'] = 'reboot'
        with self.assertRaisesRegex(ValueError, '重启'):
            self.monitor([frame])
        with self.assertRaisesRegex(ValueError, '不一致'):
            self.monitor([], dict(expected_device_id='different'))

    def test_old_firmware_preserves_successful_flash_result(self):
        report = dict(flash_succeeded=True)
        with patch('factory_check.SerialLink') as serial:
            serial.return_value.exchange.return_value = dict(device_id='device', boot_id='boot', firmware='old')
            with self.assertRaisesRegex(ValueError, '烧录已成功'):
                monitor_sensors('COM9', threading.Event(), lambda *a: None, report)
        self.assertTrue(report['flash_succeeded'])

    def capture_fixture(self, voltages, *, stop_after=None):
        report = dict(fixture=dict(minimum_mv=1240, maximum_mv=1430, ports=[]))
        capture, cancel = threading.Event(), threading.Event()
        def emit(kind, value):
            if kind == 'fixture_ready':
                if len(report['fixture']['ports']) == stop_after:
                    cancel.set()
                else:
                    capture.set()
        state = dict(device_id='device', boot_id='boot', firmware='test',
                     factory_sample_revision=1, factory_sample_millivolts=True)
        frames = [self.frame(tick=200+index*100, adc_mv=mv)
                  for index, mv in enumerate(voltages)]
        with patch('factory_check.SerialLink') as serial, patch.object(cancel, 'wait'):
            serial.return_value.exchange.side_effect = [state, *frames]
            monitor_sensors('COM9', cancel, emit, report, capture)
            serial.return_value.close.assert_called_once()
            if frames:
                self.assertEqual(serial.return_value.exchange.call_args.args[0], {'cmd': 'factory_sample', 'millivolts': True})
        return report

    def test_fixture_checks_empty_then_each_port_with_fresh_median(self):
        frames = [[0]*8]*CAPTURE_FRAMES
        # Keep one transient out of the median.
        for channel in range(8):
            for mv in (100, 1335, 1336, 1337, 1338):
                row = [0]*8
                row[channel] = mv
                frames.append(row)
        report = self.capture_fixture(frames)
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['passed'])
        self.assertEqual(report['sample_count'], 45)
        self.assertTrue(all(row['passed'] and row['fixture_mv'] == 1336 for row in report['channels']))

    def test_fixture_fails_wrong_series_resistor_and_cross_talk(self):
        frames = [[0]*8]*CAPTURE_FRAMES
        for channel in range(8):
            row = [0]*8
            row[channel] = 1574 if channel == 4 else 1336
            if channel == 2:
                row[3] = 350
            frames.extend([row]*CAPTURE_FRAMES)
        report = self.capture_fixture(frames)
        self.assertEqual(report['status'], 'failed')
        self.assertIn('J5 为 1574 mV', report['error'])
        self.assertIn('J4 350 mV', report['error'])
        self.assertEqual([row['channel'] for row in report['channels'] if not row['passed']], [2, 4])

    def test_fixture_high_empty_voltage_and_cancel_are_distinct(self):
        report = self.capture_fixture([[1400]+[0]*7]*CAPTURE_FRAMES)
        self.assertEqual(report['status'], 'failed')
        self.assertIn('J1 1400 mV', report['error'])
        self.assertEqual(report['fixture']['ports'], [])
        report = self.capture_fixture([], stop_after=0)
        self.assertEqual(report['status'], 'cancelled')
        self.assertNotIn('empty_mv', report['fixture'])

    def test_fixture_requires_calibrated_sampling_capability(self):
        state = dict(device_id='device', boot_id='boot', firmware='old', factory_sample_revision=1)
        with patch('factory_check.SerialLink') as serial:
            serial.return_value.exchange.return_value = state
            with self.assertRaisesRegex(ValueError, '毫伏采样'):
                monitor_sensors('COM9', threading.Event(), lambda *a: None, {'fixture': {}}, threading.Event())
            serial.return_value.exchange.assert_called_once_with({'cmd': 'status'})


class StationTests(unittest.TestCase):
    def station(self):
        station = Station.__new__(Station)
        station.cancel = threading.Event()
        station.messages = queue.Queue()
        station.run_name = '出品001'
        station.run_label = 'batch'
        station.run_images = ROOT / 'firmware/prebuilt'
        station.run_source = dict(label='local')
        station.run_baud = 115200
        return station

    def test_flash_passes_name_source_and_returned_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            station = self.station()
            def monitor(port, cancel, emit, report, capture=None):
                self.assertEqual(port, 'COM12')
                self.assertEqual(report['expected_device_id'], 'fresh')
                with self.assertRaises(ServiceAlreadyRunning):
                    with ServiceLease(root / 'build/flash-active.lock'):
                        self.fail('station lease missing')
                report.update(status='observed', sample_count=1)
            result = dict(status='success', flash_id='new', port='COM12', device_id='fresh', firmware='test')
            with patch('factory_check.ROOT', root), patch('factory_check.FlashJob') as job, \
                    patch('factory_check.flash', return_value=result) as flash, \
                    patch('factory_check.monitor_sensors', side_effect=monitor):
                job.return_value.reportfile = root / 'flash.json'
                station.run(True, 'COM4')
                args = flash.call_args.args[0]
                self.assertEqual(args.name, '出品001')
                self.assertEqual(args.images, station.run_images)
                self.assertFalse(args.factory)
                self.assertFalse(args.manage_companion)
            report = json.loads(next((root / 'build/factory-check').glob('*.json')).read_text(encoding='utf-8'))
            self.assertTrue(report['flash_succeeded'])
            self.assertFalse(report['passed'])
            self.assertEqual(report['status'], 'observed')

    def test_failed_source_load_does_not_change_selection(self):
        station = self.station()
        station.images = 'previous'
        with patch('factory_check.prepare_source', side_effect=ValueError('bad checksum')):
            station.load_source('github', None)
        self.assertEqual(station.images, 'previous')
        self.assertEqual(station.messages.get_nowait(), ('source_error', 'bad checksum'))

    def test_github_reuses_verified_downloader(self):
        folder = ROOT / 'firmware/prebuilt'
        release = dict(tag='v-test')
        with patch('factory_check.latest_release', return_value=release), \
                patch('factory_check.download_release', return_value=folder) as download:
            selected, info = prepare_source('github', None)
        self.assertEqual(selected, folder)
        self.assertEqual(info['label'], 'GitHub · v-test')
        self.assertEqual(download.call_args.args[0], release)

    def test_local_directory_is_copied_into_verified_cache(self):
        with tempfile.TemporaryDirectory() as temporary, patch('factory_check.ROOT', Path(temporary)):
            selected, info = prepare_source('local', ROOT / 'firmware/prebuilt')
            self.assertTrue(selected.is_dir())
            self.assertEqual(info['kind'], 'local')
            self.assertNotEqual(selected, ROOT / 'firmware/prebuilt')

    def test_custom_name_uses_existing_utf8_limits(self):
        self.assertEqual(validate_name('出品001'), '出品001')
        with self.assertRaises(ValueError):
            validate_name('娃' * 11)

    def test_summary_keeps_observations_separate_from_legacy_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            common = dict(finished_at='now', selected_channels=[0], label='=1+1')
            save_record(folder, dict(common, run_id='old', passed=True, channels=[dict(channel=0, passed=True)]))
            save_record(folder, dict(common, run_id='new', schema_version=2, passed=False,
                                     status='observed', channels=[dict(channel=0, minimum=5, maximum=2000)]))
            save_record(folder, dict(common, run_id='fixture', schema_version=2, passed=False,
                                     status='failed', channels=[dict(channel=0, passed=True)], error='J2 未通过'))
            with (folder / '检测汇总.csv').open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[1][2], '通过')
            self.assertEqual(rows[2][2], '已记录')
            self.assertEqual(rows[2][7], '')
            self.assertEqual(rows[2][1], "'=1+1")
            self.assertEqual(rows[3][2], '未通过')
            self.assertEqual(rows[3][7:9], ['CH0', 'J2 未通过'])

    def test_csv_busy_keeps_error_in_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            report = dict(run_id='run', schema_version=2, finished_at='now', selected_channels=[0], status='observed')
            with ServiceLease(folder / 'summary.lock'):
                with self.assertRaises(ServiceAlreadyRunning):
                    save_record(folder, report)
            saved = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['status'], 'error')


if __name__ == '__main__':
    unittest.main()
