import os
import string
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QRect,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFileIconProvider,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


# ==========================================
# 1. CẤU TRÚC DỮ LIỆU & TIỆN ÍCH
# ==========================================
def format_bytes(size: int) -> str:
    if size <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(size)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.0f} {units[i]}" if i == 0 else f"{val:.2f} {units[i]}"


def reveal_in_explorer(target_path: str):
    norm_path = os.path.normpath(target_path)
    if os.path.exists(norm_path):
        subprocess.Popen(f'explorer /select,"{norm_path}"')


@dataclass
class FileNode:
    name: str
    path: str
    is_dir: bool
    size: int = 0
    items: int = 0
    parent: Optional["FileNode"] = None
    children: List["FileNode"] = field(default_factory=list)

    def row(self) -> int:
        if self.parent:
            return self.parent.children.index(self)
        return 0


# ==========================================
# 2. WORKER QUÉT Ổ ĐĨA CHẠY NGẦM (QTHREAD)
# ==========================================
class ScanWorker(QObject):
    progress = Signal(int, int, str)  # folders, files, current_path
    finished = Signal(object, int, int, float)  # root_node, folders, files, elapsed
    cancelled = Signal()
    error = Signal(str)

    def __init__(self, root_path: str):
        super().__init__()
        self.root_path = root_path
        self._cancel_event = threading.Event()
        self.folders_count = 0
        self.files_count = 0
        self._last_emit = 0.0

    def stop(self):
        self._cancel_event.set()

    def run(self):
        if not os.path.exists(self.root_path):
            self.error.emit("Đường dẫn không tồn tại.")
            return

        start_time = time.perf_counter()
        self._last_emit = start_time

        root_node = self._scan_dir(self.root_path, parent=None)

        if self._cancel_event.is_set():
            self.cancelled.emit()
            return

        elapsed = time.perf_counter() - start_time
        self.finished.emit(root_node, self.folders_count, self.files_count, elapsed)

    def _scan_dir(self, current_path: str, parent: Optional[FileNode]) -> Optional[FileNode]:
        if self._cancel_event.is_set():
            return None

        name = os.path.basename(current_path) or current_path
        node = FileNode(name=name, path=current_path, is_dir=True, parent=parent)

        now = time.perf_counter()
        if now - self._last_emit > 0.12:
            self._last_emit = now
            self.progress.emit(self.folders_count, self.files_count, current_path)

        try:
            with os.scandir(current_path) as it:
                entries = list(it)
        except OSError:
            return node

        for entry in entries:
            if self._cancel_event.is_set():
                return None
            try:
                # Bỏ qua Symlink / Junction point trên Windows để tránh vòng lặp vô tận
                if entry.is_symlink():
                    continue

                if entry.is_dir(follow_symlinks=False):
                    self.folders_count += 1
                    child_node = self._scan_dir(entry.path, parent=node)
                    if child_node:
                        node.children.append(child_node)
                        node.size += child_node.size
                        node.items += child_node.items + 1
                elif entry.is_file(follow_symlinks=False):
                    self.files_count += 1
                    f_size = entry.stat(follow_symlinks=False).st_size
                    child_file = FileNode(
                        name=entry.name,
                        path=entry.path,
                        is_dir=False,
                        size=f_size,
                        items=0,
                        parent=node,
                    )
                    node.children.append(child_file)
                    node.size += f_size
                    node.items += 1
            except OSError:
                continue

        # Sắp xếp giảm dần theo dung lượng
        node.children.sort(key=lambda x: x.size, reverse=True)
        return node


# ==========================================
# 3. TREE MODEL & THANH TỶ TRỌNG DUNG LƯỢNG
# ==========================================
class DiskTreeModel(QAbstractItemModel):
    HEADERS = ["Tên File / Thư mục", "Dung lượng", "Tỷ trọng (%)", "Số mục con"]

    def __init__(self, root: Optional[FileNode] = None):
        super().__init__()
        self.root_node = root
        self.icon_provider = QFileIconProvider()
        self.folder_icon = self.icon_provider.icon(QFileIconProvider.IconType.Folder)
        self.file_icon = self.icon_provider.icon(QFileIconProvider.IconType.File)

    def set_root(self, root: Optional[FileNode]):
        self.beginResetModel()
        self.root_node = root
        self.endResetModel()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent) or not self.root_node:
            return QModelIndex()

        if not parent.isValid():
            if row == 0:
                return self.createIndex(row, column, self.root_node)
            return QModelIndex()

        parent_node: FileNode = parent.internalPointer()
        if 0 <= row < len(parent_node.children):
            return self.createIndex(row, column, parent_node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        child_node: FileNode = index.internalPointer()
        parent_node = child_node.parent
        if parent_node is None:
            return QModelIndex()
        return self.createIndex(parent_node.row(), 0, parent_node)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if not self.root_node:
            return 0
        if not parent.isValid():
            return 1
        node: FileNode = parent.internalPointer()
        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not self.root_node:
            return None

        node: FileNode = index.internalPointer()
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return node.name
            elif col == 1:
                return format_bytes(node.size)
            elif col == 2:
                total = self.root_node.size or 1
                pct = (node.size / total) * 100
                return f"{pct:.1f}%"
            elif col == 3:
                return f"{node.items:,}" if node.is_dir else "-"

        elif role == Qt.DecorationRole and col == 0:
            return self.folder_icon if node.is_dir else self.file_icon

        elif role == Qt.TextAlignmentRole:
            if col in (1, 3):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            elif col == 2:
                return int(Qt.AlignCenter)

        elif role == Qt.UserRole:
            # Trả về tỷ lệ float (0.0 -> 1.0) cho delegate vẽ thanh progress
            total = self.root_node.size or 1
            return min(node.size / total, 1.0)

        return None


class PercentageBarDelegate(QStyledItemDelegate):
    """Vẽ thanh tỷ trọng dung lượng trực quan ngay trong cột %"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        super().paint(painter, option, index)
        ratio = index.data(Qt.UserRole)
        if ratio is None:
            return

        painter.save()
        rect: QRect = option.rect.adjusted(6, 5, -6, -5)

        # Nền thanh bar
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1e293b"))
        painter.drawRoundedRect(rect, 3, 3)

        # Phần dung lượng chiếm dụng
        fill_width = int(rect.width() * ratio)
        if fill_width > 0:
            fill_rect = QRect(rect.left(), rect.top(), fill_width, rect.height())
            painter.setBrush(QColor("#0284c7"))
            painter.drawRoundedRect(fill_rect, 3, 3)

        # Chữ phần trăm nằm đè lên giữa thanh bar
        painter.setPen(QColor("#f8fafc"))
        painter.drawText(rect, Qt.AlignCenter, f"{ratio * 100:.1f}%")
        painter.restore()


# ==========================================
# 4. CỬA SỔ CHÍNH CỦA ỨNG DỤNG
# ==========================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Disk Tree Analyzer")
        self.resize(1180, 740)

        self.scan_thread: Optional[QThread] = None
        self.scan_worker: Optional[ScanWorker] = None
        self.selected_node: Optional[FileNode] = None

        self._setup_ui()
        self._apply_dark_theme()
        self._load_drives()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 8)
        main_layout.setSpacing(8)

        # --- Top Toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.drive_combo = QComboBox()
        self.drive_combo.setMinimumWidth(85)
        self.drive_combo.currentTextChanged.connect(self._on_drive_changed)

        self.browse_btn = QPushButton("Chọn thư mục...")
        self.browse_btn.clicked.connect(self._on_browse)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Nhập đường dẫn ổ đĩa hoặc thư mục bất kỳ...")

        self.scan_btn = QPushButton("Quét ngay")
        self.scan_btn.setObjectName("PrimaryBtn")
        self.scan_btn.clicked.connect(self._start_scan)

        self.cancel_btn = QPushButton("Dừng")
        self.cancel_btn.setObjectName("DangerBtn")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._stop_scan)

        toolbar.addWidget(QLabel("Ổ đĩa:"))
        toolbar.addWidget(self.drive_combo)
        toolbar.addWidget(self.browse_btn)
        toolbar.addWidget(self.path_input, 1)
        toolbar.addWidget(self.scan_btn)
        toolbar.addWidget(self.cancel_btn)
        main_layout.addLayout(toolbar)

        # --- Split View: Tree View (Trái) & Preview Panel (Phải) ---
        splitter = QSplitter(Qt.Horizontal)

        # Tree View
        self.tree_view = QTreeView()
        self.tree_model = DiskTreeModel()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setItemDelegateForColumn(2, PercentageBarDelegate(self.tree_view))

        header = self.tree_view.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(110)
        header.resizeSection(2, 130)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.tree_view.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.tree_view.doubleClicked.connect(self._on_tree_double_clicked)

        # Preview Panel
        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewPanel")
        preview_frame.setMinimumWidth(310)
        preview_frame.setMaximumWidth(440)
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        preview_layout.setSpacing(10)

        title_lbl = QLabel("Chi tiết mục đang chọn")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        preview_layout.addWidget(title_lbl)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setObjectName("Divider")
        preview_layout.addWidget(line)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setVerticalSpacing(10)

        self.lbl_name = QLabel("-")
        self.lbl_name.setWordWrap(True)
        self.lbl_type = QLabel("-")
        self.lbl_size = QLabel("-")
        self.lbl_pct = QLabel("-")
        self.lbl_items = QLabel("-")
        self.lbl_path = QLabel("-")
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form.addRow("Tên:", self.lbl_name)
        form.addRow("Loại:", self.lbl_type)
        form.addRow("Dung lượng:", self.lbl_size)
        form.addRow("Tỷ trọng:", self.lbl_pct)
        form.addRow("Mục con:", self.lbl_items)
        form.addRow("Đường dẫn:", self.lbl_path)
        preview_layout.addLayout(form)

        preview_layout.addStretch()

        hint_lbl = QLabel("Mẹo: Double-click vào bất kỳ dòng nào bên trái để mở nhanh trong File Explorer.")
        hint_lbl.setWordWrap(True)
        hint_lbl.setObjectName("MutedText")
        preview_layout.addWidget(hint_lbl)

        self.open_explorer_btn = QPushButton("Mở trong File Explorer")
        self.open_explorer_btn.setObjectName("ExplorerBtn")
        self.open_explorer_btn.setEnabled(False)
        self.open_explorer_btn.clicked.connect(self._open_selected_in_explorer)
        preview_layout.addWidget(self.open_explorer_btn)

        splitter.addWidget(self.tree_view)
        splitter.addWidget(preview_frame)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, 1)

        # --- Status Bar ---
        self.status_label = QLabel("Sẵn sàng.")
        self.statusBar().addWidget(self.status_label, 1)

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QLineEdit, QComboBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 5px 9px;
                color: #f8fafc;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #38bdf8;
            }
            QPushButton {
                background-color: #334155;
                border: none;
                border-radius: 5px;
                padding: 6px 14px;
                font-weight: 600;
                color: #ffffff;
            }
            QPushButton:hover { background-color: #475569; }
            QPushButton:disabled { background-color: #1e293b; color: #64748b; }
            QPushButton#PrimaryBtn { background-color: #0284c7; }
            QPushButton#PrimaryBtn:hover { background-color: #0369a1; }
            QPushButton#DangerBtn { background-color: #dc2626; }
            QPushButton#DangerBtn:hover { background-color: #b91c1c; }
            QPushButton#ExplorerBtn { background-color: #16a34a; padding: 9px; }
            QPushButton#ExplorerBtn:hover { background-color: #15803d; }
            QTreeView {
                background-color: #1e293b;
                alternate-background-color: #172033;
                border: 1px solid #334155;
                border-radius: 6px;
                outline: none;
            }
            QTreeView::item { padding: 3px 0; }
            QTreeView::item:selected { background-color: #1d4ed8; color: #ffffff; }
            QHeaderView::section {
                background-color: #0f172a;
                color: #94a3b8;
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid #334155;
                font-weight: 600;
            }
            QFrame#PreviewPanel {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QFrame#Divider { background-color: #334155; max-height: 1px; }
            QLabel#MutedText { color: #94a3b8; font-size: 12px; }
            QStatusBar { background-color: #1e293b; color: #94a3b8; border-top: 1px solid #334155; }
        """)

    def _load_drives(self):
        drives = [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]
        self.drive_combo.addItems(drives)
        if drives:
            self.path_input.setText(drives[0])

    def _on_drive_changed(self, drive: str):
        if drive:
            self.path_input.setText(drive)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục cần quét", self.path_input.text())
        if folder:
            self.path_input.setText(os.path.normpath(folder))

    def _start_scan(self):
        target = self.path_input.text().strip()
        if not target or not os.path.exists(target):
            QMessageBox.warning(self, "Đường dẫn không hợp lệ", "Vui lòng chọn ổ đĩa hoặc thư mục tồn tại.")
            return

        self.scan_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.drive_combo.setEnabled(False)
        self.cancel_btn.setVisible(True)
        self.tree_model.set_root(None)
        self._update_preview(None)
        self.status_label.setText(f"Đang quét: {target}...")

        self.scan_thread = QThread()
        self.scan_worker = ScanWorker(target)
        self.scan_worker.moveToThread(self.scan_thread)

        self.scan_thread.started.connect(self.scan_worker.run)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.cancelled.connect(self._on_scan_cancelled)
        self.scan_worker.error.connect(self._on_scan_error)

        self.scan_worker.finished.connect(self.scan_thread.quit)
        self.scan_worker.cancelled.connect(self.scan_thread.quit)
        self.scan_worker.error.connect(self.scan_thread.quit)
        self.scan_thread.finished.connect(self.scan_thread.deleteLater)

        self.scan_thread.start()

    def _stop_scan(self):
        if self.scan_worker:
            self.scan_worker.stop()
            self.status_label.setText("Đang dừng quá trình quét...")

    def _reset_controls(self):
        self.scan_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.drive_combo.setEnabled(True)
        self.cancel_btn.setVisible(False)

    def _on_scan_progress(self, folders: int, files: int, current_path: str):
        self.status_label.setText(
            f"Đang quét ({folders:,} thư mục, {files:,} file) | {current_path}"
        )

    def _on_scan_finished(self, root_node: FileNode, folders: int, files: int, elapsed: float):
        self._reset_controls()
        self.tree_model.set_root(root_node)
        root_idx = self.tree_model.index(0, 0)
        self.tree_view.expand(root_idx)
        self.tree_view.setCurrentIndex(root_idx)
        self.status_label.setText(
            f"Hoàn tất: {folders:,} thư mục | {files:,} file | Tổng dung lượng: {format_bytes(root_node.size)} | Thời gian: {elapsed:.2f}s"
        )

    def _on_scan_cancelled(self):
        self._reset_controls()
        self.status_label.setText("Đã hủy quá trình quét.")

    def _on_scan_error(self, msg: str):
        self._reset_controls()
        self.status_label.setText(f"Lỗi: {msg}")
        QMessageBox.critical(self, "Lỗi", msg)

    def _on_selection_changed(self, selected, _deselected):
        indexes = selected.indexes()
        if not indexes:
            self._update_preview(None)
            return
        node: FileNode = indexes[0].internalPointer()
        self._update_preview(node)

    def _update_preview(self, node: Optional[FileNode]):
        self.selected_node = node
        if not node or not self.tree_model.root_node:
            self.lbl_name.setText("-")
            self.lbl_type.setText("-")
            self.lbl_size.setText("-")
            self.lbl_pct.setText("-")
            self.lbl_items.setText("-")
            self.lbl_path.setText("-")
            self.open_explorer_btn.setEnabled(False)
            return

        total = self.tree_model.root_node.size or 1
        pct = (node.size / total) * 100

        self.lbl_name.setText(node.name)
        self.lbl_type.setText("Thư mục" if node.is_dir else "Tệp tin")
        self.lbl_size.setText(f"{format_bytes(node.size)} ({node.size:,} bytes)")
        self.lbl_pct.setText(f"{pct:.2f}%")
        self.lbl_items.setText(f"{node.items:,} mục" if node.is_dir else "Không áp dụng")
        self.lbl_path.setText(node.path)
        self.open_explorer_btn.setEnabled(True)

    def _on_tree_double_clicked(self, index: QModelIndex):
        if index.isValid():
            node: FileNode = index.internalPointer()
            reveal_in_explorer(node.path)

    def _open_selected_in_explorer(self):
        if self.selected_node:
            reveal_in_explorer(self.selected_node.path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())