# 远程服务器快捷部署

更新：2026-10-11，服务端交付 v2.16.1。此入口运行在远程 Linux 服务器上；Windows 内置 Python 用于电脑端，不需要上传到 Linux。

## 你先准备两件事

1. 一台可 SSH 登录的 Linux 服务器。Ubuntu / Debian 可以自动安装缺少的 Docker；其他 Linux 先装好 Docker Engine 与 Compose。
2. 一个域名，例如 `doll.your-domain.com`，将 A 记录指向服务器公网 IPv4；如有 AAAA，必须指向这台服务器可用的 IPv6。在云安全组允许 TCP 80 / 443。已有网站占用这两个端口时，使用原反向代理接入方式，见 [部署说明](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/DIRECT_SERVER.md)。

域名、服务器和云账号仍由你选择。安装器不会注册娃娃账号，不要求模型密钥，也不更改你的原 AI 聊天。

## 推荐：下载一个入口，填写域名

在服务器的 SSH 终端运行以下命令，把域名换成你的真实域名：

```bash
curl -fsSL https://raw.githubusercontent.com/SunRichardSKT/ai-doll-mcp/main/Install_Server.sh -o Install_Server.sh
sudo bash Install_Server.sh --domain doll.your-domain.com
```

若命令中不填写 `--domain`，入口会询问域名。若服务器没有 curl，可在电脑上下载 `Install_Server.sh` 后上传到服务器，再运行第二行；安装器会准备缺少的 curl。

安装器会完成：

1. 验证域名格式、DNS 解析和安装目录。
2. 复用已有 Docker；未安装时从 Docker 官方 apt 源安装 Docker / Compose，不卸载已有容器运行环境。
3. 下载小型 Linux 服务包并核对 SHA-256，不下载 Windows Python 或 PCB 文件。
4. 生成 `.env`、持久数据卷、服务启动配置和管理命令。
5. 构建接收服务，启动 Caddy，自动申请和续期 HTTPS 证书。
6. 校验证书及管理接口的本安装身份，通过后才显示部署成功和管理链接。

Docker 安装遵循 [Ubuntu 官方说明](https://docs.docker.com/engine/install/ubuntu/)与 [Debian 官方说明](https://docs.docker.com/engine/install/debian/)。Caddy 的自动 HTTPS 需要正确 DNS 与可达的 80 / 443，见 [官方说明](https://caddyserver.com/docs/automatic-https)。

## 也可上传小型服务包

从交付目录下载 `AI_Doll_Server_v2.16.1.tar.gz` 与对应 `.sha256` 文件，上传到服务器同一目录：

```bash
sha256sum -c AI_Doll_Server_v2.16.1.tar.gz.sha256
mkdir ai-doll-server
tar -xzf AI_Doll_Server_v2.16.1.tar.gz -C ai-doll-server
sudo bash ai-doll-server/Install_Server.sh --domain doll.your-domain.com
```

这个包只有服务代码、部署配置和指南；Python 及服务依赖由容器准备。完整源码 / Windows 包中也提供同一个根目录安装入口。

## 接入设备

安装完成会显示形如 `https://你的域名/#connect=…` 的完整管理链接。打开后自动进入管理界面，不需要手动输入娃娃账号密码；可用 `sudo ai-doll-server link` 再次取得链接。

1. 管理页点击“生成设备连接配置”，复制生成的 JSON。
2. 手机进入 ESP32 设置页；首次配网时长按 BOOT，连接娃娃热点，访问 `http://192.168.4.1/`。联网后也可使用设备的局域网 IP。
3. 在“直连服务器”粘贴配置，点击填入并保存；家庭 Wi-Fi 使用 2.4 GHz。
4. 回到服务器管理页刷新。收到设备实际上传后才显示在线；此后设备可独立供电，不需要电脑中转。

服务器不能直接访问家中 ESP32 的内网 IP，因此首次设备配置通过手机保存；配好后设备主动向服务器上传。进入设备下方的链接可设置通道、部位、人设、偏好，查看日志和模拟输入。未接传感器时用 simulation，物理输出关闭。

此服务是设备直传与原应用事件接口。自建前端可接事件并调用原模型；普通 Chat 的 MCP / Secure 隧道沿用已有接入。部署成功不等于已经实现普通 Chat 空闲唤醒。

## 日常管理与更新

```bash
sudo ai-doll-server status    # 实际服务与 HTTPS 检查
sudo ai-doll-server stop      # 停止本项目容器，保留历史和证书
sudo ai-doll-server start     # 启动并再次验证 HTTPS
sudo ai-doll-server restart   # 重启本项目
sudo ai-doll-server link      # 取得自动连接的管理链接
sudo ai-doll-server logs      # 查看应用和证书日志
```

默认安装到 `/opt/ai-doll-mcp`，默认 Compose 项目为 `ai-doll-server`。Docker 与本项目设置为重启后恢复。数据、设备绑定和证书保存在持久卷，停止或重装代码时不删除。更新时重新下载新版 `Install_Server.sh` 并运行原安装命令；已有域名和管理链接保持，若需改域名显式填写新域名并重新保存设备配置。

已有手工 Compose 部署时，先确认原项目名、卷与备份。新安装目录中可用 `--project 原项目名` 明确复用仅含 doll / https 的项目和数据卷；安装器不会自动接管默认名称下的已有容器，也不会覆盖陌生的非空目录。不要用 `docker compose down -v` 更新。

只预览安装流程，可加 `--dry-run`，不会安装依赖或启动服务。

## 出错后怎么办

- **域名未解析**：补齐 DNS 后重新运行。
- **Docker 未运行 / 插件缺少**：修复已有 Docker / Compose 后重试；安装器不会重装现有引擎。
- **80 / 443 被占用**：继续使用原网站的反向代理，或使用独立服务器；安装器不停止其他网站。
- **HTTPS 检查超时**：服务与数据保留，检查 A / AAAA、云安全组、80 / 443 和 `logs`。修复后执行 `sudo ai-doll-server start`；不会把证书失败报告成成功。
- **设备未上线**：检查开发板 Wi-Fi、服务器配置与供电。已存历史仍可查询。

当前没有你的实际公网服务器与域名；本轮提供并测试部署代码，不把本机或替身测试当作真实公网证书验收。
