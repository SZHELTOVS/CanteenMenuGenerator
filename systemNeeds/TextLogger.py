import sys

class TextLogger:
    """Перехватывает все print() и выводит в виджет Text"""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.config(state="normal")
        self.text_widget.insert("end", message)
        self.text_widget.see("end")
        self.text_widget.config(state="disabled")

    def flush(self):
        pass
