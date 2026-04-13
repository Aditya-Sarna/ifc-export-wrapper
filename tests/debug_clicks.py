"""Diagnostic: trace mouse clicks to find what widget receives them."""
import sys, os
os.environ['PYTHONUNBUFFERED'] = '1'
sys.path.insert(0, '/Users/adityasarna/osd/Osdag/src')

from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QEvent

_orig_event = QWidget.event

def _trace_event(self, event):
    if event.type() == QEvent.MouseButtonPress:
        cls = type(self).__name__
        name = self.objectName()
        geo = self.geometry()
        vis = self.isVisible()
        en = self.isEnabled()
        parent_cls = type(self.parent()).__name__ if self.parent() else "None"
        print(f'[MOUSE] {cls}({name}) parent={parent_cls} geo={geo.x()},{geo.y()},{geo.width()}x{geo.height()} vis={vis} en={en}', flush=True)
    return _orig_event(self, event)

QWidget.event = _trace_event

from osdag_gui.__main__ import main
main()
