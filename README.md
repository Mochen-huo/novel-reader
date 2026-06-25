# Python 桌面阅读与网页视频工具

这是一个用于学习的桌面工具。小说功能不会内置小说网址，也不会自动搜索小说；它只会根据用户输入的公开章节 URL 请求网页、解析标题和正文、保存到本地 SQLite，并在桌面界面中显示。视频网页功能只会打开用户主动输入的网页 URL，相当于在程序内嵌浏览器中访问网页。

## 功能

- 输入单个章节 URL 并获取章节内容
- 使用 `requests` 请求网页，`BeautifulSoup4 + lxml` 解析 HTML
- 自动处理常见中文网页编码
- 按通用规则提取章节标题和正文
- 过滤常见广告语和导航文本
- 保存到 `data/novels.db`
- 左侧显示本地章节列表，右侧显示正文
- 支持置顶、切走隐藏、悬浮恢复按钮和系统托盘
- 自动保存窗口状态、阅读偏好、最近章节、滚动位置和最近视频 URL
- 小说阅读支持字号调整、护眼主题和正文搜索
- 视频网页标签页可打开用户输入的公开视频网页 URL
- VSCode 风格暗色界面

## 合规限制

本项目不包含以下功能：

- 不爬取付费章节、登录后内容、加密内容
- 不绕过网站反爬机制
- 不使用代理池、验证码绕过、登录 Cookie 绕过
- 不使用 Scrapy、Selenium、Playwright
- 不做全站爬取
- 视频网页功能不绕过网站登录、会员、加密、风控或反爬限制

## 安装

建议使用 Python 3.10 或更高版本。

```bash
cd novel/novel_reader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

如果你使用 macOS 或 Linux，激活虚拟环境命令通常是：

```bash
source .venv/bin/activate
```

## 运行

```bash
python main.py
```

首次运行时会自动创建 `data` 目录和 `data/novels.db` 数据库文件。

## 小说使用方法

1. 在顶部输入框粘贴一个公开可访问的小说章节 URL。
2. 点击“获取章节”。
3. 获取成功后，章节会自动保存到本地数据库。
4. 如果页面本身提供“上一章 / 下一章”链接，可以直接点击工具栏里的“上一章”或“下一章”继续阅读。
5. 点击左侧列表中的章节，可以读取并显示本地已保存内容。

阅读工具栏还提供：

- `A- / A+`：调整正文大小。
- `护眼 / 暗色`：切换阅读主题。
- `查找`：在当前章节正文中搜索下一个关键词。
- `专注`：隐藏非核心控件，降低阅读干扰。

程序会自动记录最近阅读章节和每章滚动位置。

## 视频网页使用方法

1. 切换到“视频网页”标签页。
2. 输入公开视频网页 URL。
3. 点击“Edge打开”。
4. 窗口缩小时，视频页工具栏会自动隐藏，网页区域会像小说迷你模式一样占满窗口。

视频网页功能使用真实 Microsoft Edge：

- `Edge打开`：使用真实 Microsoft Edge 窗口并嵌入到 Qt 视频区域，Windows 下需要 `pywin32`。

Edge 会作为子窗口嵌入到 Qt 视频区域，并保留浏览器原生边框，缩放时更稳定。

## 窗口控制

顶层工具栏提供：

- `置顶`：让主窗口保持在其他窗口上方。
- `切走隐藏`：切换到其他窗口时自动隐藏主窗口。
- `悬浮按钮`：显示一个可拖动的小按钮，点击可隐藏或恢复主窗口。

点击窗口右上角关闭会直接退出程序。需要临时隐藏窗口时，可以使用 `切走隐藏`、悬浮按钮或托盘菜单里的“显示/隐藏”。

## 打包 EXE

Windows 下可以使用项目里的脚本打包：

```powershell
cd novel_reader
$env:PYTHON = "E:\develop\Miniconda3\envs\yoloyolo2026\python.exe"
.\build_exe.ps1
```

打包完成后，文件位于：

```txt
dist\NovelReader\NovelReader.exe
```

## 后续适配具体网站

如果某个网站的通用解析失败，请修改：

- 文件：`app/novel/infrastructure/crawler.py`
- 函数：`ChapterCrawler.extract_content`

你可以在 `extract_content` 中为指定网站增加专用正文选择器，也可以扩展 `CONTENT_ID_CANDIDATES` 和 `CONTENT_CLASS_CANDIDATES`。

## 目录分层

```txt
app/
├─ presentation/
│  └─ main_window.py                  # 顶层标签页窗口
├─ novel/
│  ├─ domain/
│  │  └─ models.py                    # 小说领域数据模型
│  ├─ application/
│  │  └─ services.py                  # 小说业务流程
│  ├─ infrastructure/
│  │  ├─ crawler.py                   # 小说网页请求与 HTML 解析
│  │  └─ database.py                  # 小说 SQLite 数据访问
│  └─ presentation/
│     ├─ main_window.py               # 小说阅读界面
│     └─ workers.py                   # 小说后台任务
├─ video/
│  └─ presentation/
│     └─ video_widget.py              # 网页视频浏览界面
└─ common/
   └─ utils.py                        # 通用路径工具
```

依赖方向：

```txt
app.presentation -> app.novel / app.video
app.novel.presentation -> app.novel.application -> app.novel.infrastructure
app.novel.application -> app.novel.domain
app.novel.infrastructure -> app.common
```

## 数据库结构

数据库文件：`data/novels.db`

表：`chapters`

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
title TEXT
book_title TEXT
url TEXT UNIQUE
content TEXT
created_at TEXT
prev_url TEXT
next_url TEXT
```
