# lecture-video-skill

[English](README.md) | 简体中文

将课件、大纲或论文制作成带配音的教学视频，同时交付字幕、逐字稿和可编辑课件。

这是供支持 `SKILL.md` 的编程代理使用的工作流与脚本模板。示例采用生物信息学主题和模拟数据，
工作流也可用于其他科学课程。

## 能力

- 将讲解拆成逐步出现的 HTML/SVG 页面，输出 1080p 视频。
- 高亮正在讲解的图示或代码，支持移动吉祥物和延迟高亮。
- 检查外部配音的漏读、错读和重复，按句修补并复用已确认的录音。
- 调整语速与句间、步骤间停顿，同时保持音高。
- 输出 MP4、SRT、带页时间段的 Markdown 逐字稿，以及文字可编辑的 PPTX。
- 可选：在 macOS 上使用 Office 字体排版并检查 PowerPoint 的实际渲染。

## 安装与使用

将本仓库内容放入代理的技能目录，文件夹命名为 `lecture-video`。例如：

```text
skills/
  lecture-video/
    SKILL.md
    references/
    template/
    examples/
```

调用示例：

```text
用 /lecture-video 把这份课件做成约 20 分钟的教学视频，先整理大纲。
```

运行脚本需要 Python 3.10+、依赖包和浏览器。安装步骤与可配置项见
[环境说明](references/environment.md)。制作流程见 [SKILL.md](SKILL.md)。

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
export LECTURE_BROWSER_CHANNEL=""
```

将 `template/` 复制为课程项目的 `build/`，在项目中编辑页面、脚本并存放配音。
`examples/` 提供四个页面、对应的旁白结构和模拟结果图生成脚本。
正式配音可使用外部录音或所选 TTS 平台；账户相关操作需要相应授权。

## 配置

| 配置项 | 用途 |
| --- | --- |
| `LECTURE_BROWSER_CHANNEL` | Playwright 浏览器通道；空字符串使用安装的 Chromium |
| `LECTURE_ASR_MODEL` | ASR 模型名或本地模型目录，默认 `large-v3-turbo` |
| `LECTURE_SUBTITLE_FONT` | 字幕使用的 CJK 字体文件 |
| `LECTURE_SUBTITLE_FONT_INDEX` | 字体集合的 face 索引 |
| `LECTURE_MONO_FONT` | 可选 PPTX 近似预览的等宽字体 |
| `VOICE_DIR` | 配音平台目录名，默认 `豆包` |

macOS 的系统字体路径和 PowerPoint 应用路径是平台默认值；其他环境可按说明配置字体和浏览器。
Office 字体导出和 PowerPoint 实测依赖本机安装的软件，仓库不包含其字体文件。

## 仓库内容

- `SKILL.md`：代理入口和制作流程。
- `references/`：页面契约、配音修补、运行环境。
- `template/`：可复制到课程项目的构建脚本与视觉资源。
- `examples/`：通用示例与模拟图。
- `requirements.txt`：Python 依赖。

私人课程素材、录音、逐字稿、个人路径、账户配置、模型权重、校准缓存、生成结果和工作日志
应保留在课程项目中，不加入此公开技能仓库。附带字体的版权说明与许可证见 [NOTICE.md](NOTICE.md)。
