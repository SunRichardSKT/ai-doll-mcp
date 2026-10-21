# 远程服务器：快速安装

> 按本页步骤操作即可；无需读完开发者资料。 [全部目录](../README.md)


适用于你自己的 Linux 服务器。首次选择方式可先看 [连接方式](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/start/MCP_TRANSPORT_DECISION.md)。电脑端的 Windows 启动程序和内置 Python 不需要上传到服务器。

本页按 [2.24.1 预发布版](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.24.1)编写，安装入口、Linux 包与 Operit 手机包使用同一发布版。2.21 旧一键安装器存在复制清单缺项，新部署应使用本页修复版；已有稳定部署的保留与升级边界见[稳定版校正版入口](../start/STABLE_2_21.md)。

整个流程是：**准备服务器和域名 → 运行安装入口 → 打开管理页面 → 手机连接娃娃 → 将 MCP 地址接入原聊天**。小型包同时包含接收服务和 MCP，原前端与 MCP 可以部署在同一台服务器。

这条路线需要已有的 Linux 服务器和域名。没有服务器也能先用 Windows 本机方式测试，不需要为了试按压就购买服务器。

Operit 用户部署后可直接在服务器管理页下载手机工具包与设备连接文件，电脑无需运行。仅安卓手机且无服务器时，可改用家庭局域网直连，见 [Operit 免电脑指南](OPERIT_NO_PC.md)。

## 1. 准备服务器和域名

- 一台可以通过 SSH 登录的 Ubuntu / Debian 服务器。安装入口会自动准备缺少的 Docker 和 Compose。
- 一个域名，例如 `doll.your-domain.com`。在域名服务商处添加 A 记录，指向服务器公网 IPv4。若有 AAAA 记录，也必须指向这台服务器可用的 IPv6。
- 在云服务商的安全组中允许 TCP **80、443**；服务器防火墙也应允许这两个端口。

首次安装推荐使用没有其他网站的服务器。已有网站占用 80 / 443 时，按 [已有反向代理的部署说明](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/developers/DIRECT_SERVER.md)接入，安装入口不会停止其他网站。

## 2. 在服务器运行安装入口

登录服务器，在 SSH 终端复制这两行：

```bash
curl -fsSL https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/Install_Server.sh -o Install_Server.sh
sudo bash Install_Server.sh
```

按提示填写域名。也可以直接粘贴 `https://你的域名/`，默认 HTTPS 端口为 443。填错后会提示重新填写。

接下来等待四步完成：环境检查、下载并校验代码、启动服务、验证 HTTPS。无需自行安装 Python、编辑 Docker 配置或申请证书。只有证书和本安装的管理接口都验证通过，才会显示部署成功。

如果服务器没有 `curl`，可在其他设备下载[本版 Install_Server.sh](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.24.1/Install_Server.sh)，上传后运行第二行；安装入口会准备缺少的下载工具。

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
2. 手机连接娃娃热点，打开固定页 `http://192.168.4.1/`；已配家庭网络后也保留此入口。在家庭 Wi-Fi 下则使用设备实际局域网 IP。家庭网络需要 2.4 GHz。
3. 在 **直连服务器** 设置中粘贴配置，填入并保存。
4. 回到服务器管理页刷新，等待设备实际上传后显示 **在线**。

服务器无法直接访问家中开发板的内网 IP，因此首次通过手机保存配置。之后 ESP32 主动上传，电脑无需常开，开发板可以独立供电。只有实际装好的端口才设为“已接入”；未安装的关闭，模拟测试另选一个端口，物理输出保持关闭。

## 5. 检查安装是否成功

- 管理页可以打开。
- 娃娃显示在线。
- 按压实际安装的传感器后，历史出现对应开始／释放记录并标明真实来源。没有传感器时按[模拟测试分支](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/integrations/CHAT_MCP.md#可选没有传感器时做模拟测试)操作，模拟记录不能作为实体硬件验收。

## 6. 将 MCP 接入原聊天

在管理页的已配对设备下点击 **复制 MCP 地址**。在原聊天客户端添加 Streamable HTTP MCP，填入完整地址，选择无需身份验证。自建聊天后端可以在同一台服务器使用它，不需要另外启动电脑采集器。

MCP 和接收服务共用数据库，默认提供 19 个状态、历史与互动工具。实际调用 `get_installation_status` 和 `doll_get_status`，取得两个新的 `verification.call_id`；再查询刚才的记录并开始 60 秒互动，保留真实／模拟来源。设备离线时仍能查询已存历史，返回最后同步时间和离线信息。

管理页地址不能替代 MCP 地址。已有网站或需要后端本机连接时，见 [同机部署与反向代理](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/developers/DIRECT_SERVER.md#同一台服务器部署原聊天与-mcp)。按压后主动向原聊天发送回复还需原应用监听事件并调用模型；普通 Chat 空闲主动唤醒不作为本轮承诺。

## 日常操作

| 要做什么 | 在服务器执行 |
| --- | --- |
| 检查服务与 HTTPS | `sudo ai-doll-server status` |
| 重新取得管理链接 | `sudo ai-doll-server link` |
| 重启服务 | `sudo ai-doll-server restart` |
| 停止 / 启动 | `sudo ai-doll-server stop` / `sudo ai-doll-server start` |
| 查看错误日志 | `sudo ai-doll-server logs` |
| 更新代码 | 从目标 Release 下载同版安装入口，再运行 `sudo bash Install_Server.sh` |

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

也可从 [2.24.1 Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.24.1)下载 `AI_Doll_Server_v2.24.1.tar.gz` 与对应 `.sha256`，上传到服务器同一目录。校验值使用该 Release 的文件，不能拿其他版本或滚动主分支清单代替：

```bash
sha256sum -c AI_Doll_Server_v2.24.1.tar.gz.sha256
mkdir ai-doll-server
tar -xzf AI_Doll_Server_v2.24.1.tar.gz -C ai-doll-server
sudo bash ai-doll-server/Install_Server.sh
```

小型包仅包含 Linux 服务代码、配置和指南，运行依赖由容器准备，不需要 Windows 完整包或 PCB 文件。

已有手工 Compose 部署可使用 `--install-dir 原绝对目录 --project 原项目名`，经核对后复用原数据卷。其他 Linux 发行版需要先准备 Docker Engine 与 Compose，再运行安装入口。

安装使用 [Docker 官方 Ubuntu](https://docs.docker.com/engine/install/ubuntu/) / [Debian](https://docs.docker.com/engine/install/debian/)软件源和 [Caddy 自动 HTTPS](https://caddyserver.com/docs/automatic-https)。已完成本机隔离 Linux 环境的安装与设备上传验证；实际公网服务器、DNS 和公网证书需在你的服务器上验证。见 [验收范围](../reports/SIMPLE_SETUP_ACCEPTANCE.md)。
