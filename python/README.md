# 随包 Python 运行环境

Windows x64 CPython 3.14.8 与固定 MCP 依赖。双击上一级的 AI_Doll.cmd 即可使用；无需安装到系统或修改 PATH。请保留完整 python 文件夹。

CPython 来源：https://www.python.org/downloads/release/python-3148/ 。官方压缩包 SHA-256 与全部依赖版本和 wheel 校验值见 RUNTIME.json。Python 的许可见 LICENSE.txt；依赖的各自许可保留于 Lib/site-packages/*.dist-info/licenses 或 METADATA。

公共 GitHub 源码仅保留运行环境说明、许可和校验信息。完整二进制运行环境在交付 ZIP 内；开发者使用 tools/build_portable_python.py 和 requirements-windows-runtime.lock 从官方 CPython/PyPI 构建。
