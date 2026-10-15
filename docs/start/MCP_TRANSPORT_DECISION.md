# 先选一种连接方式

> 按本页步骤操作即可；无需读完开发者资料。 [全部目录](../README.md)


你不需要同时安装所有入口。按自己正在使用的 AI 选择下面一条。

| 你的目标 | 选择 | 每天保持运行 |
| --- | --- | --- |
| ChatGPT 原聊天读取娃娃记录 | [Windows 安装](AI_INSTALL.md)，再接 [Secure 隧道](../integrations/SECURE_MCP.md) | 娃娃、电脑采集、隧道 |
| 本机支持 MCP 的 AI 客户端 | [Windows 安装](AI_INSTALL.md)，复制本机配置 | 娃娃、电脑采集 |
| 自己的聊天应用，先本机测试 | [本机接收服务](../integrations/SERVER_QUICKSTART.md) | 娃娃、接收电脑 |
| 自己有远程 Linux 服务器，电脑不常开 | [远程部署](../integrations/REMOTE_SERVER_SETUP.md) | 娃娃、服务器 |
| Operit，设备直传自己的服务器 | [Operit 服务器模式](../integrations/OPERIT_NO_PC.md#有自己的服务器) | 娃娃、服务器、Operit |
| Operit，只有安卓手机与家庭 Wi-Fi | [Operit 手机直连](../integrations/OPERIT_NO_PC.md#只有安卓手机没有电脑和服务器) | 娃娃、同一家庭网络的 Operit |

MCP 是给 AI 读取工具的接口，不是新模型。设备设置页是修改网络和传感器的页面，不是 MCP 连接地址。GitHub 只提供下载和说明，不是运行中的服务。

电脑采集与设备直传分别保存历史。保持一个主消费通路，切回电脑采集前先关闭直传。

只想先测试硬件时，直接 [烧录](QUICK_FLASH.md)、[打开固定设置页](../daily/WIFI_CONNECTION.md)、[校准传感器](../daily/CALIBRATION_AND_DAILY_MODE.md)，暂时不用设置 AI。
