
import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from PyQt6.QtGui import QColor
from speedometer import SpeedometerWidget
from gauge import GaugeWidget
from signal_strength import SignalStrengthWidget

class GaugesWindow(QWidget):
    def __init__(self, target_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Gauges for {target_data['name']}")
        self.target_data = target_data

        layout = QHBoxLayout()

        self.speedometer = SpeedometerWidget()
        self.speedometer.setMinimum(0)
        self.speedometer.setMaximum(1000)
        self.speedometer.setUnits("Mbps")
        layout.addWidget(self.speedometer)

        self.cpu_gauge = GaugeWidget()
        self.cpu_gauge.setMinimum(0)
        self.cpu_gauge.setMaximum(100)
        self.cpu_gauge.setUnits("%")
        layout.addWidget(self.cpu_gauge)

        self.signal_strength = SignalStrengthWidget()
        layout.addWidget(self.signal_strength)

        self.setLayout(layout)
        self.update_gauges(target_data)

    def update_gauges(self, target_data):
        self.speedometer.setValue(target_data.get('network_speed', 0))
        self.cpu_gauge.setValue(target_data.get('cpu_usage', 0))
        self.signal_strength.setStrength(target_data.get('signal_strength', 0))
