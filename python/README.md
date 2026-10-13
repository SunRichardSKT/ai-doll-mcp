# 随包 Python：完整包无需另装

Windows 完整软件包在此目录提供 **x64 CPython 3.14.8** 和固定 MCP / 网络 / 串口依赖。返回软件根目录双击 `AI_Doll.cmd` 或 `AI_Doll_Server.cmd` 即可；保留整个目录，不用修改 PATH。

## 为什么源码仓库里没有 python.exe

GitHub 源码只保存说明、许可和校验元数据，完整二进制位于 [交付软件 ZIP](https://github.com/SunRichardSKT/ai-doll-mcp/blob/main/delivery/README.md)。下载源码 ZIP 不等于下载了完整运行包。

## 来源和校验

CPython 官方来源与压缩包 SHA-256、wheel 摘要和实际依赖版本在 [RUNTIME.json](RUNTIME.json)。Python 许可见 [LICENSE.txt](LICENSE.txt)，依赖许可保留在完整包各 dist-info 的 licenses / METADATA 中。

开发者使用 `tools/build_portable_python.py` 与 `requirements-windows-runtime.lock` 重建，不复制开发虚拟环境。编译固件另需 PlatformIO，见 [开发指南](../docs/developers/DEVELOPER_GUIDE.md)。启动问题见 [故障排查](../docs/TROUBLESHOOTING.md)。
