# 2.21 稳定版：下载、校验与使用边界

本页是 2.21.0 的校正版入口。GitHub 稳定版保留为 2.21.0；[2.25.0预发布](https://github.com/SunRichardSKT/ai-doll-mcp/releases/tag/v2.25.0)提供新的 Operit 队列、常开与安装修复。两者不要交叉替换脚本、服务端或手机包。

旧 tag 下的教程保留历史原文，其中仍有 2.20 包名和指向主分支的下载／校验链接。**下载与校验以本页固定到 2.21.0 Release 的链接为准**；不要按那些旧包名或滚动链接重新安装。

## 固定下载与校验

| 文件 | 用途 |
| --- | --- |
| [AI_Doll_Code_v2.21.0.zip](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Code_v2.21.0.zip) | Windows 完整包，内置 Python |
| [AI_Doll_Operit.toolpkg](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Operit.toolpkg) | 2.21.0 手机包，也在该 Windows／Linux 包内 |
| [AI_Doll_Server_v2.21.0.tar.gz](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/AI_Doll_Server_v2.21.0.tar.gz) | 历史 Linux 服务文件，供已有部署维护；新部署见下方说明 |
| [SHA256SUMS.txt](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/SHA256SUMS.txt) | 本版全部下载文件的固定哈希 |
| [DELIVERY_MANIFEST.json](https://github.com/SunRichardSKT/ai-doll-mcp/releases/download/v2.21.0/DELIVERY_MANIFEST.json) | 本版交付清单 |

先下载文件，再使用同一 Release 的哈希核对。Windows 可运行 `Get-FileHash .\AI_Doll_Code_v2.21.0.zip -Algorithm SHA256`；手机包同名但版本不同，不能拿最新交付目录里的哈希校验旧包。

## Windows 与原聊天

1. 完整解压 2.21.0 Windows 包，保留 `python/`、`src/`、`tools/`、`clients/` 和 `delivery/`，双击 `AI_Doll.cmd`。
2. 给设备供电、连接家庭 Wi-Fi，在管理中心配对实际设备。已有板不因电脑文档更新而重新烧录。
3. 在管理中心配置原 MCP 客户端。普通 Chat 使用 Secure 隧道；添加后实际调用状态工具，再查询新历史与限时互动。

本版内含固件 2.10.0，电脑 STDIO 为 51 个工具；HTTP 状态／历史／互动配置为 2／9／19。它不提供新版端口三态界面，使用本版实际页面核对真实采样与重启恢复，不照搬 2.12.1 固件的按钮位置。

## Operit

使用上方固定的 2.21.0 手机包，选择该版本支持的连接方式并绑定已有聊天，按其面板完成连接自检后选择 1 分钟或 15 分钟互动。此版没有 2.24 的常开续接、完整批次接口和独立历史页面；新版指南的“无需发送诊断”流程也不追溯改变旧代码。

不要只把 2.24.1 手机包接到 2.21 服务端。希望使用新流程时，同时升级电脑／服务器与手机包；仅手机直连只升级工具包。操作见 [当前 Operit 指南](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/integrations/OPERIT_SETUP.md)。

## Linux 部署

2.21 的旧一键安装器存在安装复制清单缺项：可能遗漏容器构建所需的 `src/` 和手机工具包。**新部署与需要修复的安装使用 [当前安装入口](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/integrations/REMOTE_SERVER_SETUP.md)**，本页不再将旧安装器作为可用的新装主流程。

已有正常运行的 2.21 部署可以保留，维护时保持原部署目录、Compose 项目名和数据卷，不用删除数据卷重装。需要升级时使用完整2.25.0包和同版手机包，保留原数据；不要单独用新安装脚本覆盖旧目录后假定仍是稳定版。

## 验收边界

本版当时的检查与待验收项见 [2.21 发布记录](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/docs/reports/RELEASE_2_21.md)。旧版成功不证明新手机后台、当前固件、其他传感器或公网部署已经通过；各次安装仍需核对实际身份、版本与同步状态。
