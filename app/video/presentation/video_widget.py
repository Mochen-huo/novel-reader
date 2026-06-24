"""网页视频浏览界面。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - depends on local PySide6 installation
    QWebEngineProfile = None
    QWebEngineSettings = None
    QWebEngineView = None

try:
    import win32con
    import win32gui
    import win32process
except ImportError:  # pragma: no cover - Windows optional dependency
    win32con = None
    win32gui = None
    win32process = None


class VideoBrowserWidget(QWidget):
    """嵌入式网页视频浏览器，只打开用户主动输入的 URL。"""

    MINI_WIDTH = 500
    BASE_ZOOM_WIDTH = 1200
    BASE_ZOOM_HEIGHT = 760
    MIN_ZOOM_FACTOR = 0.35
    MAX_ZOOM_FACTOR = 1.15
    EDGE_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
    )
    DESKTOP_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )

    def __init__(self) -> None:
        super().__init__()
        self.url_label = QLabel("视频 URL")
        self.url_input = QLineEdit()
        self.load_button = QPushButton("打开")
        self.back_button = QPushButton("后退")
        self.forward_button = QPushButton("前进")
        self.reload_button = QPushButton("刷新")
        self.edge_button = QPushButton("备用内嵌")
        self.web_view = QWebEngineView() if QWebEngineView is not None else None
        self.content_stack = QStackedWidget()
        self.edge_container = QWidget()
        self.edge_container.setObjectName("edgeContainer")
        self.edge_container.installEventFilter(self)
        self.edge_process: subprocess.Popen | None = None
        self.edge_window_handle: int | None = None
        self.edge_attach_timer = QTimer(self)
        self.edge_attach_timer.setInterval(300)
        self.edge_attach_timer.timeout.connect(self.try_attach_edge_window)
        self.edge_attach_attempts = 0
        self.fallback_label = QLabel(
            "当前 PySide6 环境无法加载 QtWebEngine。\n"
            "请确认 PySide6 的 WebEngine 组件可用后再使用网页视频功能。"
        )

        self.build_ui()
        self.configure_web_engine()
        self.bind_events()
        self.apply_dark_theme()
        self.apply_responsive_layout()
        self.apply_web_zoom()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """监听 Edge 容器尺寸变化，同步调整嵌入窗口。"""
        if watched == self.edge_container and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.resize_embedded_edge)
        return super().eventFilter(watched, event)

    def build_ui(self) -> None:
        """创建视频浏览器布局。"""
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.toolbar = QWidget()
        self.toolbar.setObjectName("videoToolbar")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(14, 10, 14, 10)
        toolbar_layout.setSpacing(10)

        self.url_input.setPlaceholderText("请输入公开视频网页 URL，例如抖音网页版链接")
        self.load_button.setFixedWidth(72)
        self.back_button.setFixedWidth(72)
        self.forward_button.setFixedWidth(72)
        self.reload_button.setFixedWidth(72)
        self.edge_button.setFixedWidth(92)

        toolbar_layout.addWidget(self.url_label)
        toolbar_layout.addWidget(self.url_input, 1)
        toolbar_layout.addWidget(self.back_button)
        toolbar_layout.addWidget(self.forward_button)
        toolbar_layout.addWidget(self.reload_button)
        toolbar_layout.addWidget(self.load_button)
        toolbar_layout.addWidget(self.edge_button)

        root_layout.addWidget(self.toolbar)
        if self.web_view is not None:
            self.content_stack.addWidget(self.web_view)
        else:
            self.fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_stack.addWidget(self.fallback_label)
        self.content_stack.addWidget(self.edge_container)
        root_layout.addWidget(self.content_stack, 1)

    def bind_events(self) -> None:
        """绑定视频浏览器事件。"""
        self.load_button.clicked.connect(self.embed_url_in_edge)
        self.edge_button.clicked.connect(self.load_url)
        self.url_input.returnPressed.connect(self.embed_url_in_edge)
        if self.web_view is not None:
            self.back_button.clicked.connect(self.web_view.back)
            self.forward_button.clicked.connect(self.web_view.forward)
            self.reload_button.clicked.connect(self.web_view.reload)

    def configure_web_engine(self) -> None:
        """配置 QtWebEngine，尽量提高现代网页兼容性。"""
        if self.web_view is None or QWebEngineSettings is None:
            return

        profile = self.web_view.page().profile()
        profile.setHttpUserAgent(self.DESKTOP_USER_AGENT)
        if QWebEngineProfile is not None:
            self.safe_set_cookie_policy(profile)

        settings = self.web_view.settings()
        self.safe_set_web_attribute(settings, "JavascriptEnabled", True)
        self.safe_set_web_attribute(settings, "LocalStorageEnabled", True)
        self.safe_set_web_attribute(settings, "PluginsEnabled", True)
        self.safe_set_web_attribute(settings, "FullScreenSupportEnabled", True)
        self.safe_set_web_attribute(settings, "PlaybackRequiresUserGesture", False)
        self.safe_set_web_attribute(settings, "AllowRunningInsecureContent", True)
        self.safe_set_web_attribute(settings, "JavascriptCanOpenWindows", True)
        self.web_view.page().fullScreenRequested.connect(self.handle_full_screen_request)

    def safe_set_web_attribute(self, settings, attribute_name: str, enabled: bool) -> None:
        """兼容不同 PySide6 版本设置 WebEngine 属性。"""
        attribute = getattr(QWebEngineSettings.WebAttribute, attribute_name, None)
        if attribute is not None:
            settings.setAttribute(attribute, enabled)

    def safe_set_cookie_policy(self, profile) -> None:
        """启用持久 Cookie，便于网站维持正常会话。"""
        policy = getattr(QWebEngineProfile.PersistentCookiesPolicy, "ForcePersistentCookies", None)
        if policy is not None:
            profile.setPersistentCookiesPolicy(policy)

    def handle_full_screen_request(self, request) -> None:
        """处理网页播放器发起的全屏请求。"""
        request.accept()
        if request.toggleOn():
            self.window().showFullScreen()
        else:
            self.window().showNormal()

    def load_url(self) -> None:
        """使用 QtWebEngine 打开网页，作为 Edge 嵌入不可用时的备用方案。"""
        if self.web_view is None:
            QMessageBox.warning(self, "提示", "当前环境没有可用的 QtWebEngine 组件。")
            return

        raw_url = self.normalized_url()
        if not raw_url:
            QMessageBox.warning(self, "提示", "请先输入网页 URL。")
            return

        self.content_stack.setCurrentWidget(self.web_view)
        self.web_view.setUrl(QUrl(raw_url))

    def embed_url_in_edge(self) -> None:
        """把系统 Edge 窗口嵌入当前 Qt 面板。"""
        raw_url = self.normalized_url()
        if not raw_url:
            QMessageBox.warning(self, "提示", "请先输入网页 URL。")
            return

        if not self.can_embed_edge():
            QMessageBox.warning(
                self,
                "提示",
                "当前环境缺少 pywin32，无法把 Edge 嵌入到 Qt 窗口。\n"
                "请安装 pywin32 后重试：pip install pywin32",
            )
            return

        edge_path = self.find_edge_executable()
        if not edge_path:
            QMessageBox.warning(self, "提示", "没有找到 Microsoft Edge。")
            return

        self.detach_existing_edge_window()
        self.content_stack.setCurrentWidget(self.edge_container)
        self.edge_process = subprocess.Popen(
            [
                edge_path,
                f"--app={raw_url}",
                "--new-window",
                f"--user-agent={self.EDGE_USER_AGENT}",
                f"--user-data-dir={self.edge_profile_dir()}",
                "--disable-features=CalculateNativeWinOcclusion",
            ]
        )
        self.edge_attach_attempts = 0
        self.edge_attach_timer.start()

    def edge_profile_dir(self) -> str:
        """返回 Edge 嵌入使用的独立用户数据目录。"""
        path = Path(__file__).resolve().parents[4] / "data" / "edge_profile"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def can_embed_edge(self) -> bool:
        """判断当前环境是否具备 Win32 窗口嵌入能力。"""
        return win32con is not None and win32gui is not None and win32process is not None

    def try_attach_edge_window(self) -> None:
        """轮询查找刚启动的 Edge 窗口并嵌入 Qt 容器。"""
        self.edge_attach_attempts += 1
        handle = self.find_edge_window_handle()
        if handle:
            self.edge_attach_timer.stop()
            self.attach_edge_window(handle)
            return

        if self.edge_attach_attempts >= 30:
            self.edge_attach_timer.stop()
            QMessageBox.warning(self, "提示", "没有找到可嵌入的 Edge 窗口。")

    def find_edge_window_handle(self) -> int | None:
        """根据 Edge 进程查找顶层窗口句柄。"""
        if self.edge_process is None or win32gui is None or win32process is None:
            return None

        process_id = self.edge_process.pid
        handles: list[int] = []

        def enum_callback(hwnd, _) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            if window_pid == process_id and class_name == "Chrome_WidgetWin_1":
                handles.append(hwnd)
                return False
            return True

        win32gui.EnumWindows(enum_callback, None)
        return handles[0] if handles else None

    def attach_edge_window(self, hwnd: int) -> None:
        """把 Edge 顶层窗口转成当前 Qt 容器的子窗口。"""
        if win32con is None or win32gui is None:
            return

        self.edge_window_handle = hwnd
        container_handle = int(self.edge_container.winId())
        win32gui.SetParent(hwnd, container_handle)

        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style = style & ~win32con.WS_POPUP
        style = style | win32con.WS_CHILD | win32con.WS_VISIBLE
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        QTimer.singleShot(0, self.resize_embedded_edge)

    def detach_existing_edge_window(self) -> None:
        """清理当前已嵌入的 Edge 窗口引用。"""
        self.edge_attach_timer.stop()
        self.edge_window_handle = None
        self.edge_process = None

    def resize_embedded_edge(self) -> None:
        """让嵌入的 Edge 跟随 Qt 容器尺寸变化。"""
        if self.edge_window_handle is None or win32gui is None:
            return

        width = max(self.edge_container.width(), 1)
        height = max(self.edge_container.height(), 1)
        win32gui.SetWindowPos(
            self.edge_window_handle,
            None,
            0,
            0,
            width,
            height,
            win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW,
        )

    def normalized_url(self) -> str:
        """标准化用户输入的 URL。"""
        raw_url = self.url_input.text().strip()
        if raw_url and not raw_url.startswith(("http://", "https://")):
            raw_url = "https://" + raw_url
        return raw_url

    def find_edge_executable(self) -> str | None:
        """查找 Windows Edge 浏览器路径。"""
        edge_from_path = shutil.which("msedge")
        if edge_from_path:
            return edge_from_path

        candidates = [
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def resizeEvent(self, event) -> None:  # noqa: N802
        """窗口缩放时自动切换紧凑布局。"""
        super().resizeEvent(event)
        self.apply_responsive_layout()
        self.apply_web_zoom()
        QTimer.singleShot(0, self.resize_embedded_edge)

    def apply_responsive_layout(self) -> None:
        """小窗口时隐藏工具栏，使网页区域完整缩放。"""
        mini = self.width() < self.MINI_WIDTH
        self.toolbar.setVisible(not mini)
        QTimer.singleShot(0, self.resize_embedded_edge)

    def apply_web_zoom(self) -> None:
        """根据 Qt 窗口大小自动缩放网页内容。"""
        if self.web_view is None:
            return

        width_ratio = max(self.width(), 1) / self.BASE_ZOOM_WIDTH
        height_ratio = max(self.height(), 1) / self.BASE_ZOOM_HEIGHT
        zoom_factor = min(width_ratio, height_ratio)
        zoom_factor = max(self.MIN_ZOOM_FACTOR, min(self.MAX_ZOOM_FACTOR, zoom_factor))
        self.web_view.setZoomFactor(zoom_factor)

    def apply_dark_theme(self) -> None:
        """应用暗色工具栏样式。"""
        self.setStyleSheet(
            """
            QWidget {
                background: #1e1e1e;
                color: #d4d4d4;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 14px;
            }
            QWidget#videoToolbar {
                background: #333333;
                border-bottom: 1px solid #3c3c3c;
            }
            QLineEdit {
                background: #252526;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 8px 10px;
            }
            QPushButton {
                background: #0e639c;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background: #1177bb;
            }
            QWidget#edgeContainer {
                background: #000000;
            }
            """
        )
