import json
import os
from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QPushButton

# CONFIGURATION
TARGETS_FILE = 'target.json'

class TargetManager:
    def __init__(self):
        self.targets = self.load_targets()

    def load_targets(self):
        if os.path.exists(TARGETS_FILE):
            with open(TARGETS_FILE, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []
        return []

    def save_targets(self):
        with open(TARGETS_FILE, 'w') as f:
            json.dump(self.targets, f, indent=4)

    def add_target(self, name, url, api_key):
        new_id = 1 if not self.targets else max(target['id'] for target in self.targets) + 1
        new_target = {'id': new_id, 'name': name, 'url': url, 'api_key': api_key, 'status': 'unknown', 'ip': 'unknown', 'uptime': 0, 'is_checked': False}
        self.targets.append(new_target)
        self.save_targets()
        return new_target

    def get_target(self, target_id):
        for target in self.targets:
            if target['id'] == target_id:
                return target
        return None

    def update_target(self, target_id, name, url, api_key):
        for target in self.targets:
            if target['id'] == target_id:
                target['name'] = name
                target['url'] = url
                target['api_key'] = api_key
                self.save_targets()
                return target
        return None

    def delete_target(self, target_id):
        initial_len = len(self.targets)
        self.targets = [target for target in self.targets if target['id'] != target_id]
        if len(self.targets) < initial_len:
            self.save_targets()
            return True
        return False

class AddEditTargetDialog(QDialog):
    def __init__(self, parent=None, target=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Target")
        self.setGeometry(200, 200, 400, 250)

        self.layout = QFormLayout()

        self.target_id = target['id'] if target else None

        self.name_input = QLineEdit(target['name'] if target else '')
        self.url_input = QLineEdit(target['url'] if target else '')
        self.api_key_input = QLineEdit(target['api_key'] if target else '')

        self.layout.addRow("Name:", self.name_input)
        self.layout.addRow("URL:", self.url_input)
        self.layout.addRow("API Key:", self.api_key_input)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)
        self.layout.addRow(self.save_button)

        self.setLayout(self.layout)

    def get_data(self):
        return {
            'id': self.target_id,
            'name': self.name_input.text(),
            'url': self.url_input.text(),
            'api_key': self.api_key_input.text(),
        }
