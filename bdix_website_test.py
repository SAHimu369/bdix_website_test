import sys
import requests
import time
import webbrowser
import qtawesome as qta
from ping3 import ping
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QProgressBar, QTableWidget, QTableWidgetItem, QStatusBar, QMessageBox
from PyQt5.QtGui import QIcon, QPalette, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from openpyxl import Workbook

class SpeedTestWorker(QThread):
    update_signal = pyqtSignal(str, float, float)
    progress_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, urls):
        super().__init__()
        self.urls = urls

    def run(self):
        total_urls = len(self.urls)
        for index, url in enumerate(self.urls):
            try:
                ping_time = self.test_ping(url)
                if ping_time is None:
                    ping_time = -1
                
                download_speed = self.test_download_speed(url)
                self.update_signal.emit(url, ping_time, download_speed)
            except Exception as e:
                self.error_signal.emit(f"Error testing {url}: {e}")
            
            progress = int(((index + 1) / total_urls) * 100)
            self.progress_signal.emit(progress)
            
        self.finished_signal.emit()

    def test_ping(self, url):
        hostname = url.split("//")[-1].split("/")[0]
        return ping(hostname)

    def test_download_speed(self, url):
        try:
            start_time = time.time()
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            total_bytes = sum(len(chunk) for chunk in response.iter_content(chunk_size=8192))
            elapsed_time = time.time() - start_time
            return (total_bytes * 8) / (elapsed_time * 1_000_000)
        except requests.RequestException as e:
            self.error_signal.emit(f"Request error: {e}")
            return 0

class SpeedTestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BDIX Speed Test By SAHimu")
        self.setWindowIcon(QIcon('icon.png'))
        self.setGeometry(540, 100, 460, 600)

        palette = QPalette()
        palette.setColor(QPalette.Background, QColor(53, 53, 53))
        palette.setColor(QPalette.Foreground, QColor(255, 255, 255))
        self.setPalette(palette)

        self.label = QLabel("Select a file to test URLs", self)
        self.label.setAlignment(Qt.AlignCenter)

        self.file_button = QPushButton("Choose File", self)
        self.file_button.setToolTip("Select a text file containing URLs for testing.")
        self.file_button.setFixedSize(127, 36)
        self.file_button.setStyleSheet(self.get_button_style('#007bff', '#0056b3', '#004494'))
        self.file_button.clicked.connect(self.open_file_dialog)

        self.start_button = QPushButton("Start Test", self)
        self.start_button.setEnabled(False)
        self.start_button.setFixedSize(127, 36)
        self.start_button.setStyleSheet(self.get_button_style('#28a745', '#218838', '#1e7e34'))
        self.start_button.clicked.connect(self.start_test)

        self.save_button = QPushButton("Save Results", self)
        self.save_button.setEnabled(False)
        self.save_button.setFixedSize(127, 36)
        self.save_button.setStyleSheet(self.get_button_style('#6c757d', '#5a6268', '#545b62'))
        self.save_button.clicked.connect(self.save_results)

        self.result_table = QTableWidget(self)
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(['No.', 'URL', 'Ping (ms)', 'Download Speed (Mbps)'])
        self.result_table.setRowCount(0)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.cellClicked.connect(self.open_url_in_browser)
        
        # Add hover effect styling
        self.result_table.setStyleSheet("""
            QTableWidget::item:hover {
                background-color: #4CAF50;
                color: white;
            }
        """)
        
        # Enable sorting on the table
        self.result_table.setSortingEnabled(True)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setStyleSheet(self.get_progress_bar_style())
        self.progress_bar.setTextVisible(True)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.file_button)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.save_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.result_table)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.urls = []

    def open_file_dialog(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Open URL File", "", "Text Files (*.txt)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as file:
                self.urls = [line.strip() for line in file if line.strip()]
            self.start_button.setEnabled(True)

            # Display file selected notification
            self.display_file_selected_notification(file_path)

    def display_file_selected_notification(self, file_path):
        # Create a label to show the selected file path
        self.file_selected_label = QLabel("File select", self)
        self.file_selected_label.setAlignment(Qt.AlignCenter)
        self.file_selected_label.setStyleSheet("color: #28a745; font-size: 14px; padding: 5px;")
        
        # Add label to layout (position it under the buttons)
        self.layout().addWidget(self.file_selected_label)
        
        # Optionally, set a timer to hide the notification after 5 seconds
        QTimer.singleShot(9000, self.remove_file_selected_notification)

    def remove_file_selected_notification(self):
        if hasattr(self, 'file_selected_label'):
            self.file_selected_label.deleteLater()

    def get_button_style(self, bg_color, hover_color, press_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-size: 14px;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {press_color};
            }}
        """

    def get_progress_bar_style(self):
        return """
            QProgressBar {
                background-color: #2c2f33;
                border-radius: 10px;
                height: 36px;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 10px;
            }
            QProgressBar::chunk:disabled {
                background-color: #6c757d;
            }
            QProgressBar::indicator {
                border-radius: 10px;
            }
        """

    def start_test(self):
        self.result_table.setRowCount(0)
        self.progress_bar.setValue(0)

        if self.urls:
            self.worker = SpeedTestWorker(self.urls)
            self.worker.update_signal.connect(self.display_results)
            self.worker.progress_signal.connect(self.update_progress)
            self.worker.finished_signal.connect(self.on_test_complete)
            self.worker.start()
            self.start_button.setEnabled(False)

    def display_results(self, url, ping_time, download_speed):
        row_position = self.result_table.rowCount()
        self.result_table.insertRow(row_position)
        
        # Round the ping time and download speed to 2 decimal places
        ping_time = round(ping_time, 2) if ping_time != -1 else "Error"
        download_speed = round(download_speed, 2) if download_speed else "Error"
        
        self.result_table.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1)))
        self.result_table.setItem(row_position, 1, QTableWidgetItem(url))
        self.result_table.setItem(row_position, 2, QTableWidgetItem(str(ping_time) if ping_time != -1 else "Error"))
        self.result_table.setItem(row_position, 3, QTableWidgetItem(str(download_speed) if download_speed else "Error"))
        self.result_table.resizeColumnsToContents()
    
    def update_progress(self, progress):
        self.progress_bar.setValue(progress)

    def on_test_complete(self):
        self.start_button.setEnabled(True)
        self.save_button.setEnabled(True)  # Enable the Save button once the test is completed
        self.save_results_popup()

    def save_results_popup(self):
        reply = QMessageBox.question(self, "Test Completed", "Do you want to save the results?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.save_results()

    def save_results(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Results", "", "Excel Files (*.xlsx)", options=options)
        if file_path:
            wb = Workbook()
            ws = wb.active
            ws.append(['No.', 'URL', 'Ping (ms)', 'Download Speed (Mbps)'])

            for row in range(self.result_table.rowCount()):
                row_data = [self.result_table.item(row, col).text() for col in range(self.result_table.columnCount())]
                ws.append(row_data)

            wb.save(file_path)

    def open_url_in_browser(self, row, column):
        url = self.result_table.item(row, 1).text()
        webbrowser.open(url)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SpeedTestApp()
    window.show()
    sys.exit(app.exec_())
