
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QRadialGradient, QPolygonF
from PyQt6.QtCore import Qt, QRectF, QPropertyAnimation, pyqtProperty, QPointF, QEasingCurve
import math

class GaugeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._minimum = 0
        self._maximum = 100
        self._units = "%"

        self.animation = QPropertyAnimation(self, b"animated_value")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def value(self):
        return self._value

    def setValue(self, value):
        if self._minimum <= value <= self._maximum:
            self.animation.stop()
            self.animation.setStartValue(self._value)
            self.animation.setEndValue(value)
            self.animation.start()

    @pyqtProperty(float)
    def animated_value(self):
        return self._value

    @animated_value.setter
    def animated_value(self, value):
        self._value = value
        self.update()

    def setMinimum(self, minimum):
        self._minimum = minimum
        self.update()

    def minimum(self):
        return self._minimum

    def setMaximum(self, maximum):
        self._maximum = maximum
        self.update()

    def maximum(self):
        return self._maximum

    def setUnits(self, units):
        self._units = units
        self.update()

    def units(self):
        return self._units

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        side = min(rect.width(), rect.height())
        painter.setViewport((rect.width() - side) // 2, (rect.height() - side) // 2, side, side)
        painter.setWindow(-120, -120, 240, 240)

        # Background
        gradient = QRadialGradient(0, 0, 120)
        gradient.setColorAt(0, QColor(50, 50, 50))
        gradient.setColorAt(1, QColor(20, 20, 20))
        painter.setBrush(gradient)
        painter.drawEllipse(-120, -120, 240, 240)

        # Gauge
        start_angle = -45
        end_angle = 225
        span_angle = end_angle - start_angle

        painter.setPen(QPen(QColor(0, 150, 255, 50), 15))
        painter.drawArc(-100, -100, 200, 200, start_angle * 16, span_angle * 16)
        
        value_angle = (self._value / (self._maximum - self._minimum)) * span_angle
        painter.setPen(QPen(QColor(0, 150, 255, 200), 15))
        painter.drawArc(-100, -100, 200, 200, start_angle * 16, int(value_angle * 16))


        # Ticks
        painter.setPen(QColor(255, 255, 255))
        for i in range(self._minimum, self._maximum + 1, 10):
            angle = 225 - (i / (self._maximum - self._minimum)) * 270
            x1 = 90 * math.cos(math.radians(angle))
            y1 = 90 * math.sin(math.radians(angle))
            x2 = 100 * math.cos(math.radians(angle))
            y2 = 100 * math.sin(math.radians(angle))
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Value
        font = QFont("Arial", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(-50, -15, 100, 30, Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}{self._units}")
        
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.drawText(-50, 15, 100, 30, Qt.AlignmentFlag.AlignCenter, "CPU")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = QWidget()
    layout = QVBoxLayout()

    gauge = GaugeWidget()
    gauge.setMinimum(0)
    gauge.setMaximum(100)
    gauge.setUnits("%")

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setMinimum(0)
    slider.setMaximum(100)
    slider.valueChanged.connect(gauge.setValue)

    layout.addWidget(gauge)
    layout.addWidget(slider)
    window.setLayout(layout)
    window.show()
    sys.exit(app.exec())
