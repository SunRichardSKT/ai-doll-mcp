# 项目目录与交付文件规则

> [完整文档目录](../README.md) · [开发与打包](DEVELOPER_GUIDE.md)

## 源码仓库保留什么

| 位置 | 内容 |
| --- | --- |
| 根目录三个 CMD | 烧录、电脑 MCP、本机接收三条启动入口 |
| firmware/src/ | 固件、设备网页、采样、OTA 和直传源码 |
| firmware/prebuilt/ | 当前可烧录的四个镜像与校验清单 |
| tools/ | 程序、维护入口和对应测试 |
| docs/start/、daily/、integrations/ | 人类使用教程 |
| docs/developers/ | 编译、接口和扩展资料 |
| docs/ai/ | AI 安装、调用和硬件验收规则 |
| docs/reports/ | 当前验证范围与历史分阶段证据 |
| docs/images/ | 实际运行截图，个人信息已遮挡 |
| hardware/rev-v2/ | 原生工程、采购 BOM、原制造文件和必要核对证据 |
| deploy/、templates/ | Linux 部署及公共接入模板 |
| python/ | 运行环境的说明、版本与校验元数据 |
| delivery/ | 下载入口与整包校验清单 |

## 清理的内容

管理中心指南合并进日常指南；无线恢复合并进配网指南，避免重复维护同一操作。历史验收报告移动到 reports，不混入入门步骤。

原安装/启停 Secure 的四个重复 CMD 包装入口移除，统一从根目录 AI_Doll.cmd 的管理页面操作；对应维护脚本和明确有用途的远程兼容入口保留。

`channel_editor_asset.h`、`ota_manager_asset.h` 和 `device_page_asset.h` 是由网页源文件生成的编译产物，构建前由 `embed_channel_editor.py` 生成，不再重复提交或放入源码交付包。四个预编译镜像保留，因为新手不需要编译。

完整 Windows ZIP、Linux TAR 与 PCB ZIP 统一存入 **GitHub Releases**。源码仓库移除重复的大型交付包，delivery 只保留下载入口和哈希清单；旧版本可在历史 Release 或 Git 历史追溯，不通过强推改写历史。

2026-10-23本机整理：`delivery/`只保留当前候选与当前硬件包，删除重复旧安装包、旧原型交付物和旧服务器包校验副本；旧的公开源码导出副本、下载缓存与Python缓存也清除。根目录移除 `Start_Operit_Demo.cmd`、`Start_Operit_Prototype.cmd`，保留三条正式启动入口。开发原型中仍被SDK回归测试引用的模块、诊断示例与历史验收说明继续保留，避免把依赖误当垃圾删除。

本机用户CSV审阅表及其修改记录保留在 `build/copy-review/` 与本次维护记录中，不进入公共包；设备配置、个人数据库、校准和未提交的旧工作副本不作清理目标。

测试、原 Gerber、BOM、DRC 与采购核对不是无用文件。清理不以“没在日常点击”作为删除依据，不改用户已经下单的铜图形。

## 本机数据放哪里

build/ 保存个人配对、SQLite 历史、日志、烧录结果和测试证据；.tools/、.venv/、.pio/ 为本机环境。它们均不提交、不打入公共包。清理 GitHub 不会删除用户电脑历史。

公共包使用明确允许列表，验证逐文件 SHA-256、文档链接和已知本机密钥排除。新增运行依赖后，应同时更新包允许列表与验证入口，不能依赖开发电脑才有的文件。

2.19 起 `src/ai_doll/core/` 是共享策略实现，`clients/operit/` 是手机工具包源码。旧 `tools/interaction_bridge.py` 等路径只保留导入兼容；完整包必须保留 `src/`，不要单独复制几个工具脚本升级。
