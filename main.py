"""小说阅读器入口文件。"""

from __future__ import annotations

import sys
import os

from PySide6.QtWidgets import QApplication

from app.presentation.main_window import MainWindow


def main() -> int:
    """创建 Qt 应用并显示主窗口。"""
    webengine_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    media_flag = "--autoplay-policy=no-user-gesture-required"
    if media_flag not in webengine_flags:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{webengine_flags} {media_flag}".strip()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
