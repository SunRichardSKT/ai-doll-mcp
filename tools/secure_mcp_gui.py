"""Local setup and lifecycle UI; the user's AI conversation stays in ChatGPT."""
import argparse
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser

import secure_mcp as service

LABELS = {'完整互动（13 个工具）': 'interaction', '只读历史（9 个工具）': 'history',
          '状态验证（2 个工具）': 'status'}


class SetupWindow:
    def __init__(self, folder=service.DEFAULT, autostart=False):
        self.folder, self.busy = Path(folder).resolve(), False
        self.mailbox = queue.Queue()
        self.root = tk.Tk()
        self.root.title('AI Doll · ChatGPT 隧道配置')
        self.root.geometry('740x585')
        self.root.minsize(700, 560)
        self.root.option_add('*Font', ('Microsoft YaHei UI', 10))
        cfg = service.configuration(self.folder)
        self.tunnel = tk.StringVar(value=cfg.get('tunnel_id', ''))
        self.key = tk.StringVar()
        self.profile = tk.StringVar(value=next(label for label, value in LABELS.items()
                                   if value == cfg.get('profile', 'interaction')))
        self.message = tk.StringVar(value='首次保存后，在 ChatGPT 创建自定义 MCP → 隧道，填入隧道 ID。')
        self.gateway = tk.StringVar(value='待检查')
        self.native = tk.StringVar(value='待检查')
        self.device = tk.StringVar(value='使用现有 Wi-Fi 采集与配对；模拟数据保留来源标记。')
        self.last_report = {}
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='在原 ChatGPT 聊天中连接娃娃', font=('Microsoft YaHei UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='配置一次，之后双击 Start_Secure_MCP.cmd 启动。', padding=(0, 8, 0, 16)).pack(anchor='w')
        form = ttk.Frame(frame)
        form.pack(fill='x')
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text='隧道 ID').grid(row=0, column=0, sticky='w', padx=(0, 15), pady=7)
        ttk.Entry(form, textvariable=self.tunnel).grid(row=0, column=1, sticky='ew')
        ttk.Button(form, text='复制 ID', command=self.copy_id).grid(row=0, column=2, padx=(10, 0))
        ttk.Label(form, text='运行 API 密钥').grid(row=1, column=0, sticky='w', pady=7)
        ttk.Entry(form, textvariable=self.key, show='•').grid(row=1, column=1, columnspan=2, sticky='ew')
        hint = '已保存；留空沿用现有密钥。' if cfg.get('runtime_api_key') else '填写 OpenAI Platform 运行密钥，需要隧道 Read / Use 权限。'
        ttk.Label(form, text=hint, foreground='#606873').grid(row=2, column=1, columnspan=2, sticky='w', pady=(0, 6))
        ttk.Label(form, text='工具范围').grid(row=3, column=0, sticky='w', pady=7)
        ttk.Combobox(form, textvariable=self.profile, values=list(LABELS), state='readonly').grid(row=3, column=1, columnspan=2, sticky='ew')
        links = ttk.Frame(frame)
        links.pack(fill='x', pady=(8, 12))
        for label, url in (
                ('创建隧道', 'https://platform.openai.com/settings/organization/tunnels'),
                ('创建运行密钥', 'https://platform.openai.com/settings/organization/api-keys'),
                ('设备设置与模拟按压', 'http://127.0.0.1:8768/companion')):
            ttk.Button(links, text=label, command=lambda url=url: webbrowser.open(url)).pack(side='left', padx=(0, 8))
        health = ttk.LabelFrame(frame, text='实际运行状态', padding=12)
        health.pack(fill='x')
        ttk.Label(health, textvariable=self.gateway).pack(anchor='w', pady=3)
        ttk.Label(health, textvariable=self.native).pack(anchor='w', pady=3)
        ttk.Label(health, textvariable=self.device, wraplength=625, foreground='#606873').pack(anchor='w', pady=3)
        ttk.Label(frame, textvariable=self.message, wraplength=680, foreground='#235b96').pack(fill='x', pady=(12, 8))
        actions = ttk.Frame(frame)
        actions.pack(side='bottom', fill='x')
        self.buttons = []
        for label, action in (('保存并启动', self.save_start), ('检查状态', self.refresh),
                              ('停止连接', lambda: self.perform(lambda: service.stop(self.folder))),
                              ('重置连接地址', lambda: self.perform(lambda: service.reset_address(self.folder)))):
            button = ttk.Button(actions, text=label, command=action)
            button.pack(side='left', padx=(0, 8))
            self.buttons.append(button)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(100, self.drain)
        if autostart and cfg.get('runtime_api_key'):
            self.root.after(250, lambda: self.perform(lambda: service.start(self.folder)))
        else:
            self.root.after(250, self.refresh)
        self.root.after(10000, self.periodic)

    def copy_id(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.tunnel.get().strip())
        self.message.set('已复制隧道 ID。在 ChatGPT 选择“隧道”，首次添加后实际调用两个状态工具。')

    def perform(self, operation, clear_key=False):
        if self.busy:
            return
        self.busy = True
        self.message.set('正在检查本地 MCP 与官方客户端，请稍候……')
        for button in self.buttons:
            button.configure(state='disabled')
        def worker():
            try:
                self.mailbox.put((True, operation(), clear_key))
            except service.SecureError as error:
                self.mailbox.put((False, str(error), False))
            except Exception as error:
                self.mailbox.put((False, '操作失败（' + type(error).__name__ + '），请检查本机配置和网络。', False))
        threading.Thread(target=worker, daemon=True).start()

    def save_start(self):
        tunnel, key, profile = self.tunnel.get(), self.key.get(), LABELS[self.profile.get()]
        def operation():
            service.configure(self.folder, tunnel, key, profile)
            return service.start(self.folder)
        self.perform(operation, clear_key=True)

    def refresh(self):
        self.perform(lambda: service.status(self.folder, verify=True))

    def drain(self):
        try:
            ok, value, clear_key = self.mailbox.get_nowait()
        except queue.Empty:
            self.root.after(100, self.drain)
            return
        self.busy = False
        for button in self.buttons:
            button.configure(state='normal')
        if clear_key:
            self.key.set('')
        if ok:
            self.last_report = value
            self.gateway.set('本地 MCP：' + ('工具发现通过，' + str(value.get('tool_count', 0)) + ' 个工具'
                             if value.get('local_mcp_verified') else '运行中，待验证' if value.get('gateway_running') else '未启动'))
            connected, running = value.get('tunnel_connected'), value.get('runtime_running')
            self.native.set('Secure 隧道：' + ('已观察到成功连接' if connected else '客户端运行中，等待成功连接' if running else '未启动'))
            status_code = value.get('poll', {}).get('http_status')
            if connected:
                self.message.set('可以在 ChatGPT 用“隧道”添加此 ID。工具实际返回 call_id 并与本机匹配后，才算聊天验收通过。')
            elif status_code in (401, 403):
                self.message.set(f'运行密钥或隧道权限未通过（HTTP {status_code}），请检查 Platform 的 Read / Use 权限及账号关联。')
            elif not value.get('key_saved'):
                self.message.set('隧道 ID 已预填。请输入运行 API 密钥，然后点“保存并启动”。')
            elif running:
                self.message.set('客户端正在连接或退避重试；可以继续检查状态，无需重复添加隧道。')
            else:
                self.message.set('连接尚未启动。保存配置后点击“保存并启动”。')
        else:
            self.message.set(value)
        self.root.after(100, self.drain)

    def periodic(self):
        if not self.busy and self.last_report.get('runtime_running'):
            self.refresh()
        self.root.after(10000, self.periodic)

    def close(self):
        if self.busy:
            self.message.set('正在完成当前操作，完成后即可关闭窗口。')
            return
        self.root.destroy()  # The managed services keep running after closing the UI.

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=service.DEFAULT)
    parser.add_argument('--autostart', action='store_true')
    args = parser.parse_args()
    SetupWindow(args.folder, args.autostart).run()
