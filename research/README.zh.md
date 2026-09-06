# BLHeli32Proxy 研究资料索引

本目录是 `BLHeli32Proxy` 项目的研究基础：该项目计划构建一个代理/拦截层，让用户在原厂商
（BLHeli AS，挪威）已完全停止运营的情况下，继续将自己归档的 BLHeli32 测试固件安装到自有的
电调硬件上。项目的实际设计/架构见项目根目录的 `../PLAN.md`，工作规范见 `../AGENTS.md`。

English index: [`README.en.md`](README.en.md).

## 研究方法

所有主要技术资料均来自 [elmagnifico.tech](https://elmagnifico.tech/tags/#BLHeli) 上的中文博客
文章（标签：`BLHeli`、`Crack`、`DSHOT`、`ESC` —— 刻意不涉及该站点其他无关标签，按项目范围要求）。
每篇文章的处理流程：

1. 抓取原始 HTML，提取 `<article>` 正文。
2. 用 `pandoc` 转换为 Markdown → `notes/<文章名>.zh.md`（中文，存档用）。
3. 下载文中每一张嵌入图片 → `images/<文章名>/NN.png`。
4. 翻译为忠实的**技术性**英文笔记（非泛化转述，代码/十六进制原样保留，每张嵌入图片均实际
   打开查看并如实描述其内容）→ `notes/<文章名>.en.md`。**工程工作请阅读此文件**——`.zh.md`
   仅作存档源，不作为工作参考。

用户本地 `BLHeliSuite32xl` 安装包中自带的两份官方 PDF 手册也被提取为纯文本
（`manuals/*.txt`），并且对该二进制文件本身也做了只读检查（`strings`、`file` —— 未执行任何
代码），作为独立的一手资料来源——详见 `notes/BLHeliSuite32xl-local-binary-analysis.en.md`。

`urls.txt` 列出了所有已抓取文章及其日期与原始链接；`image_manifest.tsv` 记录了每张下载图片
对应的原始 URL 与来源文章，按其在文章中出现的顺序排列。

## 研究笔记索引

按对项目实际目标（授权/激活/协议）的相关性排序，而非按文章发布日期。每行链接到英文技术笔记，
并在有意义处附上对应的中文原文。

### 最高优先级——协议、加密与激活机制

| 英文笔记 | 中文原文 | 内容概要 |
|---|---|---|
| [`BLHeli-Uart-Usb-Protocol.en.md`](notes/BLHeli-Uart-Usb-Protocol.en.md) | [中文](notes/BLHeli-Uart-Usb-Protocol.zh.md) | **主协议规范**：连接/保活/断开/读取/写入帧格式、CRC16 校验、完整的字节级实测记录。与真实电调通信应从此文入手。 |
| [`BLHeliSuite32-Reverse.en.md`](notes/BLHeliSuite32-Reverse.en.md) | [中文](notes/BLHeliSuite32-Reverse.zh.md) | 逆向系列（一）：逆向工具链、Delphi 类/调用流程图，以及上位机**自带的调试日志**——独立证实了 `0xEB00` 为激活状态读取、`0xF7AC` 为进一步的设备信息读取。 |
| [`BLHeliSuite32-Reverse2.en.md`](notes/BLHeliSuite32-Reverse2.en.md) | [中文](notes/BLHeliSuite32-Reverse2.zh.md) | 逆向系列（二）：首次找到并破解解密流程——附**可直接改用的 Python 参考解密实现**及正式版 XTEA 密钥。 |
| [`BLHeliSuite32-Reverse3.en.md`](notes/BLHeliSuite32-Reverse3.en.md) | [中文](notes/BLHeliSuite32-Reverse3.zh.md) | 逆向系列（三）：解密后 256 字节配置块的完整逐字节字段布局，以及首次命名的 `ReadDeviceActivationStatus`/`ReadDeviceUUID_Str` 调用。 |
| [`BLHeliSuite32-Reverse4.en.md`](notes/BLHeliSuite32-Reverse4.en.md) | [中文](notes/BLHeliSuite32-Reverse4.zh.md) | 逆向系列（四）：确认加密算法为 **XTEA**，给出正式版与测试版固件各自具体的密钥组，以及 flash 地址作为密钥调制量的发现。 |
| [`BLHeliSuite32-Reverse5.en.md`](notes/BLHeliSuite32-Reverse5.en.md) | [中文](notes/BLHeliSuite32-Reverse5.zh.md) | 逆向系列（五）：停服后的"离线版"上位机——相较前几部分的字段偏移漂移、新增的 `FlashCounter` 字段，并确认应用内确实存在激活密钥界面与联网校验代码路径。 |
| [`BLHeliSuite32xl-local-binary-analysis.en.md`](notes/BLHeliSuite32xl-local-binary-analysis.en.md) | *（无中文原文——基于用户本地文件的原创分析）* | 直接检查用户本地 `BLHeliSuite32xl` Linux 二进制文件与官方手册得到的发现：二进制文件中的厂商激活 API 相关符号，以及官方手册中关于设备端激活强制机制（协议降级为纯 PWM）的说明。 |
| [`BLHeli-END.en.md`](notes/BLHeli-END.en.md) | [中文](notes/BLHeli-END.zh.md) | **BLHeli 停运始末**与授权池商业模式——包含厂商专用工具 `BLHeliSuite32Activator` 激活日志的真实截图（UUID + 剩余次数协议形态）、真实的制裁停运律师函，以及社区/厂商的反应。 |

### 中等优先级——实用协议细节

| 英文笔记 | 中文原文 | 内容概要 |
|---|---|---|
| [`BLH-Uart-Timeout.en.md`](notes/BLH-Uart-Timeout.en.md) | [中文](notes/BLH-Uart-Timeout.zh.md) | 固件启动时序方面的一个坑（上电后第一次连接必然失败、5 秒重连超时）及可靠自动化电调连接所需的规避方法。 |

### 低优先级——仅作背景资料，与授权机制无关

| 英文笔记 | 中文原文 | 内容概要 |
|---|---|---|
| [`bi-directional-DSHOT.en.md`](notes/bi-directional-DSHOT.en.md) | [中文](notes/bi-directional-DSHOT.zh.md) | 双向 DSHOT 与 eRPM 遥测（基于 Betaflight 自身的开源实现）。仅在未来需要搭建台架测试工具时才有意义。 |
| [`Dshot-STM32-PWM-HAL.en.md`](notes/Dshot-STM32-PWM-HAL.en.md) | [中文](notes/Dshot-STM32-PWM-HAL.zh.md) | 普通 DSHOT 协议基础，以及 STM32 HAL 库 DMA-PWM 实现中的坑，同样仅作背景资料。值得注意的是记录了 DSHOT 指令 11/12（读取/保存电调设置）这一第二条、尚未探明的配置通道。 |
| [`BLHeli-Music.en.md`](notes/BLHeli-Music.en.md) | [中文](notes/BLHeli-Music.zh.md) | 启动音乐的记谱/编码方式。与授权或协议安全无关，仅为完整性保留。 |

## 官方手册（从厂商 PDF 提取）

- [`manuals/BLHeli_32_manual_ARM_Rev32.x.txt`](manuals/BLHeli_32_manual_ARM_Rev32.x.txt) ——
  官方用户手册。直接从厂商自己的文档中确认了设备端激活失败时的行为（协议降级为纯 1-2ms PWM）。
- [`manuals/BLHeliSuite32xlHistory.txt`](manuals/BLHeliSuite32xlHistory.txt) —— Linux 版上位机
  自身的版本更新日志。确认了激活服务器确实执行了真实的 TLS 证书校验（一次证书更换曾导致旧版
  客户端故障，直到修复后才恢复）。

## 本研究引用的本地硬件/软件归档（位于本目录之外）

以下两处内容严禁删除——项目的固定约束：

- `$BLHELI32PROXY_ARCHIVE_DIR/BLHeliSuite32xl/` —— 用户自行归档的 BLHeli32 上位机 Linux 版本
  （见上文二进制分析笔记，已作为一手资料使用），及其自带的官方手册、官方 Arduino 适配器固件、
  官方正式版 `.Hex` 文件。
- `$BLHELI32PROXY_ARCHIVE_DIR/32.9.5_testcode/` —— 约 70 个各厂商专属的测试固件 `.Hex` 文件——
  本项目存在的全部意义就是让这些文件能够继续被刷入。

## 关于研究过程的提示（若日后扩充本资料库需注意）

`.en.md` 笔记中引用的每一张嵌入图片，都是实际打开查看后如实描述的，而非仅凭文件名或上下文
推测——项目早期的一次处理曾跳过了这一步，结果错过了整个资料库中最重要的一项发现（即
`BLHeli-END.en.md` 中厂商工具 `BLHeliSuite32Activator` 激活日志的截图）。若日后扩充本研究，
务必坚持直接查看每一张图片。
