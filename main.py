import json
import socketserver
import sys
import socket
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QFileDialog,
    QMessageBox, QFormLayout, QGroupBox, QListView,  QCheckBox, QSizePolicy
)

from datamodel import ListModel, ItemDelegate
from devsinfo import get_devices_info
import pandas as pd
import threading

model = ListModel()


class ClientHandler(socketserver.BaseRequestHandler):

    def handle(self):
        print(f"Client connected: {self.client_address}")

        data = self.request.recv(1024)
        message = data.decode("utf-8")
        json_data = json.loads(message)
        model.add_data(json_data)

        print(f"Client disconnected: {self.client_address}")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class HardwareInfoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_devices_capturing = False
        self.current_file = None
        self.is_running_as_server = False
        self.server = None
        self.devices_info = list()

        self.setWindowTitle("Assreg")
        self.setMinimumWidth(600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.layout.addWidget(QLabel("(<font color='red'>*</font>) Required"))

        # Hardware Info Group
        hw_group = QGroupBox("Device Information")

        # List View
        self.list_view = QListView()
        # self.list_view.setModel(self.model)
        self.list_view.setModel(model)

        # Delegate
        self.delegate = ItemDelegate()
        self.list_view.setItemDelegate(self.delegate)

        # Spacing between items
        self.list_view.setSpacing(4)

        # Title Label
        self.captured_devices_label = QLabel(f"Total Captured: {len(self.devices_info)}")
        font = self.captured_devices_label.font()
        self.captured_devices_label.setFont(font)
        model.data_changed.connect(self.on_data_changed)

        # Hardware Layout
        hw_layout = QVBoxLayout()
        hw_layout.addWidget(self.captured_devices_label)
        hw_layout.addWidget(self.list_view)

        hw_group.setLayout(hw_layout)
        self.layout.addWidget(hw_group)

        # User Input Group
        input_group = QGroupBox("Additional Information")
        input_layout = QFormLayout()

        self.room_number_edit = QLineEdit()
        self.room_number_edit.setPlaceholderText("Enter Room Name/Number")
        input_layout.addRow("Room <font color='red'>*</font>", self.room_number_edit)

        self.allocation_edit = QLineEdit()
        self.allocation_edit.setPlaceholderText("Enter whom this device is allocated to")
        input_layout.addRow("Allocation <font color='red'>*</font>", self.allocation_edit)

        input_group.setLayout(input_layout)
        self.layout.addWidget(input_group)

        server_status = QGroupBox("Server Details")
        server_layout = QHBoxLayout()

        server_address_layout = QFormLayout()
        self.server_address_edit = QLineEdit()
        self.server_address_edit.setPlaceholderText("URL or IP address")
        server_address_layout.addRow("Server Address", self.server_address_edit)

        server_port_layout = QFormLayout()
        self.port_number_edit = QLineEdit()
        self.port_number_edit.setPlaceholderText("Port Number")
        server_port_layout.addRow("Port", self.port_number_edit)
        server_layout.addLayout(server_address_layout)

        server_layout.addLayout(server_port_layout)
        server_status.setLayout(server_layout)
        self.layout.addWidget(server_status)

        # File Selection
        file_layout = QHBoxLayout()

        file_form__layout = QFormLayout()
        self.file_label = QLabel("No file selected")
        file_form__layout.addRow("Output File:", self.file_label)

        self.select_file_button = QPushButton("Select CSV/Excel File")
        self.select_file_button.adjustSize()
        self.select_file_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.select_file_button.clicked.connect(self.select_file)

        file_layout.addLayout(file_form__layout)
        file_layout.addWidget(self.select_file_button)
        self.layout.addLayout(file_layout)

        # Buttons
        main_button_layout = QHBoxLayout()

        self.run_as_server_button = QPushButton("Run as Server")
        self.run_as_server_button.clicked.connect(self.run_as_server)
        main_button_layout.addWidget(self.run_as_server_button)

        self.send_to_server_button = QPushButton("Send to Server")
        self.send_to_server_button.clicked.connect(self.send_info_to_server)
        main_button_layout.addWidget(self.send_to_server_button)

        self.capture_devices_button = QPushButton("Capture Devices")
        self.capture_devices_button.clicked.connect(self.capture_devices_info)
        main_button_layout.addWidget(self.capture_devices_button)

        self.save_to_file_button = QPushButton("Save to File")
        self.save_to_file_button.clicked.connect(self.save_to_file)
        main_button_layout.addWidget(self.save_to_file_button)

        self.layout.addLayout(main_button_layout)

        self.statusBar().showMessage("No Devices captured.")

    def on_data_changed(self, *args):
        self.captured_devices_label.setText(f"Total Captured: {len(args[0])}")

    def create_devices_info_dataframe(self):
        devices_info_df = pd.DataFrame(self.devices_info)
        devices_info_df["Room"] = self.room_number_edit.text()
        devices_info_df["Allocation"] = self.allocation_edit.text()
        return devices_info_df

    def select_file(self):
        filters = "CSV Files (*.csv);;Excel Files (*.xlsx)"

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Output File", "", filters
        )
        if file_path:
            self.current_file = file_path
            self.file_label.setText(file_path)

    def run_as_server(self):
        def get_local_ip():
            # Returns the local IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = "127.0.0.1"
            finally:
                s.close()
            return ip

        server_ip = get_local_ip()
        server_port_number = 0

        if not self.is_running_as_server and not self.server:
            self.is_running_as_server = True
            self.send_to_server_button.setEnabled(False)
            self.run_as_server_button.setText("Stop Server")

            # Run server in a separate thread to avoid blocking UI
            self.server = Server((server_ip, server_port_number), ClientHandler)
            _, server_port_number = self.server.server_address
            self.server_address_edit.setText(server_ip)
            self.port_number_edit.setText(str(server_port_number))
            print("Server Running on:", self.server.server_address)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()

            self.statusBar().showMessage("Running as Server @ {}:{} ...".format(server_ip, server_port_number))

        else:
            self.is_running_as_server = False
            self.send_to_server_button.setEnabled(True)
            self.run_as_server_button.setText("Run as Server")

            # Proper shutdown and cleanup
            if self.server:
                try:
                    self.server.shutdown()
                    self.server.server_close()  # Close the listening socket
                    self.server = None
                    self.statusBar().showMessage("Server stopped!")
                except Exception as e:
                    self.statusBar().showMessage("Error stopping server: {}".format(str(e)))

    def send_info_to_server(self):
        recv_server_ip = "127.0.0.1"
        recv_server_port_number = 500

        recv_server_ip = self.server_address_edit.text()
        recv_server_port_number = self.port_number_edit.text()

        if not model.rowCount():
            QMessageBox.warning(
                self,
                "Nothing to Send",
                "Please 'Capture devices' first, then send to server."
            )
            return

        if not self.room_number_edit.text() and not self.allocation_edit.text():
            QMessageBox.warning(
                self,
                "Missing Info",
                "Please fill Room Number and Allocation."
            )
            return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect((recv_server_ip, recv_server_port_number))
            devices_info_df = self.create_devices_info_dataframe()
            devices_info = json.dumps(devices_info_df.to_dict(orient="records"))
            client.sendall(devices_info.encode("utf-8"))

    def capture_devices_info(self):
        if not self.is_devices_capturing:
            self.is_devices_capturing = True

        self.devices_info = get_devices_info()
        if not self.is_running_as_server:
            self.statusBar().showMessage(f"{len(self.devices_info)} Devices captured.")

        for item in self.devices_info:
            self.delegate.local_serial_numbers.append(item["Serial Number"])
        model.add_data(self.devices_info)
        self.is_devices_capturing = False

    def save_to_file(self):
        if not model.rowCount():
            QMessageBox.warning(
                self,
                "Nothing to Save",
                "Please 'Capture devices' first, then save to file."
            )
            return

        if not self.room_number_edit.text() and not self.allocation_edit.text():
            QMessageBox.warning(
                self,
                "Missing Info",
                "Please fill Room Number and Allocation."
            )
            return

        if not self.current_file:
            save_filename = QFileDialog.getSaveFileName(
                self, "Save File",
                "./untitled.csv",
                "Documents (*.png *.xpm *.jpg)"
            )
            self.current_file = save_filename[0]
            self.file_label.setText(self.current_file)

        # Create DataFrame
        devices_info_df = self.create_devices_info_dataframe()

        ext = Path(self.current_file).suffix.lower()

        file_exists = os.path.exists(self.current_file)
        if file_exists:
            old_devices_info_df = pd.read_csv(self.current_file, keep_default_na=False)
            for row in devices_info_df.to_dict(orient="records"):
                if (row["Serial Number"] in old_devices_info_df["Serial Number"].values
                        or row["Room"] not in old_devices_info_df["Room"].values
                        or row["Allocation"] not in old_devices_info_df["Allocation"].values
                ):
                    old_devices_info_df = old_devices_info_df[
                        old_devices_info_df["Serial Number"] != row["Serial Number"]]

            devices_info_df = pd.concat([old_devices_info_df, devices_info_df], ignore_index=True)

        if ext == ".csv":
            devices_info_df.to_csv(self.current_file, index=False)
        elif ext == ".xlsx":  # and HAS_OPENPYXL:
            devices_info_df.to_excel(self.current_file, index=False)
        else:
            QMessageBox.warning(self, "Error", "Unsupported file type.")
            return

        QMessageBox.information(self, "Success", f"Data saved to {self.current_file}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HardwareInfoApp()
    window.show()


    def on_app_stop():
        if window.is_running_as_server:
            window.server.shutdown()


    app.aboutToQuit.connect(on_app_stop)
    sys.exit(app.exec())
