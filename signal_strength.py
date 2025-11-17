
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient
from PyQt6.QtCore import Qt, QRectF

class SignalStrengthWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._strength = 0  # 0 to 5

    def setStrength(self, strength):
        if 0 <= strength <= 5:
            self._strength = strength
            self.update()

    def strength(self):
        return self._strength

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        side = min(rect.width(), rect.height())
        painter.setViewport((rect.width() - side) // 2, (rect.height() - side) // 2, side, side)
        painter.setWindow(0, 0, 100, 100)

        num_bars = 5
        bar_width = 12
        bar_spacing = 8
        total_width = num_bars * bar_width + (num_bars - 1) * bar_spacing
        start_x = (100 - total_width) // 2

        for i in range(num_bars):
            bar_height = 20 + i * 15
            x = start_x + i * (bar_width + bar_spacing)
            y = 100 - bar_height

            if i < self._strength:
                gradient = QLinearGradient(x, y, x, y + bar_height)
                gradient.setColorAt(0, QColor(0, 255, 0, 255))
                gradient.setColorAt(1, QColor(0, 150, 0, 200))
                painter.setBrush(gradient)
                painter.setPen(Qt.PenStyle.NoPen)
            else:
                painter.setBrush(QColor(40, 40, 40))
                painter.setPen(Qt.PenStyle.NoPen)

            painter.drawRect(x, y, bar_width, bar_height)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QWidget()
    layout = QVBoxLayout()

    signal_widget = SignalStrengthWidget()

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(5)
    slider.valueChanged.connect(signal_widget.setStrength)

    layout.addWidget(signal_widget)
    layout.addWidget(slider)
    window.setLayout(layout)
    window.show()
    sys.exit(app.exec())
