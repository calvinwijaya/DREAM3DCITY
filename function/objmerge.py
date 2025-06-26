import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QVBoxLayout, QHBoxLayout
)
from PyQt5.QtGui import QFont

class OBJMerger(QWidget):
    def __init__(self):
        super().__init__()

        self.obj1_path = QLineEdit()
        self.obj2_path = QLineEdit()
        self.output_path = QLineEdit()
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)

        self.init_ui()

    def _bold_label(self, text):
        label = QLabel(text)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        return label

    def init_ui(self):
        layout = QVBoxLayout()

        # Input OBJ 1
        layout.addWidget(self._bold_label("Input OBJ 1"))
        row1 = QHBoxLayout()
        row1.addWidget(self.obj1_path)
        btn1 = QPushButton("Browse")
        btn1.clicked.connect(self.browse_obj1)
        row1.addWidget(btn1)
        layout.addLayout(row1)

        # Input OBJ 2
        layout.addWidget(self._bold_label("Input OBJ 2"))
        row2 = QHBoxLayout()
        row2.addWidget(self.obj2_path)
        btn2 = QPushButton("Browse")
        btn2.clicked.connect(self.browse_obj2)
        row2.addWidget(btn2)
        layout.addLayout(row2)

        # Output path
        layout.addWidget(self._bold_label("Select Output Directory and Filename"))
        row3 = QHBoxLayout()
        row3.addWidget(self.output_path)
        btn3 = QPushButton("Browse")
        btn3.clicked.connect(self.browse_output)
        row3.addWidget(btn3)
        layout.addLayout(row3)

        # Merge button
        self.merge_btn = QPushButton("Merge OBJs")
        self.merge_btn.setFont(QFont("Arial", 11, QFont.Bold))
        self.merge_btn.setStyleSheet("padding: 10px;")
        self.merge_btn.clicked.connect(self.merge_objs)
        layout.addWidget(self.merge_btn)

        # Log console
        layout.addWidget(self._bold_label("Log Output"))
        layout.addWidget(self.log_console)

        self.setLayout(layout)

    def browse_obj1(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select OBJ 1", "", "OBJ Files (*.obj)")
        if path:
            self.obj1_path.setText(path)

    def browse_obj2(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select OBJ 2", "", "OBJ Files (*.obj)")
        if path:
            self.obj2_path.setText(path)

    def browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Output OBJ File", "", "OBJ Files (*.obj)")
        if path:
            self.output_path.setText(path)

    def merge_objs(self):
        path1 = self.obj1_path.text()
        path2 = self.obj2_path.text()
        output_path = self.output_path.text()

        if not path1 or not path2 or not output_path:
            self.log_console.append("Please select both OBJ files and output path.")
            return

        try:
            with open(path1, "r") as f1, open(path2, "r") as f2:
                lines1 = f1.readlines()
                lines2 = f2.readlines()

            vertices = []
            faces = []
            vertex_offset = 0

            # Read OBJ 1
            for line in lines1:
                if line.startswith("v "):
                    vertices.append(line)
                elif line.startswith("f "):
                    faces.append(line)

            vertex_offset = len(vertices)

            # Read OBJ 2 and adjust face indices
            for line in lines2:
                if line.startswith("v "):
                    vertices.append(line)
                elif line.startswith("f "):
                    parts = line.strip().split()
                    new_face = "f " + " ".join(
                        str(int(p.split("/")[0]) + vertex_offset) for p in parts[1:]
                    )
                    faces.append(new_face + "\n")

            # Write merged OBJ
            with open(output_path, "w") as fout:
                fout.writelines(vertices)
                fout.writelines(faces)

            self.log_console.append(f"Successfully merged and saved to {output_path}")

        except Exception as e:
            self.log_console.append(f"Error: {str(e)}")