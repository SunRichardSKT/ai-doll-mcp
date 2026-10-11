# 远程服务器：快速安装

适用于你自己的 Linux 服务器。首次选择方式可先看 [连接方式](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/MCP_TRANSPORT_DECISION.md)。电脑端的 Windows 启动程序和内置 Python 不需要上传到服务器。

整个流程是：**准备服务器和域名 → 运行安装入口 → 打开管理页面 → 手机连接娃娃**。

## 1. 准备服务器和域名

- 一台可以通过 SSH 登录的 Ubuntu / Debian 服务器。安装入口会自动准备缺少的 Docker 和 Compose。
- 一个域名，例如 `doll.your-domain.com`。在域名服务商处添加 A 记录，指向服务器公网 IPv4。若有 AAAA 记录，也必须指向这台服务器可用的 IPv6。
- 在云服务商的安全组中允许 TCP **80、443**；服务器防火墙也应允许这两个端口。

首次安装推荐使用没有其他网站的服务器。已有网站占用 80 / 443 时，按 [已有反向代理的部署说明](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/DIRECT_SERVER.md)接入，安装入口不会停止其他网站。

## 2. 在服务器运行安装入口

登录服务器，在 SSH 终端复制这两行：

```bash
curl -fsSL https://raw.githubusercontent.com/SunRichardSKT/ai-doll-mcp/main/Install_Server.sh -o Install_Server.sh
sudo bash Install_Server.sh
```

按提示填写域名。也可以直接粘贴 `https://你的域名/`，默认 HTTPS 端口为 443。填错后会提示重新填写。

接下来等待四步完成：环境检查、下载并校验代码、启动服务、验证 HTTPS。无需自行安装 Python、编辑 Docker 配置或申请证书。只有证书和本安装的管理接口都验证通过，才会显示部署成功。

如果服务器没有 `curl`，可在电脑下载 [Install_Server.sh](https://raw.githubusercontent.com/SunRichardSKT/ai-doll-mcp/main/Install_Server.sh)，上传后运行第二行；安装入口会准备缺少的下载工具。

## 3. 打开管理页面

安装结束会显示完整管理链接，形如：

```text
https://你的域名/#connect=…
```

在浏览器打开显示的完整链接，即可进入管理页面。**不需要创建娃娃账号或填写模型 API 密钥。**

忘记链接时，在服务器运行：

```bash
sudo ai-doll-server link
```

## 4. 用手机连接娃娃

1. 在服务器管理页点击 **生成设备连接配置**，复制生成的配置。
2. 手机打开 ESP32 设置页。首次配网时，运行中的设备长按 **BOOT 约 3 秒**，连接娃娃热点，访问 `http://192.168.4.1/`；已联网时使用设备的局域网 IP。家庭 Wi-Fi 需要 2.4 GHz。
3. 在 **直连服务器** 设置中粘贴配置，填入并保存。
4. 回到服务器管理页刷新，等待设备实际上传后显示 **在线**。

服务器无法直接访问家中开发板的内网 IP，因此首次通过手机保存配置。之后 ESP32 主动上传，电脑无需常开，开发板可以独立供电。未接传感器时保持模拟模式，物理输出关闭。

## 5. 检查安装是否成功

- 管理页可以打开。
- 娃娃显示在线。
- 模拟一次按压后，日志出现新记录，并标记为模拟来源。

这完成的是设备上传、存储和原应用接口的部署。普通 Chat 的 MCP 连接沿用 [Secure MCP 接入指南](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/SECURE_MCP.md)，并不是把管理页地址填入 Chat 即可连接；普通 Chat 空闲主动唤醒也不属于此次部署验收。

## 日常操作

| 要做什么 | 在服务器执行 |
| --- | --- |
| 检查服务与 HTTPS | `sudo ai-doll-server status` |
| 重新取得管理链接 | `sudo ai-doll-server link` |
| 重启服务 | `sudo ai-doll-server restart` |
| 停止 / 启动 | `sudo ai-doll-server stop` / `sudo ai-doll-server start` |
| 查看错误日志 | `sudo ai-doll-server logs` |
| 更新代码 | 重新下载安装入口，再运行 `sudo bash Install_Server.sh` |

默认目录为 `/opt/ai-doll-mcp`。更新会复用域名、管理连接、设备绑定和历史。应用及证书使用持久数据卷；新安装的 Docker 启用开机启动，容器随引擎恢复。已有 Docker 需确认其开机启动设置。不要用 `docker compose down -v` 更新，因为它会删除数据卷。

## 安装卡住时

| 看到什么 | 怎么处理 |
| --- | --- |
| 域名尚未解析 | 检查域名的 A / AAAA 记录，解析生效后重新运行安装入口。 |
| Docker 已安装但未运行 | 启动已有 Docker 后重试；安装入口不会替换现有运行环境。 |
| HTTPS 尚未通过验证 | 检查 DNS、云安全组与防火墙的 80 / 443，运行 `logs` 查看证书错误；修复后执行 `start`。服务和数据保留。 |
| 管理页正常，但设备离线 | 检查娃娃的 Wi-Fi、供电和直连配置；重新保存配置后查看日志。 |
| 目标目录或 Compose 项目已存在 | 确认是否为原项目，按下方高级选项指定原目录 / 项目；不要删除陌生目录或容器。 |

## 高级安装方式

直接指定域名，不出现提问：

```bash
sudo bash Install_Server.sh --domain doll.your-domain.com
```

只预览，不安装依赖或启动服务：

```bash
sudo bash Install_Server.sh --domain doll.your-domain.com --dry-run
```

也可从 [交付目录](https://github.com/SunRichardSKT/ai-doll-mcp/tree/main/delivery)下载 `AI_Doll_Server_v2.16.2.tar.gz` 与对应 `.sha256`，上传到服务器同一目录：

```bash
sha256sum -c AI_Doll_Server_v2.16.2.tar.gz.sha256
mkdir ai-doll-server
tar -xzf AI_Doll_Server_v2.16.2.tar.gz -C ai-doll-server
sudo bash ai-doll-server/Install_Server.sh
```

小型包仅包含 Linux 服务代码、配置和指南，运行依赖由容器准备，不需要 Windows 完整包或 PCB 文件。

已有手工 Compose 部署可使用 `--install-dir 原绝对目录 --project 原项目名`，经核对后复用原数据卷。其他 Linux 发行版需要先准备 Docker Engine 与 Compose，再运行安装入口。

安装使用 [Docker 官方 Ubuntu](https://docs.docker.com/engine/install/ubuntu/) / [Debian](https://docs.docker.com/engine/install/debian/)软件源和 [Caddy 自动 HTTPS](https://caddyserver.com/docs/automatic-https)。已完成本机隔离 Linux 环境的安装与设备上传验证；实际公网服务器、DNS 和公网证书需在你的服务器上验证。见 [验收范围](SIMPLE_SETUP_ACCEPTANCE.md)。
