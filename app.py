import math
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from main import TreeNode, build_distance_matrix, build_tree, read_fasta


class DistanceMatrixModel(QAbstractTableModel):
    def __init__(self, matrix: pd.DataFrame) -> None:
        super().__init__()
        self._matrix = matrix

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._matrix.index)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._matrix.columns)

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid():
            return None

        value = self._matrix.iat[index.row(), index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return "NA" if pd.isna(value) else str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Optional[str]:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._matrix.columns[section])
        return str(self._matrix.index[section])


class TreeView(QWidget):
    """Draws a rooted tree as a rectangular phylogram with a scale bar."""

    ROW_HEIGHT = 34
    MARGIN = 28
    SCALE_BAR_HEIGHT = 44
    MIN_LEAF_FRACTION = 0.05

    def __init__(self) -> None:
        super().__init__()
        self.tree: Optional[TreeNode] = None
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

    def set_tree(self, tree: Optional[TreeNode]) -> None:
        self.tree = tree
        leaf_count = len(tree.leaves()) if tree else 0
        self.setMinimumHeight(
            2 * self.MARGIN + self.SCALE_BAR_HEIGHT + leaf_count * self.ROW_HEIGHT
        )
        self.update()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        if self.tree is None:
            painter.end()
            return

        label_font = QFont(self.font())
        label_font.setPointSizeF(10.5)
        small_font = QFont(self.font())
        small_font.setPointSizeF(8.5)
        label_metrics = QFontMetricsF(label_font)

        leaves = self.tree.leaves()
        label_width = max(
            label_metrics.horizontalAdvance(leaf.name or "") for leaf in leaves
        )
        depths: dict[int, float] = {}
        self._collect_depths(self.tree, 0.0, depths, 0.0)
        # Zero-length leaves would sit on their parent's vertical line, so
        # draw every leaf branch at least a small fraction of the tree depth.
        min_leaf_length = self.MIN_LEAF_FRACTION * (max(depths.values()) or 1.0)
        self._collect_depths(self.tree, 0.0, depths, min_leaf_length)
        max_depth = max(depths.values()) or 1.0

        left = float(self.MARGIN)
        right = self.width() - self.MARGIN - label_width - 12
        top = self.MARGIN + self.ROW_HEIGHT / 2
        x_scale = max(right - left, 40.0) / max_depth

        positions: dict[int, QPointF] = {}
        leaf_rows = {id(leaf): row for row, leaf in enumerate(leaves)}
        self._layout(self.tree, depths, leaf_rows, positions, left, top, x_scale)

        branch_pen = QPen(QColor("#2f5d62"), 2)
        branch_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(branch_pen)
        self._draw_branches(painter, self.tree, positions)

        painter.setFont(small_font)
        painter.setPen(QColor("#8491a2"))
        self._draw_branch_lengths(painter, self.tree, positions)

        painter.setFont(label_font)
        for leaf in leaves:
            point = positions[id(leaf)]
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#287c70"))
            painter.drawEllipse(point, 3.5, 3.5)
            painter.setPen(QColor("#1f2f44"))
            painter.drawText(
                QRectF(
                    point.x() + 10,
                    point.y() - self.ROW_HEIGHT / 2,
                    label_width + 8,
                    self.ROW_HEIGHT,
                ),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                leaf.name or "",
            )

        self._draw_scale_bar(
            painter,
            small_font,
            left,
            top + len(leaves) * self.ROW_HEIGHT,
            x_scale,
            max_depth,
        )
        painter.end()

    def _collect_depths(
        self,
        node: TreeNode,
        depth: float,
        depths: dict[int, float],
        min_leaf_length: float,
    ) -> None:
        depths[id(node)] = depth
        for child in node.children:
            length = child.branch_length
            if child.is_leaf:
                length = max(length, min_leaf_length)
            self._collect_depths(child, depth + length, depths, min_leaf_length)

    def _layout(
        self,
        node: TreeNode,
        depths: dict[int, float],
        leaf_rows: dict[int, int],
        positions: dict[int, QPointF],
        left: float,
        top: float,
        x_scale: float,
    ) -> float:
        if node.is_leaf:
            y = top + leaf_rows[id(node)] * self.ROW_HEIGHT
        else:
            child_ys = [
                self._layout(child, depths, leaf_rows, positions, left, top, x_scale)
                for child in node.children
            ]
            y = (min(child_ys) + max(child_ys)) / 2
        positions[id(node)] = QPointF(left + depths[id(node)] * x_scale, y)
        return y

    def _draw_branches(
        self, painter: QPainter, node: TreeNode, positions: dict[int, QPointF]
    ) -> None:
        if node.is_leaf:
            return
        origin = positions[id(node)]
        child_points = [positions[id(child)] for child in node.children]
        painter.drawLine(
            QPointF(origin.x(), min(point.y() for point in child_points)),
            QPointF(origin.x(), max(point.y() for point in child_points)),
        )
        for child, point in zip(node.children, child_points):
            painter.drawLine(QPointF(origin.x(), point.y()), point)
            self._draw_branches(painter, child, positions)

    def _draw_branch_lengths(
        self, painter: QPainter, node: TreeNode, positions: dict[int, QPointF]
    ) -> None:
        origin = positions[id(node)]
        for child in node.children:
            point = positions[id(child)]
            if point.x() - origin.x() > 28:
                painter.drawText(
                    QRectF(origin.x(), point.y() - 18, point.x() - origin.x(), 15),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    "{:g}".format(round(child.branch_length, 3)),
                )
            self._draw_branch_lengths(painter, child, positions)

    def _draw_scale_bar(
        self,
        painter: QPainter,
        font: QFont,
        left: float,
        y: float,
        x_scale: float,
        max_depth: float,
    ) -> None:
        # Pick a round length close to a fifth of the tree depth.
        target = max_depth / 5
        magnitude = 10 ** math.floor(math.log10(target))
        length = next(
            step * magnitude for step in (1, 2, 5, 10) if step * magnitude >= target
        )
        width = length * x_scale
        y += 8
        painter.setPen(QPen(QColor("#53657a"), 1.5))
        painter.drawLine(QPointF(left, y), QPointF(left + width, y))
        painter.drawLine(QPointF(left, y - 4), QPointF(left, y + 4))
        painter.drawLine(QPointF(left + width, y - 4), QPointF(left + width, y + 4))
        painter.setFont(font)
        painter.drawText(
            QRectF(left, y + 4, max(width, 140), 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "{:g} substitution{}".format(length, "" if length == 1 else "s"),
        )


class PhyloMapperWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PhyloMapper")
        self.resize(1120, 760)
        self.setMinimumSize(760, 560)

        self.sequences: dict[str, str] = {}
        self.matrix: Optional[pd.DataFrame] = None
        self.tree: Optional[TreeNode] = None

        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 28, 36, 28)
        layout.setSpacing(22)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        logo = QLabel("PHYLOMAPPER")
        logo.setObjectName("brand")
        title = QLabel("Sequence distance explorer")
        title.setObjectName("title")
        subtitle = QLabel(
            "Compare aligned DNA sequences, inspect pairwise differences "
            "and plot their phylogeny."
        )
        subtitle.setObjectName("subtitle")
        brand.addWidget(logo)
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch()
        self.open_button = QPushButton("Open FASTA")
        self.open_button.setObjectName("primaryButton")
        self.open_button.clicked.connect(self._choose_fasta)
        header.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header)

        actions = QFrame()
        actions.setObjectName("actionCard")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(18, 14, 18, 14)
        actions_layout.setSpacing(12)
        self.file_label = QLabel("No FASTA file loaded")
        self.file_label.setObjectName("fileLabel")
        self.file_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.method_combo = QComboBox()
        self.method_combo.setObjectName("methodCombo")
        self.method_combo.addItem("UPGMA", "upgma")
        self.method_combo.addItem("Neighbor joining", "nj")
        self.method_combo.currentIndexChanged.connect(self._replot_tree)
        self.analyze_button = QPushButton("Build tree")
        self.analyze_button.setObjectName("secondaryButton")
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self._calculate)
        self.export_button = QPushButton("Export")
        self.export_button.setObjectName("secondaryButton")
        self.export_button.setEnabled(False)
        export_menu = QMenu(self.export_button)
        export_menu.addAction("Distance matrix (CSV)...", self._export_csv)
        self.newick_action = export_menu.addAction(
            "Tree (Newick)...", self._export_newick
        )
        self.image_action = export_menu.addAction(
            "Tree image (PNG)...", self._export_png
        )
        self.export_button.setMenu(export_menu)
        actions_layout.addWidget(self.file_label)
        actions_layout.addWidget(self.method_combo)
        actions_layout.addWidget(self.analyze_button)
        actions_layout.addWidget(self.export_button)
        layout.addWidget(actions)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.sequence_stat = self._make_stat("SEQUENCES", "--")
        self.length_stat = self._make_stat("ALIGNMENT LENGTH", "--")
        self.status_stat = self._make_stat("STATUS", "Waiting for a file")
        stats.addWidget(self.sequence_stat)
        stats.addWidget(self.length_stat)
        stats.addWidget(self.status_stat, stretch=1)
        layout.addLayout(stats)

        self.content = QStackedWidget()
        self.content.setObjectName("content")
        self.empty_state = self._make_empty_state()
        self.content.addWidget(self.empty_state)

        self.tree_view = TreeView()
        tree_scroll = QScrollArea()
        tree_scroll.setObjectName("treeScroll")
        tree_scroll.setWidgetResizable(True)
        tree_scroll.setWidget(self.tree_view)
        self.tree_message = QLabel()
        self.tree_message.setObjectName("emptyDetails")
        self.tree_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tree_message.setWordWrap(True)
        self.tree_stack = QStackedWidget()
        self.tree_stack.addWidget(tree_scroll)
        self.tree_stack.addWidget(self.tree_message)

        self.table = QTableView()
        self.table.setObjectName("matrixTable")
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSortingEnabled(False)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.horizontalHeader().setMinimumSectionSize(92)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(
            self.table.horizontalHeader().ResizeMode.Interactive
        )

        self.results = QTabWidget()
        self.results.setObjectName("results")
        self.results.addTab(self.tree_stack, "Phylogenetic tree")
        self.results.addTab(self.table, "Distance matrix")
        self.content.addWidget(self.results)
        layout.addWidget(self.content, stretch=1)

        self.setCentralWidget(root)

    def _make_stat(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(5)
        heading = QLabel(label)
        heading.setObjectName("statHeading")
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        card_layout.addWidget(heading)
        card_layout.addWidget(value_label)
        card.value_label = value_label
        return card

    def _make_empty_state(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("emptyPanel")
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        heading = QLabel("Start with an aligned FASTA file")
        heading.setObjectName("emptyTitle")
        details = QLabel(
            "Load a .fasta or .fa file to calculate pairwise distances "
            "and plot a phylogenetic tree."
        )
        details.setObjectName("emptyDetails")
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(details)
        return panel

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#root { background: #f4f7fb; color: #182235; }
            QLabel#brand { color: #317c72; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
            QLabel#title { color: #172438; font-size: 27px; font-weight: 700; }
            QLabel#subtitle { color: #6a788b; font-size: 13px; }
            QFrame#actionCard, QFrame#statCard, QFrame#emptyPanel {
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px;
            }
            QLabel#fileLabel { color: #405168; font-size: 13px; }
            QPushButton { border: 0; border-radius: 7px; padding: 10px 16px; font-size: 12px; font-weight: 600; }
            QPushButton#primaryButton { color: white; background: #287c70; }
            QPushButton#primaryButton:hover { background: #216b61; }
            QPushButton#secondaryButton { color: #315b58; background: #e8f2f0; }
            QPushButton#secondaryButton:hover:enabled { background: #d7e9e5; }
            QPushButton:disabled { color: #9aa5b3; background: #edf0f4; }
            QComboBox#methodCombo {
                color: #26364a; background: #ffffff; border: 1px solid #d5dee8;
                border-radius: 7px; padding: 8px 12px; font-size: 12px; min-width: 140px;
            }
            QLabel#statHeading { color: #8491a2; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
            QLabel#statValue { color: #25364c; font-size: 16px; font-weight: 600; }
            QLabel#emptyTitle { color: #26374d; font-size: 18px; font-weight: 650; }
            QLabel#emptyDetails { color: #758398; font-size: 13px; background: #ffffff; }
            QTabWidget#results::pane {
                background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; top: -1px;
            }
            QTabBar::tab {
                background: transparent; color: #6a788b; padding: 9px 18px; font-size: 12px;
                font-weight: 600; border: 0; border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #1f5f56; border-bottom: 2px solid #287c70; }
            QScrollArea#treeScroll { border: 0; background: #ffffff; }
            QTableView#matrixTable { background: #ffffff; border: 0; alternate-background-color: #f8fafc; color: #26364a; }
            QHeaderView::section { background: #f0f5f7; color: #53657a; border: 0; padding: 11px; font-weight: 600; }
            QTableView::item { padding: 8px; border: 0; }
            QTableView::item:selected { background: #d9ece8; color: #173f39; }
            """
        )

    def _choose_fasta(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open aligned FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.fna *.fas);;All files (*)",
        )
        if file_name:
            self.load_fasta(Path(file_name))

    def load_fasta(self, path: Path) -> None:
        try:
            sequences = read_fasta(path)
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could not load FASTA", str(error))
            return

        self.sequences = sequences
        self.matrix = None
        self.tree = None
        lengths = {len(sequence) for sequence in sequences.values()}
        self.file_label.setText(path.name)
        self.sequence_stat.value_label.setText(str(len(sequences)))
        self.length_stat.value_label.setText(
            "{} bp".format(next(iter(lengths))) if len(lengths) == 1 else "Unequal"
        )
        if len(lengths) == 1:
            self.status_stat.value_label.setText("Ready to build tree")
            self.analyze_button.setEnabled(True)
        else:
            self.status_stat.value_label.setText("Sequences need alignment")
            self.analyze_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.content.setCurrentWidget(self.empty_state)

    def _calculate(self) -> None:
        if not self.sequences:
            return
        try:
            self.matrix = build_distance_matrix(self.sequences)
        except ValueError as error:
            QMessageBox.critical(self, "Could not calculate distances", str(error))
            return

        self.table.setModel(DistanceMatrixModel(self.matrix))
        self.table.resizeColumnsToContents()
        self.content.setCurrentWidget(self.results)
        self.results.setCurrentWidget(self.tree_stack)
        self.export_button.setEnabled(True)
        self._replot_tree()

    def _replot_tree(self) -> None:
        if self.matrix is None:
            return
        try:
            self.tree = build_tree(self.matrix, self.method_combo.currentData())
        except ValueError as error:
            self.tree = None
            self.tree_view.set_tree(None)
            self.tree_message.setText(str(error))
            self.tree_stack.setCurrentWidget(self.tree_message)
            self.status_stat.value_label.setText("Distance matrix ready, no tree")
        else:
            self.tree_view.set_tree(self.tree)
            self.tree_stack.setCurrentIndex(0)
            self.status_stat.value_label.setText(
                "{} tree ready".format(self.method_combo.currentText())
            )
        self.newick_action.setEnabled(self.tree is not None)
        self.image_action.setEnabled(self.tree is not None)

    def _save_path(
        self, caption: str, default_name: str, file_filter: str, suffix: str
    ) -> Optional[Path]:
        file_name, _ = QFileDialog.getSaveFileName(
            self, caption, default_name, file_filter
        )
        if not file_name:
            return None
        destination = Path(file_name)
        if destination.suffix.lower() != suffix:
            destination = destination.with_suffix(suffix)
        return destination

    def _export_csv(self) -> None:
        if self.matrix is None:
            return
        destination = self._save_path(
            "Export distance matrix", "distance-matrix.csv", "CSV files (*.csv)", ".csv"
        )
        if destination is None:
            return
        try:
            self.matrix.to_csv(destination, na_rep="NA")
        except OSError as error:
            QMessageBox.critical(self, "Could not export CSV", str(error))
            return
        self.status_stat.value_label.setText("Exported {}".format(destination.name))

    def _export_newick(self) -> None:
        if self.tree is None:
            return
        destination = self._save_path(
            "Export tree", "tree.nwk", "Newick files (*.nwk)", ".nwk"
        )
        if destination is None:
            return
        try:
            destination.write_text(self.tree.to_newick() + "\n", encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Could not export tree", str(error))
            return
        self.status_stat.value_label.setText("Exported {}".format(destination.name))

    def _export_png(self) -> None:
        if self.tree is None:
            return
        destination = self._save_path(
            "Export tree image", "tree.png", "PNG images (*.png)", ".png"
        )
        if destination is None:
            return
        if not self.tree_view.grab().save(str(destination), "PNG"):
            QMessageBox.critical(
                self, "Could not export image", "Failed to write {}".format(destination)
            )
            return
        self.status_stat.value_label.setText("Exported {}".format(destination.name))


def main() -> int:
    app = QApplication(sys.argv)
    window = PhyloMapperWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
