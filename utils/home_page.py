"""A quiet introduction shown when no analysis tabs are open."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from utils.app_paths import resource_path


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.addStretch(2)

        content = QWidget()
        content.setObjectName("homeContent")
        content.setMaximumWidth(680)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel()
        logo.setObjectName("homeLogo")
        pixmap = QPixmap(resource_path("window_logo.png"))
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(
                96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(logo)
            layout.addSpacing(12)

        def centered(text, name):
            label = QLabel(text)
            label.setObjectName(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            layout.addWidget(label)

        centered("SeqSketch", "homeTitle")
        layout.addSpacing(6)
        centered("Sequence analysis, simplified.", "homeTagline")
        layout.addSpacing(18)
        centered(
            "A toolkit for everyday bioinformatics, bringing together sequence processing,\n"
            "DNA and protein analysis, alignment, BLAST, primer design and phylogenetics.",
            "homeDescription",
        )
        layout.addSpacing(36)

        features = QGridLayout()
        features.setHorizontalSpacing(48)
        features.setVerticalSpacing(6)
        features.setRowMinimumHeight(2, 26)
        features.setColumnStretch(0, 1)
        features.setColumnStretch(1, 1)
        for index, (title, description) in enumerate((
            ("Sequence processing", "Prepare and organize FASTA sequence data."),
            ("DNA & protein analysis", "Explore nucleotide and protein sequence features."),
            ("Alignment & BLAST", "Compare sequences and search for similar matches."),
            ("Primers & phylogenetics", "Design primers and explore evolutionary relationships."),
        )):
            heading = QLabel(title)
            heading.setObjectName("homeFeatureTitle")
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heading.setWordWrap(True)
            heading.setMinimumHeight(22)
            description_label = QLabel(description)
            description_label.setObjectName("homeFeatureDescription")
            description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            description_label.setWordWrap(True)
            description_label.setMinimumHeight(40)
            # Direct grid rows let Qt share the wrapped title height between
            # both columns instead of clipping a taller translated heading.
            row, column = (index // 2) * 3, index % 2
            features.addWidget(heading, row, column)
            features.addWidget(description_label, row + 1, column)
        layout.addLayout(features)
        layout.addSpacing(36)
        centered("Choose a tool from the menu above to get started.", "homeHint")

        # Fill the available width up to the cap. AlignHCenter would constrain
        # this widget to its size hint, leaving narrow columns even in a wide window.
        content_row = QHBoxLayout()
        content_row.addStretch()
        content_row.addWidget(content, 1)
        content_row.addStretch()
        outer.addLayout(content_row)
        outer.addStretch(3)
