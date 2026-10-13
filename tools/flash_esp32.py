"""Verified, no-build USB flashing of the ESP32-C3 delivery images.

Normal flashing writes only the four manifest images. NVS and the event store
are not erased. Several candidates require an explicit --port selection.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_OFFSETS = {'bootloader.bin': 0, 'partitions.bin': 0x8000,
                    'boot_app0.bin': 0xe000, 'firmware.bin': 0x10000}


def validate_images(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / 'FLASH_MANIFEST.json').read_text(encoding='utf-8'))
    if (manifest.get('chip'), manifest.get('flashSize'), manifest.get('flashMode'),
        manifest.get('flashFrequency')) != ('esp32c3', '4MB', 'dio', '80m'):
        raise ValueError('固件清单不是本项目的 ESP32-C3 / 4MB / DIO / 80MHz 配置。')
    images = manifest.get('images', [])
    if len(images) != 4 or {item['file'] for item in images} != set(EXPECTED_OFFSETS):
        raise ValueError('固件清单必须包含四个指定镜像。')
    pairs = []
    previous_end = 0
    for item in sorted(images, key=lambda image: int(image['offset'], 0)):
        name = item['file']
        offset = int(item['offset'], 0)
        path = folder / name
        data = path.read_bytes()
        if offset != EXPECTED_OFFSETS[name] or offset < previous_end:
            raise ValueError('镜像地址不正确或重叠：' + name)
        # Boot sectors/NVS boundaries and the app0 0x140000 partition.
        limit = {'bootloader.bin':0x8000, 'partitions.bin':0x9000,
                 'boot_app0.bin':0x10000, 'firmware.bin':0x150000}[name]
        if not data or len(data) != item['bytes'] or offset + len(data) > limit:
            raise ValueError('镜像大小或写入边界不正确：' + name)
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('镜像 SHA-256 校验失败：' + name)
        previous_end = offset + len(data)
        pairs += [hex(offset), str(path)]
    return manifest, pairs


def select_port(ports, explicit=None):
    if explicit:
        if not any(port.device.lower() == explicit.lower() for port in ports):
            raise ValueError('未检测到串口 ' + explicit)
        return explicit
    candidates = [port for port in ports if port.vid == 0x303a]
    if not candidates:
        candidates = [port for port in ports if port.vid in (0x1a86, 0x10c4, 0x0403)]
    if len(candidates) != 1:
        raise ValueError('未找到唯一开发板。请用 --list-ports 查看，再指定 --port COM4（按实际串口填写）。')
    return candidates[0].device


def run_tool(arguments, logfile):
    command = [sys.executable, '-X', 'utf8', '-m', 'esptool'] + arguments
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace')
    lines = []
    with logfile.open('a', encoding='utf-8') as log:
        for line in process.stdout:
            print(line, end='', flush=True); log.write(line); lines.append(line)
    if process.wait() != 0:
        raise RuntimeError('烧录工具执行失败。关闭串口监视器；必要时按住 BOOT，点按 RST，再松开 BOOT 后重试。')
    return ''.join(lines)


def boot_status(port, expected, timeout=180, device_id=None):
    from device_lab import SerialLink
    from serial.tools.list_ports import comports
    link = SerialLink(port)
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            state = link.exchange({'cmd':'status'}, timeout=3)
            if state.get('firmware') != expected:
                raise RuntimeError('设备启动版本与烧录清单不同。')
            if device_id and state.get('device_id') != device_id:
                time.sleep(.5)
                continue
            state['serial_port'] = port
            return state
        except (OSError, TimeoutError):
            link.close()
            if not any(p.device == port for p in comports()):
                try: port = select_port(list(comports()))
                except ValueError: pass
                link = SerialLink(port)
            time.sleep(.5)
        finally:
            link.close()
    raise RuntimeError('写入已完成，但未确认应用启动。点按 RST 后重试状态检查，详见烧录日志。')


class FlashJob:
    """One exclusive directory per attempt, including early failures."""
    def __init__(self, folder=None):
        folder = Path(folder or ROOT/'build/flash')
        folder.mkdir(parents=True, exist_ok=True)
        while True:
            self.suffix = uuid.uuid4().hex[:20]
            self.id = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S') + '-' + self.suffix
            self.folder = folder/self.id
            try:
                self.folder.mkdir()
                break
            except FileExistsError:
                continue
        self.logfile = self.folder/'flash.log'
        self.logfile.touch()
        self.reportfile = self.folder/'result.json'
        self.report = dict(flash_id=self.id, device_suffix=self.suffix,
                           target_device_id='AI-Doll-'+self.suffix,
                           status='running', phase='prepare', write_hash_verified=False,
                           boot_verified=False, identity_verified=False)
        self.update()

    def update(self, **fields):
        self.report.update(fields)
        temporary = self.folder/'result.tmp'
        temporary.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.reportfile)

    def message(self, text):
        print(text, flush=True)
        with self.logfile.open('a', encoding='utf-8') as log:
            log.write(text+'\n')


def pause_collector(port):
    """Release only this project's USB collector; never interrupt a chat session."""
    from control_panel import request_collector, collector_stop
    try:
        connection = request_collector('/connection', timeout=2)
    except (OSError, ValueError):
        return False
    if connection.get('transport') != 'usb' or connection.get('serial_port','').lower() != port.lower():
        return False
    active = request_collector('/companion/tool', {'name':'get_interaction_status','arguments':{}}, timeout=3)
    if active.get('active_session'):
        raise RuntimeError('互动会话正在进行。请先结束互动，再烧录。')
    collector_stop()
    return True


def capture_existing(port):
    from device_lab import SerialLink
    link = SerialLink(port)
    try:
        return link.exchange({'cmd':'status'}, timeout=2)
    except (OSError, TimeoutError):
        return {}
    finally:
        link.close()


def set_identity(port, job, expected, timeout):
    from device_lab import SerialLink
    link = SerialLink(port)
    try:
        try:
            reply = link.exchange({'cmd':'flash_identity','suffix':job.suffix,'flash_id':job.id}, timeout=3)
            if reply.get('error') or reply.get('ok') is not True:
                raise RuntimeError('设备未保存新编号：'+str(reply.get('error','无有效确认')))
        except (OSError, TimeoutError):
            # A lost reboot acknowledgement is resolved by reading the saved ID.
            pass
    finally:
        link.close()
    state = boot_status(port, expected, timeout=timeout, device_id=job.report['target_device_id'])
    if state.get('flash_id') != job.id:
        raise RuntimeError('烧录编号回读不一致。')
    return state


def refresh_pairing(previous, state):
    """A renamed board keeps its archive; refresh only a pairing matching the old ID."""
    from device_lab import SerialLink, CONFIG
    from private_storage import write_json
    if not CONFIG.is_file():
        return False
    config = json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    old_id = config.get('device_id') or config.get('state',{}).get('device_id')
    if not previous.get('device_id') or old_id != previous['device_id']:
        return False
    link = SerialLink(state['serial_port'])
    try:
        setup = link.exchange({'cmd':'setup'})
    finally:
        link.close()
    config.update(setup, device_id=state['device_id'], state=state)
    write_json(CONFIG, config)
    return True


def _flash(args, job):
    resume = False
    state = {}
    try:
        job.update(full_erase=bool(args.factory), mode='factory' if args.factory else 'update')
        manifest, pairs = validate_images(args.images)
        job.update(firmware=manifest['firmware'], written_images=manifest['images'],
                   manifest_sha256=hashlib.sha256((args.images/'FLASH_MANIFEST.json').read_bytes()).hexdigest())
        if importlib.util.find_spec('serial') is None or importlib.util.find_spec('esptool') is None:
            raise RuntimeError('烧录依赖缺失，请使用完整 Windows 软件包。')
        from serial.tools.list_ports import comports
        port = select_port(list(comports()), args.port)
        job.update(port=port)
        resume = pause_collector(port)
        previous = capture_existing(port)
        job.update(previous_device_id=previous.get('device_id'), phase='connect')
        job.message('准备烧录：'+port+' → '+manifest['firmware'])
        job.message('本次独立编号：'+job.id)
        job.message('正在自动连接。失败时：按住 BOOT → 点按 RST → 松开 BOOT 后重试。')
        base = ['--chip','esp32c3','--port',port,'--baud',str(args.baud)]
        probe = run_tool(base+['flash_id'], job.logfile)
        if 'Detected flash size: 4MB' not in probe:
            raise RuntimeError('实际 Flash 不是 4MB，本次未写入。')
        mac = re.search(r'MAC: ([0-9a-f:]+)', probe, re.I)
        job.update(chip='esp32c3', mac=mac[1] if mac else None)
        if args.factory:
            job.update(phase='erase')
            job.message('恢复出厂：清除设备配网、校准和板内缓存；电脑历史保留。')
            run_tool(base+['erase_flash'], job.logfile)
        job.update(phase='write')
        run_tool(base+['write_flash','--flash_mode','dio','--flash_freq','80m','--flash_size','4MB']+pairs, job.logfile)
        job.update(write_hash_verified=True, phase='boot')
        job.message('写入校验通过，正在确认启动。如未启动，仅点按 RST。')
        state = boot_status(port, manifest['firmware'], timeout=args.boot_timeout)
        job.update(boot_verified=True, phase='identity')
        state = set_identity(state['serial_port'], job, manifest['firmware'], args.boot_timeout)
        job.update(identity_verified=True, device_id=state['device_id'], port=state['serial_port'],
                   sensor_mode=state.get('sensor_mode'), network_mode=state.get('network_mode'),
                   configuration_url=state.get('configuration_url'),
                   configuration_hotspot=state.get('configuration_hotspot'),
                   factory_profile=state.get('factory_profile'))
        if state.get('configuration_url') != 'http://192.168.4.1/' or not state.get('config_ap_open'):
            raise RuntimeError('启动成功，但固定配置热点未通过回读检查。')
        if args.factory and (state.get('wifi_connected') or state.get('sensor_mode') != 'simulation'
                             or state.get('physical_outputs_enabled')
                             or state.get('factory_profile') != 'safe-manual-v1'):
            raise RuntimeError('恢复出厂后的默认状态检查未通过。')
        job.update(pairing_refreshed=refresh_pairing(previous,state))
        job.update(status='success', phase='done', finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
        job.message('烧录成功：'+state['device_id'])
        job.message('连接热点 '+state['device_id']+'，浏览器打开 http://192.168.4.1/')
        return job.report
    except Exception as error:
        job.message('失败：'+str(error))
        job.update(status='failed', error=str(error), finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
        return job.report
    finally:
        if resume:
            try:
                from device_transport import save_connection
                from control_panel import collector_start, WORK
                save_connection(WORK/'connection-private.json','usb',port=state.get('serial_port',job.report['port']))
                collector_start()
                job.update(collector_restored=True)
            except Exception:
                job.message('采集服务未恢复，请双击 AI_Doll.cmd 检查连接。')
                job.update(collector_restored=False)


def flash(args, job=None):
    from service_lifecycle import ServiceLease, ServiceAlreadyRunning
    job = job or FlashJob()
    try:
        with ServiceLease(ROOT/'build/flash-active.lock'):
            return _flash(args,job)
    except ServiceAlreadyRunning:
        job.message('已有烧录任务正在运行，请等待完成。')
        job.update(status='failed',error='已有烧录任务正在运行，请等待完成。')
        return job.report


def main():
    parser = argparse.ArgumentParser(description='ESP32-C3 快速烧录：自动串口、镜像校验、写入校验、启动检查。')
    parser.add_argument('--port')
    parser.add_argument('--baud', type=int, choices=(115200, 230400, 460800, 921600), default=460800)
    parser.add_argument('--images', type=Path, default=ROOT/'firmware/prebuilt')
    parser.add_argument('--check', action='store_true', help='只校验镜像，不访问开发板')
    parser.add_argument('--list-ports', action='store_true')
    parser.add_argument('--factory', action='store_true', help='明确清空设备设置及板内缓存，重新初始化')
    parser.add_argument('--boot-timeout', type=int, default=180,
                        help='写入后等待应用启动的秒数，默认180秒，便于人工单按RST')
    args = parser.parse_args()
    if not 5 <= args.boot_timeout <= 600:
        raise ValueError('启动等待时间应为 5～600 秒。')
    if args.check:
        manifest, _ = validate_images(args.images)
        print('四个镜像和地址校验通过：' + manifest['firmware']); return
    if args.list_ports:
        from serial.tools.list_ports import comports
        ports = list(comports())
        for port in ports: print(port.device + ' · ' + port.description)
        return
    job = FlashJob()
    report = flash(args,job)
    print('日志和结果：'+str(job.folder))
    return 0 if report['status']=='success' else 1


if __name__ == '__main__':
    try: sys.exit(main() or 0)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print('失败：'+str(error), file=sys.stderr); sys.exit(1)
