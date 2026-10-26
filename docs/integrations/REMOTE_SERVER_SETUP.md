# 远程服务器：快速安装

> 按本页步骤操作即可；无需读完开发者资料。 [全部目录](../README.md)


适用于你自己的 Linux 服务器。首次选择方式可先看 [连接方式](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/start/MCP_TRANSPORT_DECISION.md)。电脑端的 Windows 启动程序和内置 Python 不需要上传到服务器。

本页按 **2.25.2预发布**编写，安装入口、Linux包与Operit手机包从[同一Release](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.25.2)下载。新部署和升级均推荐从完整包解压目录运行安装器；同版独立脚本也可下载配套服务包。

2.25.3为尚未发布的[本地维护候选](../reports/RELEASE_2_25_3.md)。持有完整候选包时，从该包解压目录运行安装器，并搭配同批次手机包；不要将候选安装器单独用于下载尚未发布的Release。

上一修订版[2.24.1](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.24.1)按其固定版本教程操作。2.21旧安装器有复制清单缺项，保留与升级边界见[稳定版入口](../start/STABLE_2_21.md)。

整个流程是：**准备服务器和域名 → 运行安装入口 → 打开管理页面 → 手机连接娃娃 → 将 MCP 地址接入原聊天**。小型包同时包含接收服务和 MCP，原前端与 MCP 可以部署在同一台服务器。

这条路线需要已有的 Linux 服务器和域名。没有服务器也能先用 Windows 本机方式测试，不需要为了试按压就购买服务器。

Operit 用户部署后可直接在服务器管理页下载手机工具包与设备连接文件，电脑无需运行。仅安卓手机且无服务器时，可改用家庭局域网直连，见 [Operit 免电脑指南](OPERIT_NO_PC.md)。

## 1. 准备服务器和域名

- 一台可以通过 SSH 登录的 Ubuntu / Debian 服务器。安装入口会自动准备缺少的 Docker 和 Compose。
- 一个域名，例如 `doll.your-domain.com`。在域名服务商处添加 A 记录，指向服务器公网 IPv4。若有 AAAA 记录，也必须指向这台服务器可用的 IPv6。
- 在云服务商的安全组中允许 TCP **80、443**；服务器防火墙也应允许这两个端口。

首次安装推荐使用没有其他网站的服务器。已有网站占用 80 / 443 时，按 [已有反向代理的部署说明](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/developers/DIRECT_SERVER.md)接入，安装入口不会停止其他网站。

## 2. 上传并运行发布包

将本机 `delivery/AI_Doll_Server_v2.25.2.tar.gz` 与同目录的 `.sha256` 文件上传到服务器同一目录。在 SSH 终端校验、解压，然后运行**包内**入口：

```bash
sha256sum -c AI_Doll_Server_v2.25.2.tar.gz.sha256
mkdir ai-doll-server-2.25.2
tar -xzf AI_Doll_Server_v2.25.2.tar.gz -C ai-doll-server-2.25.2
cd ai-doll-server-2.25.2
sudo bash Install_Server.sh
```

按提示填写域名。也可以直接粘贴 `https://你的域名/`，默认 HTTPS 端口为 443。填错后会提示重新填写。

接下来等待环境检查、包内文件检查与安装、启动服务和 HTTPS 验证。无需自行安装 Python、编辑 Docker 配置或申请证书。只有证书和本安装的管理接口都验证通过，才会显示部署成功。

完整解压时保留 `src/`、`tools/`、`clients/`、`delivery/` 和 `deploy/`。也可单独运行本版Release的`Install_Server.sh`，它会下载并校验配套Linux包。旧安装目录的入口先核对目标版本，不把旧脚本下载的旧包当作2.25。

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
2. 手机连接娃娃热点，打开固定页 `http://192.168.4.1/`；2.13.1起首次热点最长10分钟，新配网成功后约90秒关闭；需要时运行中长按BOOT约3秒重新开启。在家庭Wi-Fi下通过已配对客户端的设置链接或网页登录访问设备。家庭网络需要 2.4 GHz。
3. 在 **直连服务器** 设置中粘贴配置，填入并保存。
4. 回到服务器管理页刷新，等待设备实际上传后显示 **在线**。

服务器无法直接访问家中开发板的内网 IP，因此首次通过手机保存配置。之后 ESP32 主动上传，电脑无需常开，开发板可以独立供电。只有实际装好的端口才设为“已接入”；未安装的关闭，模拟测试另选一个端口，物理输出保持关闭。

Operit 连接则从服务器管理页的对应设备取得：下载连接文件、复制连接码或显示临时二维码。手机导入后核对持久服务器实例标识、配对标识和已知设备身份；这些标识保存在服务器数据中，不随服务进程重启改变。二维码不需要贴在设备上，同一手机优先文件或连接码。设备家庭 IP 改变不需要修改手机的服务器连接。

设备开启直传后由服务器路径归档；不要同时将手机直连当作主归档端。新固件的有限租约协调确认缓存，手机连接服务器查询其数据库；这与仅手机模式的“自动同步记录”开关不同。配套协议与兼容范围见 [离线记录](../daily/OFFLINE_RECORDS.md)。

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
| 更新到本地 2.25 候选 | 从新候选包解压目录运行 `sudo bash Install_Server.sh`，复用原目录和项目；不是运行已安装的更新入口 |

默认目录为 `/opt/ai-doll-mcp`。更新会复用域名、管理连接、设备绑定、持久实例标识和历史。已有自定义目录／项目时必须传入原来的 `--install-dir` 与 `--project`，不另建空数据卷。应用及证书使用持久数据卷；新安装的 Docker 启用开机启动，容器随引擎恢复。已有 Docker 需确认其开机启动设置。不要用 `docker compose down -v` 更新，因为它会删除数据卷。

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

已有手工 Compose 部署可在**新候选包解压目录**中指定原目录／项目；先核对其确为本项目：

```bash
sudo bash Install_Server.sh --install-dir /原安装绝对目录 --project 原项目名
```

小型包包含 Linux 服务代码、共享核心、手机工具包、二维码资源及必要指南，运行依赖由容器准备，不需要 Windows 完整包或 PCB 文件。候选使用同批次本地校验文件；已发布版本使用其固定 Release 校验，不混用版本或滚动主分支清单。

其他 Linux 发行版需要先准备 Docker Engine 与 Compose，再运行安装入口。

安装使用 [Docker 官方 Ubuntu](https://docs.docker.com/engine/install/ubuntu/) / [Debian](https://docs.docker.com/engine/install/debian/)软件源和 [Caddy 自动 HTTPS](https://caddyserver.com/docs/automatic-https)。历史版本的隔离 Linux 安装与设备上传证据见 [旧验收范围](../reports/SIMPLE_SETUP_ACCEPTANCE.md)；本版软件与打包检查见 [2.25 候选报告](../reports/RELEASE_2_25_1.md)。这些结果不能替代当前公网服务器、DNS、证书或目标手机验收。
