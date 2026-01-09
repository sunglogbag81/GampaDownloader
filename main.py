# ===== main.py (FULL) - Part 1 / N =====
import os
import sys
import re
import time
import atexit
import faulthandler
from pathlib import Path
from dataclasses import dataclass
from datetime import timedelta
from collections import deque

import yt_dlp
from PySide6.QtCore import (
    Qt, QObject, QThread, Signal, Slot, QSettings, QMimeData,
    qInstallMessageHandler, QTimer
)
from PySide6.QtGui import QAction, QKeySequence, QPalette, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QProgressBar, QPlainTextEdit, QToolBar, QCheckBox,
    QComboBox, QGroupBox, QFormLayout, QTabWidget
)

# -------------------- Crash/Qt logs --------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
CRASH_LOG_PATH = os.path.join(APP_DIR, "crash.log")
QT_LOG_PATH = os.path.join(APP_DIR, "qt.log")


def _setup_faulthandler():
    fp = open(CRASH_LOG_PATH, "a", encoding="utf-8")
    faulthandler.enable(fp)
    fp.write(f"\n=== session start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    fp.flush()

    def _on_exit():
        try:
            fp.write(f"=== atexit {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            fp.flush()
        except Exception:
            pass

    atexit.register(_on_exit)
    return fp


def _setup_qt_message_log():
    fp = open(QT_LOG_PATH, "a", encoding="utf-8")
    fp.write(f"\n=== qt session start {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    fp.flush()

    def handler(mode, context, message):
        try:
            fp.write(message + "\n")
            fp.flush()
        except Exception:
            pass

    qInstallMessageHandler(handler)
    return fp


# -------------------- Utilities --------------------
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
URL_RE = re.compile(r"https?://[^\s]+")


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub("", s or "")


def hms(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    return str(timedelta(seconds=int(seconds)))


def app_base_path() -> str:
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def ffmpeg_location() -> str | None:
    base = app_base_path()
    ffmpeg = os.path.join(base, "ffmpeg.exe")
    ffprobe = os.path.join(base, "ffprobe.exe")
    if os.path.exists(ffmpeg) and os.path.exists(ffprobe):
        return base  # 둘이 있는 폴더
    return None


def extract_urls_from_text(text: str) -> list[str]:
    urls = URL_RE.findall(text or "")
    return [u.strip().strip(")>]}.,") for u in urls]


def normalize_url(url: str) -> str:
    return (url or "").strip()


TAB_SUFFIXES = ("videos", "streams", "live", "shorts", "featured", "playlists")


def normalize_channel_to_videos(url: str) -> str:
    """
    채널 메인 URL(@handle, /channel/, /c/, /user/)이면 videos 탭으로 유도.
    """
    u = normalize_url(url)
    if not u:
        return u
    base = u.rstrip("/")
    if any(base.endswith("/" + t) for t in TAB_SUFFIXES):
        return u
    if ("youtube.com/@" in base) or ("/channel/" in base) or ("/c/" in base) or ("/user/" in base):
        return base + "/videos"
    return u


def looks_like_tab_entry(e: dict) -> bool:
    if not isinstance(e, dict):
        return False
    u = (e.get("url") or e.get("webpage_url") or "").lower()
    if not u:
        return False
    return any(u.rstrip("/").endswith("/" + t) for t in TAB_SUFFIXES)


def safe_date_yyyymmdd(s: str) -> str:
    """
    yt-dlp --dateafter/--datebefore 는 yyyymmdd 등을 받는다.
    UI 입력에서 'YYYY-MM-DD' 또는 'YYYYMMDD'를 허용.
    """
    t = (s or "").strip()
    if not t:
        return ""
    t = t.replace("-", "").replace("/", "").replace(".", "")
    if len(t) != 8 or not t.isdigit():
        return ""  # invalid
    return t


# -------------------- Themes --------------------
def palette_dark_discord() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#36393F"))
    p.setColor(QPalette.WindowText, QColor("#DCDDDE"))
    p.setColor(QPalette.Base, QColor("#2F3136"))
    p.setColor(QPalette.AlternateBase, QColor("#2B2D31"))
    p.setColor(QPalette.Text, QColor("#DCDDDE"))
    p.setColor(QPalette.Button, QColor("#2F3136"))
    p.setColor(QPalette.ButtonText, QColor("#DCDDDE"))
    p.setColor(QPalette.Highlight, QColor("#5865F2"))
    p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    return p


def palette_light_clean() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor("#F4F5F7"))
    p.setColor(QPalette.WindowText, QColor("#111827"))
    p.setColor(QPalette.Base, QColor("#FFFFFF"))
    p.setColor(QPalette.AlternateBase, QColor("#F3F4F6"))
    p.setColor(QPalette.Text, QColor("#111827"))
    p.setColor(QPalette.Button, QColor("#E5E7EB"))
    p.setColor(QPalette.ButtonText, QColor("#111827"))
    p.setColor(QPalette.Highlight, QColor("#2563EB"))
    p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    return p


QSS_DARK = """
QWidget { font-family: "Segoe UI"; font-size: 13px; }
QLabel#Subtle { color: #AAB2BD; }
QLabel#Header { font-size: 20px; font-weight: 800; color: #FFFFFF; }
QLabel#Status { color: #DCDDDE; font-weight: 700; }

QLineEdit, QPlainTextEdit, QComboBox {
  background: #2F3136;
  border: 1px solid #202225;
  border-radius: 10px;
  padding: 10px;
  color: #DCDDDE;
  selection-background-color: #5865F2;
}

QLineEdit:focus, QComboBox:focus { border: 1px solid #5865F2; }
QComboBox::drop-down { border: 0px; width: 28px; }
QComboBox::down-arrow {
  image: none;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 8px solid #DCDDDE;
  margin-right: 10px;
}

QGroupBox {
  border: 1px solid #202225;
  border-radius: 12px;
  margin-top: 12px;
}

QGroupBox::title {
  subcontrol-origin: margin;
  subcontrol-position: top left;
  padding: 0 6px;
  color: #DCDDDE;
  font-weight: 800;
}

QTableWidget {
  background: #2F3136;
  border: 1px solid #202225;
  border-radius: 12px;
  alternate-background-color: #2B2D31;
}

QHeaderView::section {
  background: #202225;
  color: #DCDDDE;
  padding: 8px;
  border: 0px;
}

QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background: #3A3D44; }

QPushButton {
  background: #2F3136;
  border: 1px solid #202225;
  border-radius: 10px;
  padding: 10px 12px;
  font-weight: 800;
  color: #DCDDDE;
}

QPushButton:hover { background: #34373C; border: 1px solid #1F2124; }
QPushButton:pressed {
  background: #232428;
  border: 1px solid #5865F2;
  padding-top: 12px;
  padding-bottom: 8px;
}

QPushButton:disabled { background: #2B2D31; color: #7B8190; border: 1px solid #202225; }

QPushButton#Primary { background: #5865F2; border: 1px solid #5865F2; color: #FFFFFF; }
QPushButton#Primary:hover { background: #4E5AE6; border: 1px solid #4E5AE6; }
QPushButton#Primary:pressed { background: #3C45B5; border: 1px solid #3C45B5; padding-top: 12px; padding-bottom: 8px; }

QPushButton#Success { background: #3BA55C; border: 1px solid #3BA55C; color: #0B1A0F; }
QPushButton#Success:hover { background: #339150; border: 1px solid #339150; }
QPushButton#Success:pressed { background: #246A3A; border: 1px solid #246A3A; padding-top: 12px; padding-bottom: 8px; }

QPushButton#Danger { background: #ED4245; border: 1px solid #ED4245; color: #1A0B0B; }
QPushButton#Danger:hover { background: #D83C3E; border: 1px solid #D83C3E; }
QPushButton#Danger:pressed { background: #A92E30; border: 1px solid #A92E30; padding-top: 12px; padding-bottom: 8px; }

QProgressBar {
  background: #202225;
  border: 1px solid #202225;
  border-radius: 10px;
  height: 14px;
  text-align: center;
  color: #DCDDDE;
}

QProgressBar::chunk { background: #5865F2; border-radius: 10px; }

/* Tabs - Discord-ish (clean) */
QTabWidget::pane {
  border: 1px solid #202225;
  border-radius: 12px;
  top: 0px;
  background: #2F3136;
}

QTabBar { background: transparent; }

QTabBar::tab {
  background: #2B2D31;
  color: #DCDDDE;
  border: 1px solid #202225;
  border-bottom: 0px;
  padding: 8px 12px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  margin-right: 6px;
}

QTabBar::tab:selected { background: #2F3136; }
QTabBar::tab:hover { background: #34373C; }

QCheckBox { color: #DCDDDE; }
"""

QSS_LIGHT = """
QWidget { font-family: "Segoe UI"; font-size: 13px; }
QLabel#Subtle { color: #6B7280; }
QLabel#Header { font-size: 20px; font-weight: 800; color: #111827; }
QLabel#Status { color: #111827; font-weight: 700; }

QLineEdit, QPlainTextEdit, QComboBox {
  background: #FFFFFF;
  border: 1px solid #D1D5DB;
  border-radius: 10px;
  padding: 10px;
  color: #111827;
  selection-background-color: #2563EB;
}

QLineEdit:focus, QComboBox:focus { border: 1px solid #2563EB; }
QComboBox::drop-down { border: 0px; width: 28px; }
QComboBox::down-arrow {
  image: none;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 8px solid #111827;
  margin-right: 10px;
}

QGroupBox {
  border: 1px solid #D1D5DB;
  border-radius: 12px;
  margin-top: 12px;
}

QGroupBox::title {
  subcontrol-origin: margin;
  subcontrol-position: top left;
  padding: 0 6px;
  color: #111827;
  font-weight: 800;
}

QTableWidget {
  background: #FFFFFF;
  border: 1px solid #D1D5DB;
  border-radius: 12px;
  alternate-background-color: #F3F4F6;
}

QHeaderView::section { background: #F3F4F6; color: #111827; padding: 8px; border: 0px; }
QTableWidget::item:selected { background: #DBEAFE; }

QPushButton {
  background: #E5E7EB;
  border: 1px solid #D1D5DB;
  border-radius: 10px;
  padding: 10px 12px;
  font-weight: 800;
  color: #111827;
}

QPushButton:hover { background: #D1D5DB; }
QPushButton:pressed {
  background: #C7CDD6;
  border: 1px solid #2563EB;
  padding-top: 12px;
  padding-bottom: 8px;
}

QPushButton:disabled { color: #9CA3AF; }

QPushButton#Primary { background: #2563EB; border: 1px solid #2563EB; color: white; }
QPushButton#Primary:hover { background: #1D4ED8; border: 1px solid #1D4ED8; }
QPushButton#Primary:pressed { background: #1E40AF; border: 1px solid #1E40AF; padding-top: 12px; padding-bottom: 8px; }

QPushButton#Success { background: #16A34A; border: 1px solid #16A34A; color: white; }
QPushButton#Success:hover { background: #15803D; border: 1px solid #15803D; }
QPushButton#Success:pressed { background: #166534; border: 1px solid #166534; padding-top: 12px; padding-bottom: 8px; }

QPushButton#Danger { background: #DC2626; border: 1px solid #DC2626; color: white; }
QPushButton#Danger:hover { background: #B91C1C; border: 1px solid #B91C1C; }
QPushButton#Danger:pressed { background: #991B1B; border: 1px solid #991B1B; padding-top: 12px; padding-bottom: 8px; }

QProgressBar {
  background: #E5E7EB;
  border: 1px solid #D1D5DB;
  border-radius: 10px;
  height: 14px;
  text-align: center;
}

QProgressBar::chunk { background: #2563EB; border-radius: 10px; }

/* Tabs - light (clean) */
QTabWidget::pane {
  border: 1px solid #D1D5DB;
  border-radius: 12px;
  top: 0px;
  background: #FFFFFF;
}

QTabBar { background: transparent; }

QTabBar::tab {
  background: #F3F4F6;
  color: #111827;
  border: 1px solid #D1D5DB;
  border-bottom: 0px;
  padding: 8px 12px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  margin-right: 6px;
}

QTabBar::tab:selected { background: #FFFFFF; }
QTabBar::tab:hover { background: #E5E7EB; }
"""

# -------------------- Data --------------------
@dataclass
class QueueItem:
    url: str
    title: str = ""
    status: str = "Queued"


# -------------------- Expand worker (persistent thread) --------------------
class ExpandWorker(QObject):
    log = Signal(str)
    count = Signal(int)
    finished_one = Signal(bool, str, list)  # ok, msg, list[QueueItem]
    idle = Signal()
    request = Signal(str)

    def __init__(self):
        super().__init__()
        self._stop = False
        self._queue = deque()
        self._working = False
        self.request.connect(self.enqueue)

    @Slot()
    def stop(self):
        self._stop = True
        self._queue.clear()

    @Slot(str)
    def enqueue(self, url: str):
        url = normalize_url(url)
        if not url:
            return
        self._queue.append(url)
        if not self._working:
            self._working = True
            QTimer.singleShot(0, self._process_next)

    @Slot()
    def _process_next(self):
        if self._stop:
            self._working = False
            self.idle.emit()
            return
        if not self._queue:
            self._working = False
            self.idle.emit()
            return
        url = self._queue.popleft()
        self._expand(url)
        QTimer.singleShot(0, self._process_next)

    def _extract_flat(self, url: str):
        ydl_opts = {
            "quiet": True,
            "ignoreerrors": True,
            "extract_flat": "in_playlist",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    def _expand(self, url: str):
        self._stop = False
        self.count.emit(0)
        self.log.emit(f"확장 시작: {url}")

        try:
            info = self._extract_flat(url)
        except Exception as e:
            self.finished_one.emit(False, f"분석 실패: {e}", [])
            return

        if not info:
            self.finished_one.emit(False, "정보를 가져오지 못했습니다.", [])
            return

        entries = []
        if isinstance(info, dict) and "entries" in info and info["entries"]:
            entries = [e for e in info["entries"] if e]

        # Patch: 탭 엔트리만이면 /videos로 재시도
        if entries and all(looks_like_tab_entry(e) for e in entries):
            self.log.emit("탭 엔트리만 감지됨 → /videos로 재시도")
            retry_url = normalize_channel_to_videos(url)
            if retry_url != url:
                try:
                    info2 = self._extract_flat(retry_url)
                    if info2 and isinstance(info2, dict) and "entries" in info2 and info2["entries"]:
                        entries2 = [e for e in info2["entries"] if e]
                        if entries2 and not all(looks_like_tab_entry(e) for e in entries2):
                            entries = entries2
                            self.log.emit(f"재시도 성공: {retry_url}")
                        else:
                            self.log.emit("videos 재시도에서도 탭/빈 결과 → 원래 결과 유지")
                except Exception as e:
                    self.log.emit(f"videos 재시도 실패: {e}")

        collected: list[QueueItem] = []
        if entries:
            n = 0
            for e in entries:
                if self._stop:
                    self.finished_one.emit(False, f"사용자 취소(수집 {n}개)", collected)
                    return
                u = e.get("url") or e.get("webpage_url") or ""
                t = e.get("title") or ""
                if u:
                    collected.append(QueueItem(url=u, title=t or u, status="Queued"))
                    n += 1
                    if (n % 200) == 0:
                        self.count.emit(n)

            self.count.emit(n)
            self.finished_one.emit(True, f"추가 완료({n}개)", collected)
            return

        title = info.get("title") if isinstance(info, dict) else None
        title = title or url
        collected.append(QueueItem(url=url, title=title, status="Queued"))
        self.count.emit(1)
        self.finished_one.emit(True, "추가 완료(1개)", collected)

class DownloadWorker(QObject):
    log = Signal(str)
    current_title = Signal(str)
    file_progress = Signal(int)
    total_progress = Signal(int)
    file_eta = Signal(str)
    total_eta = Signal(str)
    finished = Signal(bool, str)

    def __init__(
        self,
        items: list[QueueItem],
        save_folder: str,
        keep_thumb: bool,
        keep_sub: bool,
        log_path: str | None,
        fmt: str,
        format_sort: list[str] | None,
        cookiesfrombrowser: tuple | None,
        filter_opts: dict
    ):
        super().__init__()
        self.items = items
        self.save_folder = save_folder
        self.keep_thumb = keep_thumb
        self.keep_sub = keep_sub
        self.log_path = log_path
        self.fmt = fmt
        self.format_sort = format_sort
        self.cookiesfrombrowser = cookiesfrombrowser
        self.filter_opts = filter_opts
        self._stop = False
        self._start = 0.0
        self._total = 0
        self._done = 0

    def stop(self):
        self._stop = True

    @Slot()
    def run(self):
        if not self.items:
            self.finished.emit(False, "대기열이 비어있습니다.")
            return

        self._start = time.time()
        self._total = len(self.items)
        self._done = 0

        outtmpl = os.path.join(self.save_folder, "%(title)s.%(ext)s")
        ffloc = ffmpeg_location()

        def hook(d):
            if self._stop:
                return
            st = d.get("status")
            if st == "downloading":
                p_str = strip_ansi(d.get("_percent_str", "0%")).replace("%", "").strip()
                eta_str = strip_ansi(d.get("_eta_str", "--:--")).strip()
                try:
                    self.file_progress.emit(int(float(p_str)))
                except Exception:
                    pass
                self.file_eta.emit(eta_str)

                elapsed = time.time() - self._start
                if self._done > 0:
                    avg = elapsed / self._done
                    rem = self._total - self._done
                    self.total_eta.emit(hms(int(avg * rem)))
                else:
                    self.total_eta.emit("계산 중...")
            elif st == "finished":
                self.log.emit("병합 중...")

        ydl_opts = {
            "format": self.fmt,
            "merge_output_format": "mkv",
            "outtmpl": outtmpl,
            "ignoreerrors": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [hook],
            "writethumbnail": bool(self.keep_thumb),
            "writesubtitles": bool(self.keep_sub),
        }

        # 코덱/컨테이너 선호 (yt-dlp -S / --format-sort)
        if self.format_sort:
            ydl_opts["format_sort"] = self.format_sort

        # 쿠키 (yt-dlp --cookies-from-browser, python opts: cookiesfrombrowser)
        if self.cookiesfrombrowser:
            ydl_opts["cookiesfrombrowser"] = self.cookiesfrombrowser

        # 부분 다운로드(필터): dateafter/datebefore (yt-dlp 옵션)
        ydl_opts.update(self.filter_opts)

        if ffloc:
            ydl_opts["ffmpeg_location"] = ffloc

        f = None
        try:
            if self.log_path:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                f = open(self.log_path, "a", encoding="utf-8")
                f.write(f"\n--- Session {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                f.write(f"format={self.fmt}\n")
                if self.format_sort:
                    f.write(f"format_sort={self.format_sort}\n")
                if self.cookiesfrombrowser:
                    f.write(f"cookiesfrombrowser={self.cookiesfrombrowser}\n")
                if self.filter_opts:
                    f.write(f"filter_opts={self.filter_opts}\n")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for idx, item in enumerate(self.items):
                    if self._stop:
                        self.finished.emit(False, "사용자 중지")
                        return

                    title = item.title or item.url
                    self.current_title.emit(title)

                    msg = f"[{idx+1}/{self._total}] {title}"
                    self.log.emit(msg)
                    if f:
                        f.write(msg + "\n")

                    self.file_progress.emit(0)
                    self.file_eta.emit("--:--")

                    try:
                        ydl.download([item.url])
                    except Exception as e:
                        emsg = f"실패: {title} ({e})"
                        self.log.emit(emsg)
                        if f:
                            f.write(emsg + "\n")

                    self._done += 1
                    self.total_progress.emit(int((self._done / self._total) * 100))

            self.file_progress.emit(100)
            self.total_progress.emit(100)
            self.total_eta.emit("00:00:00")
            self.finished.emit(True, "완료")
        finally:
            if f:
                f.close()


# -------------------- Main Window --------------------
class MainWindow(QMainWindow):
    ORG = "LocalLab"
    APP = "YTQueueUltimateFullPlusTabs"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.resize(1380, 920)
        self.setAcceptDrops(True)

        self.settings = QSettings(self.ORG, self.APP)

        # 기본 저장 폴더: (설정값 없을 때) 사용자 다운로드 폴더
        default_download_folder = str(Path.home() / "Downloads")
        self.save_folder = self.settings.value("save_folder", default_download_folder, str)

        self.theme_mode = self.settings.value("theme_mode", "dark", str)
        self.keep_thumb = self.settings.value("keep_thumb", False, bool)
        self.keep_sub = self.settings.value("keep_sub", False, bool)
        self.log_to_file = self.settings.value("log_to_file", False, bool)
        self.force_best = self.settings.value("force_best", True, bool)
        self.max_quality = self.settings.value("max_quality", "1080p", str)

        # 새 기능 설정
        self.use_cookies = self.settings.value("use_cookies", False, bool)
        self.cookie_browser = self.settings.value("cookie_browser", "chrome", str)
        self.filter_exclude_shorts = self.settings.value("filter_exclude_shorts", False, bool)
        self.filter_date_after = self.settings.value("filter_date_after", "", str)
        self.filter_date_before = self.settings.value("filter_date_before", "", str)
        self.filter_include_kw = self.settings.value("filter_include_kw", "", str)
        self.filter_exclude_kw = self.settings.value("filter_exclude_kw", "", str)
        self.codec_pref = self.settings.value("codec_pref", "auto", str)

        self.queue: list[QueueItem] = []
        self.url_set: set[str] = set()
        self._pending_count = 0
        self._expanding_collected_count = 0

        self.worker_thread: QThread | None = None
        self.worker: DownloadWorker | None = None

        self._build_ui()
        self._build_menu_toolbar()
        self.apply_theme(self.theme_mode)
        self.on_toggle_best(None)

        # persistent expand thread
        self.expand_thread = QThread(self)
        self.expand_worker = ExpandWorker()
        self.expand_worker.moveToThread(self.expand_thread)
        self.expand_thread.start()
        self.expand_worker.log.connect(self.append_log)
        self.expand_worker.count.connect(self.on_expand_count)
        self.expand_worker.finished_one.connect(self.on_expand_finished_one)
        self.expand_worker.idle.connect(self.on_expand_idle)

        self.refresh_state()
        self.append_log("App started. Tabs UI + cookies + filtering + codec preference.")

    # ----- Safe shutdown -----
    def closeEvent(self, event):
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass
        try:
            if self.worker_thread and self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(5000)
        except Exception:
            pass
        try:
            if self.expand_worker:
                self.expand_worker.stop()
            if self.expand_thread and self.expand_thread.isRunning():
                self.expand_thread.quit()
                self.expand_thread.wait(5000)
        except Exception:
            pass
        super().closeEvent(event)

    # ----- Drag & Drop -----
    def dragEnterEvent(self, event):
        md: QMimeData = event.mimeData()
        if md.hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        text = event.mimeData().text()
        urls = extract_urls_from_text(text)
        if urls:
            self.add_urls_as_queue(urls)

    # ----- UI -----
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QHBoxLayout(root)
        main.setContentsMargins(14, 14, 14, 14)
        main.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)
        main.addWidget(splitter)

        # --- Left Widgets (tabs) ---
        left = QWidget()
        left_root = QVBoxLayout(left)
        left_root.setContentsMargins(12, 12, 12, 12)
        left_root.setSpacing(10)

        header = QLabel("Queue Downloader")
        header.setObjectName("Header")
        sub = QLabel("최대한 많은 기능을 지원하기 위해 노력하는 중입니다.")
        sub.setObjectName("Subtle")
        left_root.addWidget(header)
        left_root.addWidget(sub)

        # Input + buttons (Queue tab에 들어갈 것이라 여기서 생성만)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("영상/채널/재생목록 URL — Enter로 추가")
        self.url_input.returnPressed.connect(self.on_add_clicked)

        self.btn_add = QPushButton("대기열 추가")
        self.btn_add.setObjectName("Primary")
        self.btn_add.clicked.connect(self.on_add_clicked)

        self.btn_pick = QPushButton("저장 폴더")
        self.btn_pick.clicked.connect(self.on_pick_folder)

        self.btn_remove = QPushButton("체크 삭제")
        self.btn_remove.clicked.connect(self.on_remove_checked)

        self.btn_clear = QPushButton("전체 비우기")
        self.btn_clear.setObjectName("Danger")
        self.btn_clear.clicked.connect(self.on_clear)

        self.lbl_folder = QLabel("저장 폴더: (미선택)" if not self.save_folder else f"저장 폴더: {self.save_folder}")
        self.lbl_folder.setWordWrap(True)
        self.lbl_folder.setObjectName("Subtle")

        # Download settings group
        gb = QGroupBox("다운로드 옵션")
        form = QFormLayout(gb)

        self.chk_best = QCheckBox("최고 화질(권장)")
        self.chk_best.setChecked(bool(self.force_best))
        self.chk_best.stateChanged.connect(self.on_toggle_best)

        self.cmb_quality = QComboBox()
        self.cmb_quality.addItems(["4320p(8k)", "2160p(4K)", "1440p", "1080p", "720p", "480p", "360p", "240p", "144p"])
        self.set_quality_combo(self.max_quality)
        self.cmb_quality.currentTextChanged.connect(self.on_quality_changed)

        self.chk_thumb = QCheckBox("썸네일 저장")
        self.chk_thumb.setChecked(bool(self.keep_thumb))
        self.chk_thumb.stateChanged.connect(self.on_toggle_thumb)

        self.chk_sub = QCheckBox("자막 저장")
        self.chk_sub.setChecked(bool(self.keep_sub))
        self.chk_sub.stateChanged.connect(self.on_toggle_sub)

        self.chk_logfile = QCheckBox("로그 파일 저장")
        self.chk_logfile.setChecked(bool(self.log_to_file))
        self.chk_logfile.stateChanged.connect(self.on_toggle_logfile)

        # Codec preference
        self.cmb_codec = QComboBox()
        self.cmb_codec.addItems([
            "auto(기본)",
            "H.264 + AAC (MP4 선호)",
            "VP9 + Opus (WebM 선호)",
            "AV1 우선 (가능하면 AV1)",
        ])
        self.set_codec_combo(self.codec_pref)
        self.cmb_codec.currentTextChanged.connect(self.on_codec_changed)

        form.addRow(self.chk_best)
        form.addRow(QLabel("최대 해상도"), self.cmb_quality)
        form.addRow(QLabel("코덱 선호"), self.cmb_codec)
        form.addRow(self.chk_thumb)
        form.addRow(self.chk_sub)
        form.addRow(self.chk_logfile)

        # Cookies group
        gb_cookie = QGroupBox("쿠키(로그인 필요 시)")
        form_c = QFormLayout(gb_cookie)

        self.chk_cookies = QCheckBox("브라우저에서 쿠키 가져오기")
        self.chk_cookies.setChecked(bool(self.use_cookies))
        self.chk_cookies.stateChanged.connect(self.on_toggle_cookies)

        self.cmb_browser = QComboBox()
        self.cmb_browser.addItems(["chrome", "edge", "firefox"])
        idx = self.cmb_browser.findText(self.cookie_browser)
        if idx >= 0:
            self.cmb_browser.setCurrentIndex(idx)
        self.cmb_browser.currentTextChanged.connect(self.on_cookie_browser_changed)

        form_c.addRow(self.chk_cookies)
        form_c.addRow(QLabel("브라우저"), self.cmb_browser)

        # Filter group
        gb_filter = QGroupBox("부분 다운로드/필터")
        form_f = QFormLayout(gb_filter)

        self.chk_ex_shorts = QCheckBox("Shorts 제외")
        self.chk_ex_shorts.setChecked(bool(self.filter_exclude_shorts))
        self.chk_ex_shorts.stateChanged.connect(self.on_filter_changed)

        self.in_date_after = QLineEdit(self.filter_date_after)
        self.in_date_after.setPlaceholderText("YYYY-MM-DD 또는 YYYYMMDD")
        self.in_date_after.textChanged.connect(self.on_filter_changed)

        self.in_date_before = QLineEdit(self.filter_date_before)
        self.in_date_before.setPlaceholderText("YYYY-MM-DD 또는 YYYYMMDD")
        self.in_date_before.textChanged.connect(self.on_filter_changed)

        self.in_kw_in = QLineEdit(self.filter_include_kw)
        self.in_kw_in.setPlaceholderText("예: '강의' 포함만")
        self.in_kw_in.textChanged.connect(self.on_filter_changed)

        self.in_kw_out = QLineEdit(self.filter_exclude_kw)
        self.in_kw_out.setPlaceholderText("예: 'shorts' 제외")
        self.in_kw_out.textChanged.connect(self.on_filter_changed)

        form_f.addRow(self.chk_ex_shorts)
        form_f.addRow(QLabel("업로드 이후(dateafter)"), self.in_date_after)
        form_f.addRow(QLabel("업로드 이전(datebefore)"), self.in_date_before)
        form_f.addRow(QLabel("제목 포함 키워드"), self.in_kw_in)
        form_f.addRow(QLabel("제목 제외 키워드"), self.in_kw_out)

        # Start/Stop (항상 하단 고정)
        self.btn_start = QPushButton("다운로드 시작")
        self.btn_start.setObjectName("Success")
        self.btn_start.clicked.connect(self.on_start)

        self.btn_stop = QPushButton("중지(확장/다운로드)")
        self.btn_stop.setObjectName("Danger")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setEnabled(False)

        # Tabs
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setMovable(False)
        tabs.setTabPosition(QTabWidget.North)

        # ★ 탭 아래 기본 라인 제거(가장 효과 큼)
        tabs.tabBar().setDrawBase(False)
        tabs.tabBar().setExpanding(False)

        # Tab: Queue
        tab_queue = QWidget()
        q = QVBoxLayout(tab_queue)
        q.setContentsMargins(0, 10, 0, 0)
        q.setSpacing(10)
        q.addWidget(self.url_input)

        row_btn = QHBoxLayout()
        row_btn.addWidget(self.btn_add)
        row_btn.addWidget(self.btn_pick)
        q.addLayout(row_btn)

        row_btn2 = QHBoxLayout()
        row_btn2.addWidget(self.btn_remove)
        row_btn2.addWidget(self.btn_clear)
        q.addLayout(row_btn2)

        q.addWidget(self.lbl_folder)
        q.addStretch(1)
        tabs.addTab(tab_queue, "Queue")

        # Tab: Download
        tab_dl = QWidget()
        d = QVBoxLayout(tab_dl)
        d.setContentsMargins(0, 10, 0, 0)
        d.setSpacing(10)
        d.addWidget(gb)
        d.addStretch(1)
        tabs.addTab(tab_dl, "Download")

        # Tab: Advanced
        tab_adv = QWidget()
        a = QVBoxLayout(tab_adv)
        a.setContentsMargins(0, 10, 0, 0)
        a.setSpacing(10)
        a.addWidget(gb_cookie)
        a.addWidget(gb_filter)
        a.addStretch(1)
        tabs.addTab(tab_adv, "Advanced")

        left_root.addWidget(tabs, 1)
        left_root.addWidget(self.btn_start)
        left_root.addWidget(self.btn_stop)

        # --- Right Widgets ---
        right = QWidget()
        r = QVBoxLayout(right)
        r.setContentsMargins(12, 12, 12, 12)
        r.setSpacing(10)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["✔", "제목", "상태"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(20000)

        self.lbl_now = QLabel("현재: -")
        self.lbl_now.setObjectName("Subtle")

        self.pb_file = QProgressBar()
        self.pb_total = QProgressBar()
        self.pb_file.setRange(0, 100)
        self.pb_total.setRange(0, 100)

        eta_row = QHBoxLayout()
        self.lbl_file_eta = QLabel("파일 남은 시간: --:--")
        self.lbl_total_eta = QLabel("전체 남은 시간: 계산 중...")
        self.lbl_file_eta.setObjectName("Subtle")
        self.lbl_total_eta.setObjectName("Subtle")
        eta_row.addWidget(self.lbl_file_eta)
        eta_row.addStretch(1)
        eta_row.addWidget(self.lbl_total_eta)

        self.lbl_status = QLabel("Ready.")
        self.lbl_status.setObjectName("Status")

        r.addWidget(self.table, 5)
        r.addWidget(QLabel("Log"))
        r.addWidget(self.log, 3)
        r.addWidget(self.lbl_now)
        r.addWidget(QLabel("현재 파일"))
        r.addWidget(self.pb_file)
        r.addWidget(QLabel("전체 진행"))
        r.addWidget(self.pb_total)
        r.addLayout(eta_row)
        r.addWidget(self.lbl_status)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([520, 860])

    def _build_menu_toolbar(self):
        menu = self.menuBar()

        m_file = menu.addMenu("파일")
        act_save_txt = QAction("대기열 저장(TXT)...", self)
        act_save_txt.setShortcut(QKeySequence("Ctrl+S"))
        act_save_txt.triggered.connect(self.on_save_queue_txt)
        m_file.addAction(act_save_txt)

        act_load_txt = QAction("대기열 불러오기(TXT)...", self)
        act_load_txt.setShortcut(QKeySequence("Ctrl+L"))
        act_load_txt.triggered.connect(self.on_load_queue_txt)
        m_file.addAction(act_load_txt)

        act_save_log = QAction("로그 저장(txt)...", self)
        act_save_log.triggered.connect(self.on_save_log)
        m_file.addAction(act_save_log)

        act_exit = QAction("종료", self)
        act_exit.setShortcut(QKeySequence.Quit)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        m_view = menu.addMenu("보기")
        self.act_theme_auto = QAction("테마: 자동", self, checkable=True)
        self.act_theme_dark = QAction("테마: 다크(Discord)", self, checkable=True)
        self.act_theme_light = QAction("테마: 라이트", self, checkable=True)

        self.act_theme_auto.triggered.connect(lambda: self.set_theme("auto"))
        self.act_theme_dark.triggered.connect(lambda: self.set_theme("dark"))
        self.act_theme_light.triggered.connect(lambda: self.set_theme("light"))

        m_view.addAction(self.act_theme_auto)
        m_view.addAction(self.act_theme_dark)
        m_view.addAction(self.act_theme_light)

        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_add = QAction("추가", self)
        act_add.setShortcut(QKeySequence("Ctrl+N"))
        act_add.triggered.connect(self.on_add_clicked)
        tb.addAction(act_add)

        act_start = QAction("시작", self)
        act_start.setShortcut(QKeySequence("Ctrl+Enter"))
        act_start.triggered.connect(self.on_start)
        tb.addAction(act_start)

        act_stop = QAction("중지", self)
        act_stop.setShortcut(QKeySequence("Ctrl+D"))
        act_stop.triggered.connect(self.on_stop)
        tb.addAction(act_stop)

        tb.addSeparator()

        act_theme_toggle = QAction("테마 토글", self)
        act_theme_toggle.setShortcut(QKeySequence("Ctrl+T"))
        act_theme_toggle.triggered.connect(self.toggle_theme_quick)
        tb.addAction(act_theme_toggle)

        self._sync_theme_actions()

    # Theme
    def apply_theme(self, mode: str):
        app = QApplication.instance()
        app.setStyle("Fusion")

        mode = (mode or "dark").lower()
        if mode == "dark":
            app.setPalette(palette_dark_discord())
            self.setStyleSheet(QSS_DARK)
        elif mode == "light":
            app.setPalette(palette_light_clean())
            self.setStyleSheet(QSS_LIGHT)
        else:
            app.setPalette(app.style().standardPalette())
            self.setStyleSheet(QSS_LIGHT)

        self.theme_mode = mode
        self._sync_theme_actions()

    def set_theme(self, mode: str):
        self.apply_theme(mode)
        self.settings.setValue("theme_mode", self.theme_mode)

    def toggle_theme_quick(self):
        nxt = {"auto": "dark", "dark": "light", "light": "auto"}[self.theme_mode]
        self.set_theme(nxt)

    def _sync_theme_actions(self):
        self.act_theme_auto.setChecked(self.theme_mode == "auto")
        self.act_theme_dark.setChecked(self.theme_mode == "dark")
        self.act_theme_light.setChecked(self.theme_mode == "light")

    # Options
    def on_toggle_best(self, _):
        self.force_best = self.chk_best.isChecked()
        self.settings.setValue("force_best", self.force_best)
        self.cmb_quality.setEnabled(not self.force_best)

    def quality_to_height(self, text: str) -> int:
        t = (text or "").lower()
        if "4320" in t or "8k" in t:
            return 4320
        if "2160" in t or "4k" in t:
            return 2160
        for n in [1440, 1080, 720, 480, 360, 240, 144]:
            if str(n) in t:
                return n
        return 1080

    def set_quality_combo(self, saved: str):
        saved = (saved or "1080p").lower()
        mapping = {
            "4320p": "4320p(8K)",
            "4k": "2160p(4K)",
            "1440p": "1440p",
            "1080p": "1080p",
            "720p": "720p",
            "480p": "480p",
            "360p": "360p",
            "240p": "240p",
            "144p": "144p",
        }
        want = mapping.get(saved, "1080p")
        idx = self.cmb_quality.findText(want)
        if idx >= 0:
            self.cmb_quality.setCurrentIndex(idx)

    def on_quality_changed(self, text: str):
        h = self.quality_to_height(text)
        self.max_quality = f"{h}p"
        self.settings.setValue("max_quality", self.max_quality)

    def on_toggle_thumb(self, _):
        self.keep_thumb = self.chk_thumb.isChecked()
        self.settings.setValue("keep_thumb", self.keep_thumb)

    def on_toggle_sub(self, _):
        self.keep_sub = self.chk_sub.isChecked()
        self.settings.setValue("keep_sub", self.keep_sub)

    def on_toggle_logfile(self, _):
        self.log_to_file = self.chk_logfile.isChecked()
        self.settings.setValue("log_to_file", self.log_to_file)

    # Cookies
    def on_toggle_cookies(self, _):
        self.use_cookies = self.chk_cookies.isChecked()
        self.settings.setValue("use_cookies", self.use_cookies)

    def on_cookie_browser_changed(self, text: str):
        self.cookie_browser = (text or "chrome").lower()
        self.settings.setValue("cookie_browser", self.cookie_browser)

    # Filters
    def on_filter_changed(self, _=None):
        self.filter_exclude_shorts = self.chk_ex_shorts.isChecked()
        self.filter_date_after = self.in_date_after.text().strip()
        self.filter_date_before = self.in_date_before.text().strip()
        self.filter_include_kw = self.in_kw_in.text().strip()
        self.filter_exclude_kw = self.in_kw_out.text().strip()

        self.settings.setValue("filter_exclude_shorts", self.filter_exclude_shorts)
        self.settings.setValue("filter_date_after", self.filter_date_after)
        self.settings.setValue("filter_date_before", self.filter_date_before)
        self.settings.setValue("filter_include_kw", self.filter_include_kw)
        self.settings.setValue("filter_exclude_kw", self.filter_exclude_kw)

    # Codec preference
    def set_codec_combo(self, saved: str):
        saved = (saved or "auto").lower()
        mapping = {
            "auto": "auto(기본)",
            "h264": "H.264 + AAC (MP4 선호)",
            "vp9": "VP9 + Opus (WebM 선호)",
            "av1": "AV1 우선 (가능하면 AV1)",
        }
        want = mapping.get(saved, "auto(기본)")
        idx = self.cmb_codec.findText(want)
        if idx >= 0:
            self.cmb_codec.setCurrentIndex(idx)

    def on_codec_changed(self, _text: str):
        t = self.cmb_codec.currentText()
        if t.startswith("H.264"):
            self.codec_pref = "h264"
        elif t.startswith("VP9"):
            self.codec_pref = "vp9"
        elif t.startswith("AV1"):
            self.codec_pref = "av1"
        else:
            self.codec_pref = "auto"
        self.settings.setValue("codec_pref", self.codec_pref)

    # Helpers
    def append_log(self, s: str):
        self.log.appendPlainText(s)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def set_status(self, s: str):
        self.lbl_status.setText(s)
        self.statusBar().showMessage(s)

    def render_table_all(self):
        self.table.setUpdatesEnabled(False)
        try:
            self.table.setRowCount(len(self.queue))
            for row, it in enumerate(self.queue):
                it0 = QTableWidgetItem()
                it0.setFlags(it0.flags() | Qt.ItemIsUserCheckable)
                it0.setCheckState(Qt.Checked)
                self.table.setItem(row, 0, it0)
                self.table.setItem(row, 1, QTableWidgetItem(it.title or it.url))
                self.table.setItem(row, 2, QTableWidgetItem(it.status or "Queued"))
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()

    def refresh_state(self):
        expanding = self._pending_count > 0
        downloading = self.worker is not None
        working = expanding or downloading

        can_start = (len(self.queue) > 0) and bool(self.save_folder) and (not working)
        self.btn_start.setEnabled(can_start)
        self.btn_stop.setEnabled(working)

        self.btn_add.setEnabled(not working)
        self.btn_remove.setEnabled(not working)
        self.btn_clear.setEnabled(not working)
        self.btn_pick.setEnabled(not working)
        self.url_input.setEnabled(not working)

        self.lbl_folder.setText("저장 폴더: (미선택)" if not self.save_folder else f"저장 폴더: {self.save_folder}")

        if expanding:
            self.set_status(f"Expanding... collected={self._expanding_collected_count} pending={self._pending_count}")
        elif downloading:
            self.set_status("Downloading...")
        else:
            self.set_status("Ready.")

    # Expand API
    def add_urls_as_queue(self, urls: list[str]):
        urls = [normalize_url(u) for u in urls if normalize_url(u)]
        if not urls:
            return

        fixed = [normalize_channel_to_videos(u) for u in urls]
        self._pending_count += len(fixed)
        self.append_log(f"입력됨: {len(fixed)}개 (pending={self._pending_count})")

        for u in fixed:
            self.expand_worker.request.emit(u)

        self.refresh_state()

    @Slot(int)
    def on_expand_count(self, n: int):
        self._expanding_collected_count = n
        self.refresh_state()

    @Slot(bool, str, list)
    def on_expand_finished_one(self, ok: bool, msg: str, collected: list):
        self.append_log(msg)
        self._pending_count = max(0, self._pending_count - 1)
        self._expanding_collected_count = 0

        added = 0
        for it in collected:
            u = normalize_url(getattr(it, "url", "") or "")
            t = getattr(it, "title", "") or u
            if not u or u in self.url_set:
                continue
            self.url_set.add(u)
            self.queue.append(QueueItem(url=u, title=t, status="Queued"))
            added += 1

        self.append_log(f"확장 반영: +{added}개 (총 {len(self.queue)}개)")
        self.refresh_state()

    @Slot()
    def on_expand_idle(self):
        if self._pending_count == 0:
            self.append_log("확장 idle: 테이블 일괄 렌더링")
            self.render_table_all()
            self.refresh_state()

    # Actions
    def on_pick_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "저장 폴더 선택",
            self.save_folder or os.path.expanduser("~")
        )
        if folder:
            self.save_folder = folder
            self.settings.setValue("save_folder", folder)
            self.refresh_state()

    def on_add_clicked(self):
        url = normalize_url(self.url_input.text())
        if not url:
            QMessageBox.information(self, "안내", "URL을 입력하세요.")
            return
        self.url_input.clear()
        self.add_urls_as_queue([url])

    def on_remove_checked(self):
        rows = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                rows.append(r)

        if not rows:
            QMessageBox.information(self, "안내", "체크된 항목이 없습니다.")
            return

        for r in reversed(rows):
            if 0 <= r < len(self.queue):
                self.url_set.discard(self.queue[r].url)
                self.queue.pop(r)

        self.append_log(f"삭제됨: {len(rows)}개")
        self.render_table_all()
        self.refresh_state()

    def on_clear(self):
        self.table.setRowCount(0)
        self.queue.clear()
        self.url_set.clear()
        self.append_log("대기열 초기화")
        self.refresh_state()

    def build_format_string(self) -> str:
        if self.force_best:
            return "bestvideo+bestaudio/best"
        h = self.quality_to_height(self.max_quality)
        return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"

    def build_format_sort(self) -> list[str] | None:
        # yt-dlp format sorting (CLI: -S / --format-sort)와 대응되는 python 옵션 키: format_sort
        if self.codec_pref == "h264":
            return ["vcodec:h264", "res", "acodec:m4a"]
        if self.codec_pref == "vp9":
            return ["vcodec:vp9", "res", "acodec:opus"]
        if self.codec_pref == "av1":
            return ["vcodec:av01", "res", "acodec"]
        return None

    def build_cookiesfrombrowser(self) -> tuple | None:
        if not self.use_cookies:
            return None
        b = (self.cookie_browser or "chrome").lower()
        return (b, None, None, None)

    def build_filter_opts(self) -> dict:
        opts = {}
        da = safe_date_yyyymmdd(self.filter_date_after)
        db = safe_date_yyyymmdd(self.filter_date_before)

        if self.filter_date_after and not da:
            self.append_log("필터 경고: dateafter 형식이 잘못됨(YYYYMMDD/ YYYY-MM-DD)")
        if self.filter_date_before and not db:
            self.append_log("필터 경고: datebefore 형식이 잘못됨(YYYYMMDD/ YYYY-MM-DD)")

        if da:
            opts["dateafter"] = da
        if db:
            opts["datebefore"] = db
        return opts

    def on_start(self):
        if not self.save_folder:
            QMessageBox.information(self, "안내", "저장 폴더를 먼저 선택하세요.")
            return

        if self._pending_count > 0:
            QMessageBox.information(self, "안내", "현재 채널/재생목록 펼치는 중입니다. 끝난 뒤 시작하세요.")
            return

        idxs = []
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.checkState() == Qt.Checked:
                idxs.append(r)

        if not idxs:
            QMessageBox.information(self, "안내", "체크된 항목이 없습니다.")
            return

        items = []
        for i in idxs:
            qi = self.queue[i]

            if self.filter_exclude_shorts:
                if "/shorts/" in (qi.url or "").lower():
                    continue

            if self.filter_include_kw:
                if self.filter_include_kw.lower() not in (qi.title or "").lower():
                    continue

            if self.filter_exclude_kw:
                if self.filter_exclude_kw.lower() in (qi.title or "").lower():
                    continue

            items.append(qi)

        if not items:
            QMessageBox.information(self, "안내", "필터 결과 다운로드할 항목이 없습니다.")
            return

        log_path = None
        if self.log_to_file:
            log_dir = os.path.join(self.save_folder, "_logs")
            log_path = os.path.join(log_dir, "yt_queue_log.txt")

        fmt = self.build_format_string()
        fmt_sort = self.build_format_sort()
        cookies = self.build_cookiesfrombrowser()
        filter_opts = self.build_filter_opts()

        self.append_log(f"선택된 포맷: {fmt}")
        if fmt_sort:
            self.append_log(f"코덱 선호(format_sort): {fmt_sort}")
        if cookies:
            self.append_log(f"쿠키 사용: {cookies[0]}")
        if filter_opts:
            self.append_log(f"다운로드 필터: {filter_opts}")

        self.pb_file.setValue(0)
        self.pb_total.setValue(0)
        self.lbl_file_eta.setText("파일 남은 시간: --:--")
        self.lbl_total_eta.setText("전체 남은 시간: 계산 중...")
        self.lbl_now.setText("현재: -")

        self.worker_thread = QThread()
        self.worker = DownloadWorker(
            items=items,
            save_folder=self.save_folder,
            keep_thumb=self.keep_thumb,
            keep_sub=self.keep_sub,
            log_path=log_path,
            fmt=fmt,
            format_sort=fmt_sort,
            cookiesfrombrowser=cookies,
            filter_opts=filter_opts
        )

        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)

        self.worker.log.connect(self.append_log)
        self.worker.current_title.connect(lambda t: self.lbl_now.setText(f"현재: {t}"))
        self.worker.file_progress.connect(self.pb_file.setValue)
        self.worker.total_progress.connect(self.pb_total.setValue)
        self.worker.file_eta.connect(lambda s: self.lbl_file_eta.setText(f"파일 남은 시간: {s}"))
        self.worker.total_eta.connect(lambda s: self.lbl_total_eta.setText(f"전체 남은 시간: {s}"))

        self.worker.finished.connect(self.on_download_finished)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()
        self.refresh_state()

    def on_stop(self):
        try:
            self.expand_worker.stop()
        except Exception:
            pass

        self._pending_count = 0
        self._expanding_collected_count = 0

        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass

        try:
            if self.worker_thread and self.worker_thread.isRunning():
                self.worker_thread.quit()
                self.worker_thread.wait(5000)
        except Exception:
            pass

        self.append_log("중지 요청됨(확장/다운로드)")
        self.refresh_state()

    @Slot(bool, str)
    def on_download_finished(self, ok: bool, msg: str):
        self.worker = None
        self.worker_thread = None
        self.refresh_state()

        self.append_log(f"결과: {msg}")
        if ok:
            QMessageBox.information(self, "완료", "다운로드가 완료되었습니다.")
        else:
            QMessageBox.warning(self, "완료", msg)

    def on_save_queue_txt(self):
        path, _ = QFileDialog.getSaveFileName(self, "대기열 저장(TXT)", "", "Text (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            for it in self.queue:
                f.write(it.url + "\n")
        self.append_log(f"대기열 TXT 저장됨: {path}")

    def on_load_queue_txt(self):
        path, _ = QFileDialog.getOpenFileName(self, "대기열 불러오기(TXT)", "", "Text (*.txt)")
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            QMessageBox.warning(self, "오류", f"불러오기 실패: {e}")
            return

        urls = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue

            found = extract_urls_from_text(line)
            if found:
                urls.extend(found)
            else:
                if line.startswith("http"):
                    urls.append(line)

        if not urls:
            QMessageBox.information(self, "안내", "TXT에서 URL을 찾지 못했습니다.")
            return

        self.add_urls_as_queue(urls)

    def on_save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "로그 저장", "", "Text (*.txt)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.log.toPlainText())
        self.append_log(f"로그 저장됨: {path}")


def main():
    crash_fp = _setup_faulthandler()
    qt_fp = _setup_qt_message_log()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    win = MainWindow()
    win.apply_theme(win.theme_mode)
    win.show()

    try:
        code = app.exec()
    finally:
        try:
            qt_fp.write(f"=== qt session end {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            qt_fp.flush()
            qt_fp.close()
        except Exception:
            pass

        try:
            crash_fp.write(f"=== session end {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            crash_fp.flush()
            crash_fp.close()
        except Exception:
            pass

    sys.exit(code)


if __name__ == "__main__":
    main()
