"""Gen1 USB production station. SPDX-License-Identifier: AGPL-3.0-only."""
import csv
import datetime as dt
import json
import os
from pathlib import Path
import queue
import sys
import threading
from types import SimpleNamespace
import uuid
import tkinter as tk
from tkinter import filedialog, ttk

from device_lab import SerialLink
import flash_esp32
from flash_esp32 import ROOT, FlashJob, _flash as flash, validate_images, validate_name, select_port
from flash_sources import FILES, prepare_files, prepare_zip, latest_release, download_release, describe
from service_lifecycle import ServiceLease, ServiceAlreadyRunning
from serial.tools.list_ports import comports

if getattr(sys, 'frozen', False):
    ROOT = Path(sys.executable).resolve().parent
    flash_esp32.ROOT = ROOT
IMAGES = Path(sys._MEIPASS) / 'firmware/prebuilt' if getattr(sys, 'frozen', False) else ROOT / 'firmware/prebuilt'


class LiveReadings:
    """Eight physical readings and their observed ranges, without pass/fail rules."""
    def __init__(self):
        self.last_tick = None
        self.samples = 0
        self.channels = []

    def feed(self, frame):
        raw = frame.get('raw')
        if (frame.get('source') != 'sensor' or not isinstance(raw, list) or len(raw) != 8
                or any(type(v) is not int or not 0 <= v <= 4095 for v in raw)):
            raise ValueError('设备未返回有效的八路实体 ADC 样本')
        tick = frame.get('uptime_ms')
        if type(tick) is not int or (self.last_tick is not None and (tick - self.last_tick) % (2**32) not in range(1, 2**31)):
            raise ValueError('设备采样时间未前进，请重新连接')
        self.last_tick = tick
        if not self.channels:
            self.channels = [dict(channel=c, connector=f'J{c + 1}', minimum=v, maximum=v, last=v)
                             for c, v in enumerate(raw)]
        else:
            for row, value in zip(self.channels, raw):
                row.update(minimum=min(row['minimum'], value), maximum=max(row['maximum'], value), last=value)
        self.samples += 1
        return [dict(row) for row in self.channels]


def monitor_sensors(port, cancel, emit, report):
    link = SerialLink(port)
    readings = LiveReadings()
    try:
        state = link.exchange({'cmd': 'status'})
        if state.get('error'):
            raise ValueError(str(state['error']))
        identity = (state['device_id'], state['boot_id'])
        if report.get('expected_device_id', identity[0]) != identity[0]:
            raise ValueError('检测设备与本次烧录设备不一致')
        report.update(device_id=identity[0], boot_id=identity[1], firmware=state['firmware'])
        emit('device', f"{state.get('device_name', identity[0])}  ·  {identity[0]}  ·  {state['firmware']}  ·  {port}")
        if state.get('factory_sample_revision') != 1:
            prefix = '烧录已成功。' if report.get('flash_succeeded') else ''
            raise ValueError(prefix + '该固件不支持八路实时采样，请选用含 factory_sample 入口的配套固件')
        emit('prompt', '八路实时采样中，可自由按压任意传感器；点击“停止采样”结束并保存记录。')
        while not cancel.is_set():
            frame = link.exchange({'cmd': 'factory_sample'}, timeout=3)
            if frame.get('error'):
                raise ValueError(str(frame['error']))
            if (frame.get('device_id'), frame.get('boot_id')) != identity:
                raise ValueError('设备身份变化或重启，请重新连接采样')
            rows = readings.feed(frame)
            report.update(channels=rows, last_raw=frame['raw'], sample_count=readings.samples)
            emit('sample', rows)
            cancel.wait(.1)
        report['status'] = 'observed' if readings.samples else 'cancelled'
    finally:
        link.close()


def prepare_source(kind, value):
    cache = ROOT / 'build/flash-sources'
    if kind == 'bundled':
        folder, label = IMAGES, '随包固件'
    elif kind == 'local':
        path = Path(value)
        if path.is_dir():
            folder = prepare_files({name: (path / name).read_bytes() for name in FILES}, cache)
        else:
            folder = prepare_zip(path, cache)
        label = '本地 · ' + path.name
    elif kind == 'github':
        release = latest_release()
        folder = download_release(release, cache)
        label = 'GitHub · ' + release['tag']
    else:
        raise ValueError('未知固件来源')
    return folder, describe(folder, kind, label)


def save_record(folder, report):
    """Keep historical guided results readable alongside manual observation runs."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (report['run_id'] + '.json')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    summary = folder / '检测汇总.csv'
    columns = ['结束时间', '批次或编号', '结果', '设备编号', '固件', '串口', '检测通道', '已通过通道', '失败原因', '记录文件']
    try:
        with ServiceLease(folder / 'summary.lock'):
            new = not summary.exists() or not summary.stat().st_size
            with summary.open('a', encoding='utf-8-sig', newline='') as stream:
                writer = csv.writer(stream)
                if new:
                    writer.writerow(columns)
                if report.get('schema_version', 1) >= 2:
                    result = {'observed': '已记录', 'cancelled': '已停止', 'error': '异常'}.get(report['status'], '异常')
                else:
                    result = '通过' if report['passed'] else '未通过'
                values = [report['finished_at'], report.get('label', ''), result,
                          report.get('device_id', ''), report.get('firmware', ''), report.get('port', ''),
                          ' '.join('CH' + str(c) for c in report['selected_channels']),
                          ' '.join('CH' + str(r['channel']) for r in report.get('channels', []) if r.get('passed')),
                          report.get('error', ''), path.name]
                writer.writerow(["'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r')) else v for v in values])
    except (OSError, ServiceAlreadyRunning) as error:
        report.update(passed=False, status='error', error='汇总表写入失败，请关闭Excel后重试：' + str(error))
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
        raise
    return path


class Station:
    def __init__(self, window):
        self.window = window
        window.title('AI Doll · 一代批量烧录与八路实时数据')
        window.geometry('1020x760')
        window.minsize(940, 710)
        self.messages = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.active_phase = 'idle'
        self.port_user_selected = False
        self.images = IMAGES
        self.source_info = describe(IMAGES, 'bundled', '随包固件')
        panel = ttk.Frame(window, padding=18)
        panel.pack(fill='both', expand=True)
        ttk.Label(panel, text='一代 C3 · 烧录与八路实时数据', font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='连接主板 → 选择固件 / 填写设备名称 → 烧录或直接采样 → 自由按压观察 → 手动停止换板').pack(anchor='w', pady=8)
        row = ttk.Frame(panel)
        row.pack(fill='x', pady=6)
        ttk.Label(row, text='串口').pack(side='left')
        self.port = ttk.Combobox(row, width=15, state='readonly')
        self.port.bind('<<ComboboxSelected>>', lambda event: setattr(self, 'port_user_selected', True))
        self.port.pack(side='left', padx=8)
        self.refresh_button = ttk.Button(row, text='刷新串口', command=self.refresh)
        self.refresh_button.pack(side='left')
        ttk.Label(row, text='烧录速度').pack(side='left', padx=(12, 4))
        self.baud = ttk.Combobox(row, values=('115200', '460800'), width=9, state='readonly')
        self.baud.set('115200')
        self.baud.pack(side='left')
        row = ttk.Frame(panel)
        row.pack(fill='x', pady=6)
        ttk.Label(row, text='设备名称（选填）').pack(side='left')
        self.name = ttk.Entry(row, width=24)
        self.name.pack(side='left', padx=8)
        ttk.Label(row, text='批次 / 编号（本机记录）').pack(side='left', padx=(12, 0))
        self.label = ttk.Entry(row, width=24)
        self.label.pack(side='left', padx=8)
        row = ttk.Frame(panel)
        row.pack(fill='x', pady=6)
        self.source_buttons = []
        for title, command in [('随包固件', lambda: self.choose_source('bundled')),
                               ('选择刷入 ZIP', self.choose_zip), ('选择固件目录', self.choose_folder),
                               ('从 GitHub 更新', lambda: self.choose_source('github'))]:
            button = ttk.Button(row, text=title, command=command)
            button.pack(side='left', padx=4)
            self.source_buttons.append(button)
        self.source_text = tk.StringVar(value=self.source_label())
        ttk.Label(panel, textvariable=self.source_text, wraplength=970).pack(anchor='w', pady=4)
        self.prompt = tk.StringVar(value='就绪。可直接开始八路采样，手动停止后保存本次读数。')
        self.prompt_label = ttk.Label(panel, textvariable=self.prompt, wraplength=970, font=('Microsoft YaHei UI', 12, 'bold'))
        self.prompt_label.pack(anchor='w', pady=10)
        self.device = tk.StringVar(value='尚未读取设备')
        ttk.Label(panel, textvariable=self.device).pack(anchor='w')
        self.table = ttk.Treeview(panel, columns=('port', 'raw', 'min', 'max', 'range', 'bar'), show='headings', height=8)
        for key, title, width in [('port', '通道 / 插座', 110), ('raw', '实时 ADC', 100),
                                  ('min', '本次最低', 100), ('max', '本次最高', 100),
                                  ('range', '变化范围', 100), ('bar', '电平 0～4095', 300)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor='center')
        self.clear_table()
        self.table.pack(fill='x', pady=10)
        row = ttk.Frame(panel)
        row.pack(fill='x')
        self.flash_button = ttk.Button(row, text='烧录并实时采样', command=lambda: self.start(True))
        self.flash_button.pack(side='left', padx=4)
        self.test_button = ttk.Button(row, text='开始实时采样', command=lambda: self.start(False))
        self.test_button.pack(side='left', padx=4)
        self.stop_button = ttk.Button(row, text='停止采样', command=self.cancel.set, state='disabled')
        self.stop_button.pack(side='left', padx=4)
        ttk.Button(row, text='打开本地记录', command=self.open_records).pack(side='right')
        self.note = tk.StringVar(value='名称为空时使用随机名称。八路数据持续刷新，可同时按压多个传感器。')
        ttk.Label(panel, textvariable=self.note, wraplength=970).pack(anchor='w', pady=8)
        self.flash_log = tk.Text(panel, height=5, wrap='word', state='disabled', font=('Consolas', 9))
        self.flash_log.pack(fill='both', expand=True)
        self.controls = [self.flash_button, self.test_button, self.refresh_button, self.name, self.label,
                         self.port, self.baud, *self.source_buttons]
        self.close_pending = False
        window.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()
        window.after(100, self.poll)
        window.after(1500, self.refresh_idle)

    def source_label(self):
        support = '支持八路采样' if self.source_info.get('factory_sample_revision') == 1 else '未声明八路采样入口'
        return f"当前来源 · {self.source_info['label']} · {self.source_info['firmware']} · {support}"

    def clear_table(self):
        for item in self.table.get_children():
            self.table.delete(item)
        for c in range(8):
            self.table.insert('', 'end', iid=str(c), values=(f'CH{c} / J{c + 1}', '—', '—', '—', '—', ''))

    def set_busy(self, value):
        self.busy = value
        for widget in self.controls:
            widget.configure(state='disabled' if value else 'normal')
        if not value:
            self.port.configure(state='readonly')
            self.baud.configure(state='readonly')

    def choose_zip(self):
        value = filedialog.askopenfilename(title='选择完整固件包', filetypes=[('固件 ZIP', '*.zip')])
        if value:
            self.choose_source('local', value)

    def choose_folder(self):
        value = filedialog.askdirectory(title='选择包含四个 BIN 和 FLASH_MANIFEST.json 的目录')
        if value:
            self.choose_source('local', value)

    def choose_source(self, kind, value=None):
        if self.busy:
            return
        self.set_busy(True)
        self.active_phase = 'prepare'
        self.prompt.set('正在下载并校验 GitHub 最新正式版…' if kind == 'github' else '正在校验固件…')
        threading.Thread(target=self.load_source, args=(kind, value), daemon=False).start()

    def load_source(self, kind, value):
        try:
            folder, info = prepare_source(kind, value)
            self.emit('source', (folder, info))
        except Exception as error:
            self.emit('source_error', str(error))

    def refresh(self):
        ports = list(comports())
        self.port['values'] = [p.device for p in ports]
        if self.port.get() not in self.port['values']:
            self.port_user_selected = False
        if not self.port_user_selected:
            try:
                self.port.set(select_port(ports))
            except ValueError:
                self.port.set('')

    def refresh_idle(self):
        if not self.busy:
            self.refresh()
        self.window.after(1500, self.refresh_idle)

    def open_records(self):
        folder = ROOT / 'build/factory-check'
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def close(self):
        if self.busy:
            self.close_pending = True
            self.cancel.set()
            self.note.set('正在结束任务并保存记录；烧录或下载进行中请等待完成。')
        else:
            self.window.destroy()

    def start(self, write):
        if self.busy:
            return
        try:
            port = self.port.get()
            if not port:
                raise ValueError('请连接开发板并选择串口')
            name = validate_name(self.name.get()) if write and self.name.get().strip() else None
            if write:
                validate_images(self.images)
        except (ValueError, OSError) as error:
            self.prompt.set(str(error))
            return
        self.cancel.clear()
        self.set_busy(True)
        self.job = None
        self.device.set('正在读取本次设备…')
        self.clear_table()
        self.prompt.set('正在烧录，请保持 USB 连接。必要时按住 BOOT，点 RST，再松开 BOOT。' if write else '正在连接设备…')
        self.active_phase = 'flash' if write else 'test'
        self.stop_button.configure(state='disabled' if write else 'normal')
        self.run_baud, self.run_label = int(self.baud.get()), self.label.get().strip()
        self.run_name = name
        self.run_images, self.run_source = self.images, dict(self.source_info)
        self.flash_log.configure(state='normal')
        self.flash_log.delete('1.0', 'end')
        self.flash_log.configure(state='disabled')
        threading.Thread(target=self.run, args=(write, port), daemon=False).start()

    def emit(self, kind, value):
        self.messages.put((kind, value))

    def run(self, write, port):
        report = dict(schema_version=2, run_id=uuid.uuid4().hex,
                      started_at=dt.datetime.now(dt.timezone.utc).isoformat(), selected_channels=list(range(8)),
                      label=self.run_label, requested_name=self.run_name, passed=False,
                      status='running', flash_requested=write, flash_succeeded=False, channels=[], sample_count=0)
        try:
            with ServiceLease(ROOT / 'build/flash-active.lock'):
                if write:
                    report['firmware_source'] = self.run_source
                    job = FlashJob()
                    self.emit('flash_job', job)
                    result = flash(SimpleNamespace(port=port, name=self.run_name, baud=self.run_baud,
                                   images=self.run_images, factory=False, boot_timeout=90, manage_companion=False), job)
                    report.update(flash_id=result['flash_id'], flash_report=str(job.reportfile))
                    if result['status'] != 'success':
                        raise RuntimeError(result.get('error', '烧录失败'))
                    port = result['port']
                    report.update(expected_device_id=result['device_id'], device_id=result['device_id'],
                                  firmware=result.get('firmware'), flash_succeeded=True,
                                  mac=result.get('mac'), manifest_sha256=result.get('manifest_sha256'))
                report['port'] = port
                self.emit('testing', True)
                monitor_sensors(port, self.cancel, self.emit, report)
        except Exception as error:
            report.update(status='error', error=str(error))
        finally:
            report['finished_at'] = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()
            try:
                path = save_record(ROOT / 'build/factory-check', report)
                self.emit('saved', str(path))
            except (OSError, ServiceAlreadyRunning) as error:
                report.update(status='error', error='记录保存失败：' + str(error))
            self.emit('done', report)

    def poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'prompt':
                    self.prompt.set(value)
                elif kind == 'device':
                    self.device.set(value)
                elif kind == 'sample':
                    for row in value:
                        level = '█' * round(row['last'] / 4095 * 24)
                        self.table.item(str(row['channel']), values=(f"CH{row['channel']} / {row['connector']}",
                                        row['last'], row['minimum'], row['maximum'], row['maximum'] - row['minimum'], level))
                elif kind == 'flash_job':
                    self.job = value
                elif kind == 'testing':
                    self.active_phase = 'test'
                    self.stop_button.configure(state='normal')
                elif kind in ('source', 'source_error'):
                    if kind == 'source':
                        self.images, self.source_info = value
                        self.source_text.set(self.source_label())
                        self.prompt.set('固件已校验并选中，可开始烧录。')
                    else:
                        self.prompt.set('固件准备失败：' + value)
                    self.set_busy(False)
                    self.active_phase = 'idle'
                    if self.close_pending:
                        self.window.destroy()
                        return
                elif kind == 'saved':
                    self.note.set('本次记录已保存 ' + value)
                elif kind == 'done':
                    self.set_busy(False)
                    self.active_phase = 'idle'
                    self.stop_button.configure(state='disabled')
                    self.prompt.set('采样已停止，可换板后重新开始。' if value['status'] != 'error' else value['error'])
                    self.refresh()
                    if self.close_pending:
                        self.window.destroy()
                        return
        except queue.Empty:
            pass
        if self.busy and self.active_phase == 'flash' and getattr(self, 'job', None):
            try:
                log = self.job.logfile.read_text(encoding='utf-8', errors='replace')[-6000:]
                self.flash_log.configure(state='normal')
                self.flash_log.delete('1.0', 'end')
                self.flash_log.insert('end', log)
                self.flash_log.see('end')
                self.flash_log.configure(state='disabled')
            except OSError:
                pass
        self.window.after(100, self.poll)


def main():
    window = tk.Tk()
    Station(window)
    window.mainloop()


if __name__ == '__main__':
    main()
