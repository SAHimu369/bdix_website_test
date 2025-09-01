import sys
import os
import requests
import time
import webbrowser
import logging
import traceback
from ping3 import ping, errors
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFileDialog, QProgressBar, QTableWidget, 
                             QTableWidgetItem, QStatusBar, QMessageBox, QHeaderView)
from PyQt5.QtGui import QIcon, QColor, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from openpyxl import Workbook

# ---------------- Enhanced Logging Setup ----------------
def setup_logging():
    logging.basicConfig(
        filename="speed_test.log",
        level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

setup_logging()
logger = logging.getLogger("BDIX Speed Test")

class SpeedTestWorker(QThread):
    update_signal = pyqtSignal(str, float, float)
    progress_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, urls):
        super().__init__()
        self.urls = urls
        self.is_running = True
        logger.info(f"Worker initialized with {len(urls)} URLs")

    def run(self):
        try:
            total_urls = len(self.urls)
            logger.debug(f"Starting test with {total_urls} URLs")
            
            for index, url in enumerate(self.urls):
                if not self.is_running:
                    logger.info("Test stopped by user")
                    break

                try:
                    logger.debug(f"Testing URL {index+1}/{total_urls}: {url}")
                    ping_time = self.test_ping(url)
                    if ping_time is None or ping_time is False:
                        ping_time = -1
                        logger.warning(f"Ping test failed for {url}")

                    download_speed = self.test_download_speed(url)
                    logger.debug(f"Results for {url}: Ping={ping_time}, Speed={download_speed}")
                    self.update_signal.emit(url, ping_time, download_speed)
                except Exception as e:
                    msg = f"Error testing {url}: {str(e)}"
                    logger.error(msg, exc_info=True)
                    self.error_signal.emit(msg)

                progress = int(((index + 1) / total_urls) * 100)
                self.progress_signal.emit(progress)

            logger.info("Test completed successfully")

        except Exception as e:
            msg = f"Worker crashed: {str(e)}"
            logger.critical(msg, exc_info=True)
            self.error_signal.emit(msg)
        finally:
            self.finished_signal.emit()

    def stop(self):
        logger.info("Stopping worker")
        self.is_running = False

    def test_ping(self, url):
        try:
            # Extract hostname from URL
            if '://' in url:
                hostname = url.split('://')[1].split('/')[0]
            else:
                hostname = url.split('/')[0]
                
            # Handle port if present
            if ':' in hostname:
                hostname = hostname.split(':')[0]
                
            logger.debug(f"Pinging hostname: {hostname}")
            result = ping(hostname, unit='ms', timeout=2)
            return result
        except errors.PingError as e:
            logger.warning(f"Ping error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected ping error for {url}: {e}")
            return None

    def test_download_speed(self, url):
        try:
            logger.debug(f"Testing download speed for {url}")
            start_time = time.time()
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()

            content = b""
            content_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if not self.is_running:
                    logger.debug("Download test stopped by user")
                    return 0
                    
                content += chunk
                content_size += len(chunk)
                if content_size >= 102400:  # 100KB
                    break

            elapsed_time = time.time() - start_time
            if elapsed_time < 0.001:
                elapsed_time = 0.001

            speed = (content_size * 8) / (elapsed_time * 1_000_000)  # Mbps
            logger.debug(f"Download speed for {url}: {speed:.2f} Mbps")
            return speed
            
        except requests.RequestException as e:
            msg = f"Request error for {url}: {str(e)}"
            logger.warning(msg)
            self.error_signal.emit(msg)
            return 0
        except Exception as e:
            msg = f"Download test error for {url}: {str(e)}"
            logger.error(msg, exc_info=True)
            self.error_signal.emit(msg)
            return 0

class SpeedTestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Initializing application")
        try:
            self.init_ui()
            self.urls = []
            self.worker = None
            logger.info("Application initialized successfully")
        except Exception as e:
            logger.critical(f"Failed to initialize application: {e}", exc_info=True)
            raise

    def init_ui(self):
        self.setWindowTitle("BDIX Speed Test By SAHimu")
        self.setWindowIcon(self.get_icon())
        self.setGeometry(300, 100, 900, 700)

        # Set application style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2d2d2d;
            }
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            QStatusBar {
                color: #ffffff;
                background-color: #3d3d3d;
            }
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Title label
        self.title_label = QLabel("BDIX Speed Test - Select a file containing URLs")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px; color: #ffffff;")
        self.layout.addWidget(self.title_label)

        # Button layout
        self.button_layout = QHBoxLayout()
        
        self.file_button = QPushButton("Choose File")
        self.file_button.setToolTip("Select a text file containing URLs for testing.")
        self.file_button.setFixedSize(120, 40)
        self.file_button.setStyleSheet(self.get_button_style('#007bff', '#0056b3', '#004494'))
        self.file_button.clicked.connect(self.open_file_dialog)
        self.button_layout.addWidget(self.file_button)

        self.start_button = QPushButton("Start Test")
        self.start_button.setEnabled(False)
        self.start_button.setFixedSize(120, 40)
        self.start_button.setStyleSheet(self.get_button_style('#28a745', '#218838', '#1e7e34'))
        self.start_button.clicked.connect(self.start_test)
        self.button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Test")
        self.stop_button.setEnabled(False)
        self.stop_button.setFixedSize(120, 40)
        self.stop_button.setStyleSheet(self.get_button_style('#dc3545', '#c82333', '#bd2130'))
        self.stop_button.clicked.connect(self.stop_test)
        self.button_layout.addWidget(self.stop_button)

        self.save_button = QPushButton("Save Results")
        self.save_button.setEnabled(False)
        self.save_button.setFixedSize(120, 40)
        self.save_button.setStyleSheet(self.get_button_style('#6c757d', '#5a6268', '#545b62'))
        self.save_button.clicked.connect(self.save_results)
        self.button_layout.addWidget(self.save_button)

        self.layout.addLayout(self.button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setStyleSheet(self.get_progress_bar_style())
        self.progress_bar.setTextVisible(True)
        self.layout.addWidget(self.progress_bar)

        # Results table
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(['No.', 'URL', 'Ping (ms)', 'Download Speed (Mbps)'])
        self.result_table.setRowCount(0)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.cellClicked.connect(self.open_url_in_browser)
        
        # Set column widths
        self.result_table.setColumnWidth(0, 50)   # No.
        self.result_table.setColumnWidth(1, 400)  # URL
        self.result_table.setColumnWidth(2, 100)  # Ping
        self.result_table.setColumnWidth(3, 150)  # Speed
        
        # Enable sorting
        self.result_table.setSortingEnabled(True)
        
        # Add styling
        self.result_table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                gridline-color: #555;
                border: 1px solid #444;
                alternate-background-color: #333;
            }
            QTableWidget::item {
                padding: 5px;
                border-bottom: 1px solid #444;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QTableWidget::item:hover {
                background-color: #3d3d3d;
            }
            QHeaderView::section {
                background-color: #444;
                padding: 5px;
                border: none;
                font-weight: bold;
                color: white;
            }
        """)
        
        self.layout.addWidget(self.result_table)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def get_icon(self):
        try:
            if os.path.exists('icon.png'):
                return QIcon('icon.png')
            else:
                # Create a simple default icon
                from PyQt5.QtGui import QPixmap, QPainter
                pixmap = QPixmap(32, 32)
                pixmap.fill(QColor(53, 53, 53))
                painter = QPainter(pixmap)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(pixmap.rect(), Qt.AlignCenter, "ST")
                painter.end()
                return QIcon(pixmap)
        except Exception as e:
            logger.warning(f"Could not create icon: {e}")
            return QIcon()

    def get_button_style(self, bg_color, hover_color, press_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-size: 14px;
                font-weight: bold;
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
            QPushButton:disabled {{
                background-color: #6c757d;
                color: #ccc;
            }}
        """

    def get_progress_bar_style(self):
        return """
            QProgressBar {
                background-color: #2c2f33;
                border-radius: 10px;
                height: 25px;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 10px;
            }
        """

    def open_file_dialog(self):
        try:
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getOpenFileName(self, "Open URL File", "", "Text Files (*.txt)")
            if file_path:
                logger.info(f"Opening file: {file_path}")
                with open(file_path, 'r', encoding='utf-8') as file:
                    self.urls = [line.strip() for line in file if line.strip()]
                
                if self.urls:
                    self.start_button.setEnabled(True)
                    self.status_bar.showMessage(f"Loaded {len(self.urls)} URLs from {file_path}")
                    logger.info(f"Loaded {len(self.urls)} URLs from {file_path}")
                else:
                    self.status_bar.showMessage("No valid URLs found in the file")
                    logger.warning("No valid URLs found in the file")
                    QMessageBox.warning(self, "No URLs", "The selected file doesn't contain any valid URLs.")
        except Exception as e:
            msg = f"Failed to read file: {str(e)}"
            logger.error(msg, exc_info=True)
            QMessageBox.critical(self, "Error", msg)

    def start_test(self):
        try:
            logger.info("Starting speed test")
            self.result_table.setRowCount(0)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Starting test...")

            if self.urls:
                self.worker = SpeedTestWorker(self.urls)
                self.worker.update_signal.connect(self.display_results)
                self.worker.progress_signal.connect(self.update_progress)
                self.worker.error_signal.connect(self.handle_error)
                self.worker.finished_signal.connect(self.on_test_complete)
                self.worker.start()
                
                self.start_button.setEnabled(False)
                self.stop_button.setEnabled(True)
                self.save_button.setEnabled(False)
                self.status_bar.showMessage("Testing in progress...")
        except Exception as e:
            msg = f"Failed to start test: {str(e)}"
            logger.error(msg, exc_info=True)
            QMessageBox.critical(self, "Error", msg)
            self.start_button.setEnabled(True)

    def stop_test(self):
        try:
            if self.worker and self.worker.isRunning():
                logger.info("Stopping test")
                self.worker.stop()
                self.worker.wait()
                self.status_bar.showMessage("Test stopped by user")
                self.on_test_complete()
        except Exception as e:
            logger.error(f"Error stopping test: {e}", exc_info=True)

    def handle_error(self, error_msg):
        self.status_bar.showMessage(error_msg)
        logger.error(error_msg)

    def display_results(self, url, ping_time, download_speed):
        try:
            row_position = self.result_table.rowCount()
            self.result_table.insertRow(row_position)
            
            # Format values
            ping_display = round(ping_time, 2) if isinstance(ping_time, (int, float)) and ping_time >= 0 else "Error"
            speed_display = round(download_speed, 2) if isinstance(download_speed, (int, float)) and download_speed >= 0 else "Error"
            
            # Add items to table
            self.result_table.setItem(row_position, 0, QTableWidgetItem(str(row_position + 1)))
            self.result_table.setItem(row_position, 1, QTableWidgetItem(url))
            self.result_table.setItem(row_position, 2, QTableWidgetItem(str(ping_display)))
            self.result_table.setItem(row_position, 3, QTableWidgetItem(str(speed_display)))
            
            # Color code based on performance
            if ping_time != -1 and isinstance(ping_time, (int, float)):
                ping_item = self.result_table.item(row_position, 2)
                if ping_time < 100:  # Good ping
                    ping_item.setBackground(QColor(0, 100, 0))
                elif ping_time < 200:  # Average ping
                    ping_item.setBackground(QColor(200, 100, 0))
                else:  # Poor ping
                    ping_item.setBackground(QColor(150, 0, 0))
            
            if download_speed and isinstance(download_speed, (int, float)):
                speed_item = self.result_table.item(row_position, 3)
                if download_speed > 10:  # Good speed
                    speed_item.setBackground(QColor(0, 100, 0))
                elif download_speed > 5:  # Average speed
                    speed_item.setBackground(QColor(200, 100, 0))
                else:  # Poor speed
                    speed_item.setBackground(QColor(150, 0, 0))
        except Exception as e:
            msg = f"Error displaying results: {str(e)}"
            self.status_bar.showMessage(msg)
            logger.error(msg, exc_info=True)
    
    def update_progress(self, progress):
        self.progress_bar.setValue(progress)
        self.progress_bar.setFormat(f"Testing... {progress}%")

    def on_test_complete(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.save_button.setEnabled(True)
        self.progress_bar.setFormat("Test Complete")
        self.status_bar.showMessage("Test completed successfully")
        
        # Ask if user wants to save results
        QTimer.singleShot(1000, self.save_results_popup)

    def save_results_popup(self):
        if self.result_table.rowCount() > 0:
            reply = QMessageBox.question(self, "Test Completed", 
                                        "Do you want to save the results to an Excel file?", 
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.save_results()

    def save_results(self):
        try:
            options = QFileDialog.Options()
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Results", "speed_test_results", "Excel Files (*.xlsx)", options=options)
            if file_path:
                logger.info(f"Saving results to: {file_path}")
                wb = Workbook()
                ws = wb.active
                ws.title = "Speed Test Results"
                ws.append(['No.', 'URL', 'Ping (ms)', 'Download Speed (Mbps)'])

                for row in range(self.result_table.rowCount()):
                    row_data = []
                    for col in range(self.result_table.columnCount()):
                        item = self.result_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    ws.append(row_data)

                wb.save(file_path)
                self.status_bar.showMessage(f"Results saved to {file_path}")
                logger.info(f"Results saved successfully to {file_path}")
        except Exception as e:
            msg = f"Failed to save results: {str(e)}"
            logger.error(msg, exc_info=True)
            QMessageBox.critical(self, "Error", msg)

    def open_url_in_browser(self, row, column):
        try:
            if column == 1:
                url_item = self.result_table.item(row, 1)
                if url_item:
                    url = url_item.text()
                    logger.info(f"Opening URL in browser: {url}")
                    webbrowser.open(url)
        except Exception as e:
            logger.error(f"Error opening URL in browser: {e}", exc_info=True)

    def closeEvent(self, event):
        try:
            if self.worker and self.worker.isRunning():
                logger.info("Stopping worker on application close")
                self.worker.stop()
                self.worker.wait()
        except Exception as e:
            logger.error(f"Error during close event: {e}", exc_info=True)
        finally:
            logger.info("Application closing")
            event.accept()

def main():
    try:
        logger.info("Starting application")
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        
        window = SpeedTestApp()
        window.show()
        
        ret = app.exec_()
        logger.info("Application exited normally")
        sys.exit(ret)
    except Exception as e:
        logger.critical(f"Application crashed: {e}\n{traceback.format_exc()}")
        # Try to show error message if possible
        try:
            error_box = QMessageBox()
            error_box.setIcon(QMessageBox.Critical)
            error_box.setText("Application Error")
            error_box.setInformativeText(str(e))
            error_box.exec_()
        except:
            pass
        sys.exit(1)

if __name__ == '__main__':
    main()