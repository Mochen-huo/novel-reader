"""网页视频浏览界面。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.common.utils import data_dir

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

    def __init__(self) -> None:
        super().__init__()
        self.url_label = QLabel("视频 URL")
        self.url_input = QLineEdit()
        self.load_button = QPushButton("Edge打开")
        self.back_button = QPushButton("后退")
        self.forward_button = QPushButton("前进")
        self.reload_button = QPushButton("刷新")
        self.edge_container = QWidget()
        self.edge_container.setObjectName("edgeContainer")
        self.edge_container.installEventFilter(self)
        self.edge_process: subprocess.Popen | None = None
        self.edge_window_handle: int | None = None
        self.settings = QSettings()
        self.edge_attach_timer = QTimer(self)
        self.edge_attach_timer.setInterval(300)
        self.edge_attach_timer.timeout.connect(self.try_attach_edge_window)
        self.edge_attach_attempts = 0

        self.build_ui()
        self.bind_events()
        self.apply_dark_theme()
        self.apply_responsive_layout()

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
        self.load_button.setFixedWidth(82)
        self.back_button.setFixedWidth(72)
        self.forward_button.setFixedWidth(72)
        self.reload_button.setFixedWidth(72)

        toolbar_layout.addWidget(self.url_label)
        toolbar_layout.addWidget(self.url_input, 1)
        toolbar_layout.addWidget(self.back_button)
        toolbar_layout.addWidget(self.forward_button)
        toolbar_layout.addWidget(self.reload_button)
        toolbar_layout.addWidget(self.load_button)

        root_layout.addWidget(self.toolbar)
        root_layout.addWidget(self.edge_container, 1)

    def bind_events(self) -> None:
        """绑定视频浏览器事件。"""
        self.load_button.clicked.connect(self.embed_url_in_edge)
        self.url_input.returnPressed.connect(self.embed_url_in_edge)
        self.back_button.clicked.connect(self.go_back)
        self.forward_button.clicked.connect(self.go_forward)
        self.reload_button.clicked.connect(self.reload_page)

    def go_back(self) -> None:
        """控制嵌入的 Edge 后退。"""
        if win32con is not None:
            self.send_edge_hotkey(win32con.VK_BROWSER_BACK)

    def go_forward(self) -> None:
        """控制嵌入的 Edge 前进。"""
        if win32con is not None:
            self.send_edge_hotkey(win32con.VK_BROWSER_FORWARD)

    def reload_page(self) -> None:
        """控制嵌入的 Edge 刷新。"""
        self.send_edge_hotkey(ord("R"), ctrl=True)

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

        self.save_settings()
        self.detach_existing_edge_window()
        self.edge_process = subprocess.Popen(
            [
                edge_path,
                f"--app={raw_url}",
                "--new-window",
                f"--user-data-dir={self.edge_profile_dir()}",
                "--disable-features=CalculateNativeWinOcclusion",
            ]
        )
        self.edge_attach_attempts = 0
        self.edge_attach_timer.start()

    def edge_profile_dir(self) -> str:
        """返回 Edge 嵌入使用的独立用户数据目录。"""
        path = data_dir() / "edge_profile"
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
        style &= ~win32con.WS_POPUP
        style |= win32con.WS_CHILD | win32con.WS_VISIBLE
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            max(self.edge_container.width(), 1),
            max(self.edge_container.height(), 1),
            win32con.SWP_NOZORDER
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_FRAMECHANGED
            | win32con.SWP_SHOWWINDOW,
        )
        QTimer.singleShot(0, self.resize_embedded_edge)

    def detach_existing_edge_window(self) -> None:
        """清理当前已嵌入的 Edge 窗口引用。"""
        self.edge_attach_timer.stop()
        if self.edge_process is not None and self.edge_process.poll() is None:
            self.edge_process.terminate()
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

    def send_edge_hotkey(self, key_code: int, ctrl: bool = False) -> None:
        """向嵌入的 Edge 发送常用浏览器快捷键。"""
        if self.edge_window_handle is None or win32gui is None or win32con is None:
            return
        win32gui.SetFocus(self.edge_window_handle)
        if ctrl:
            win32gui.PostMessage(self.edge_window_handle, win32con.WM_KEYDOWN, win32con.VK_CONTROL, 0)
        win32gui.PostMessage(self.edge_window_handle, win32con.WM_KEYDOWN, key_code, 0)
        win32gui.PostMessage(self.edge_window_handle, win32con.WM_KEYUP, key_code, 0)
        if ctrl:
            win32gui.PostMessage(self.edge_window_handle, win32con.WM_KEYUP, win32con.VK_CONTROL, 0)

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
        QTimer.singleShot(0, self.resize_embedded_edge)

    def apply_responsive_layout(self) -> None:
        """小窗口时隐藏工具栏，使网页区域完整缩放。"""
        mini = self.width() < self.MINI_WIDTH
        self.toolbar.setVisible(not mini)
        QTimer.singleShot(0, self.resize_embedded_edge)

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

    def restore_settings(self) -> None:
        """恢复最近打开的视频 URL。"""
        self.url_input.setText(self.settings.value("video/last_url", ""))

    def save_settings(self) -> None:
        """保存最近打开的视频 URL。"""
        self.settings.setValue("video/last_url", self.url_input.text().strip())
