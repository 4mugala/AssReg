import sys
import socket
import platform
import subprocess
import csv
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QFileDialog,
    QMessageBox, QFormLayout, QGroupBox
)
from PySide6.QtCore import Qt
from sysinfo import get_computer_info#, request_elevated_privileges

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    print("openpyxl not installed. Excel support disabled. Install with: pip install openpyxl")



class HardwareInfoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_data_fetched = False
        self.setWindowTitle("Inventorizer")
        self.setMinimumWidth(600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Hardware Info Group
        hw_group = QGroupBox("Hardware Information")
        hw_layout = QFormLayout()

        self.computer_name_edit = QLineEdit()
        self.computer_name_edit.setReadOnly(True)
        hw_layout.addRow("Computer Name:", self.computer_name_edit)

        self.serial_edit = QLineEdit()
        self.serial_edit.setReadOnly(True)
        hw_layout.addRow("System Serial:", self.serial_edit)

        self.monitor_name_edit = QLineEdit()
        self.monitor_name_edit.setReadOnly(True)
        hw_layout.addRow("Monitor Name:", self.monitor_name_edit)

        self.monitor_serial_edit = QLineEdit()
        self.monitor_serial_edit.setReadOnly(True)
        hw_layout.addRow("Monitor Serial:", self.monitor_serial_edit)

        hw_group.setLayout(hw_layout)
        self.layout.addWidget(hw_group)

        # User Input Group
        input_group = QGroupBox("Additional Information")
        input_layout = QFormLayout()

        self.room_edit = QLineEdit()
        input_layout.addRow("Room Number:", self.room_edit)

        self.location_edit = QLineEdit()
        input_layout.addRow("Location:", self.location_edit)

        input_group.setLayout(input_layout)
        self.layout.addWidget(input_group)

        # File Selection
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.select_file_btn = QPushButton("Select CSV/Excel File")
        self.select_file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(QLabel("Output File:"))
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_file_btn)
        self.layout.addLayout(file_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.fetch_btn = QPushButton("Fetch Hardware Info")
        self.fetch_btn.clicked.connect(self.fetch_hardware_info)
        self.save_btn = QPushButton("Save to File")
        self.save_btn.clicked.connect(self.save_to_file)
        # self.save_type_btn =
        btn_layout.addWidget(self.fetch_btn)
        btn_layout.addWidget(self.save_btn)
        self.layout.addLayout(btn_layout)

        self.current_file = None
        # self.fetch_hardware_info()  # Auto fetch on start

    def fetch_hardware_info(self):
        # request_elevated_privileges()
        if not self.is_data_fetched:
            self.is_data_fetched = True
        computer_info = get_computer_info()
        # Computer Name
        computer_name = socket.gethostname()
        self.computer_name_edit.setText(computer_name)

        # System Serial
        serial = computer_info.get("serial_number")
        self.serial_edit.setText(serial or "N/A")

        # Monitor Info (basic, platform specific)
        print(computer_info)
        for monitors in computer_info.get("monitors"):
            self.monitor_name_edit.setText(monitors.get("name") or "N/A")
            self.monitor_serial_edit.setText(monitors.get("serial_number") or "N/A")

    def select_file(self):
        filters = "CSV Files (*.csv);;Excel Files (*.xlsx)"
        if not HAS_OPENPYXL:
            filters = "CSV Files (*.csv)"

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Output File", "", filters
        )
        if file_path:
            self.current_file = file_path
            self.file_label.setText(file_path)

    def save_to_file(self):
        if not self.current_file:
            # QMessageBox.warning(self, "No File", "Please select a file first.")
            save_filename = QFileDialog.getSaveFileName(self, "Save File",
            "./untitled.csv",
            "Documents (*.png *.xpm *.jpg)")
            self.current_file = save_filename[0]
            self.file_label.setText(self.current_file)
            print("Saving to: ", self.current_file)
            # return

        # Gather data
        data = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Computer Name": self.computer_name_edit.text(),
            "System Serial": self.serial_edit.text(),
            "Monitor Name": self.monitor_name_edit.text(),
            "Monitor Serial": self.monitor_serial_edit.text(),
            "Room Number": self.room_edit.text().strip(),
            "Location": self.location_edit.text().strip()
        }

        if not data["Room Number"] or not data["Location"]:
            QMessageBox.warning(self, "Missing Info", "Please fill Room Number and Location.")
            return

        ext = Path(self.current_file).suffix.lower()

        if ext == ".csv":
            self.save_to_csv(data)
        elif ext == ".xlsx" and HAS_OPENPYXL:
            self.save_to_excel(data)
        else:
            QMessageBox.warning(self, "Error", "Unsupported file type.")

    def save_to_csv(self, data):
        file_exists = os.path.exists(self.current_file)
        fieldnames = list(data.keys())

        # Check for duplicates
        if file_exists:
            with open(self.current_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row.get("Computer Name") == data["Computer Name"] and
                            row.get("System Serial") == data["System Serial"]):
                        QMessageBox.information(self, "Duplicate", "This computer record already exists.")
                        return

        mode = 'a' if file_exists else 'w'
        with open(self.current_file, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data)

        QMessageBox.information(self, "Success", f"Data saved to {self.current_file}")

    def save_to_excel(self, data):
        if not HAS_OPENPYXL:
            return

        wb = None
        file_exists = os.path.exists(self.current_file)

        if file_exists:
            wb = openpyxl.load_workbook(self.current_file)
            ws = wb.active
            # Check duplicate
            for row in ws.iter_rows(min_row=2, values_only=True):
                if len(row) > 1 and row[1] == data["Computer Name"] and row[2] == data["System Serial"]:
                    QMessageBox.information(self, "Duplicate", "This computer record already exists.")
                    return
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(list(data.keys()))

        ws.append(list(data.values()))
        wb.save(self.current_file)
        QMessageBox.information(self, "Success", f"Data saved to {self.current_file}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HardwareInfoApp()
    window.show()
    sys.exit(app.exec())
