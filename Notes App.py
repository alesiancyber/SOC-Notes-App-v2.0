import re
import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from ipaddress import ip_address, IPv4Address, IPv6Address
from spellchecker import SpellChecker  # Import the SpellChecker class
import json


class NumberKeyPressedSignal(QtCore.QObject):
    number_key_pressed = QtCore.pyqtSignal(int)


class CustomPlainTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spell_checker = SpellChecker()  # Initialize the spell checker
        self.setMouseTracking(True)
        self.setAcceptDrops(False)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.text() == ':':
            self.parent().handle_colon_search()
        elif event.text().isdigit():
            self.parent().from_keyboard = True
            self.parent().select_search_result_by_number(int(event.text()))

        self.highlight_misspelled_words()  # Highlight misspelled words after every keypress

    def highlight_misspelled_words(self):
        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.Document)
        cursor.setCharFormat(QtGui.QTextCharFormat())
        cursor.clearSelection()

        # Find misspelled words and apply red underline
        text = self.toPlainText()
        # Exclude markdown table rows and content within double quotes
        excluded_pattern = r"(?:(?<=\|).*?(?=\|))|(\"[^\"]*\")"
        excluded_matches = [match for match in re.finditer(excluded_pattern, text)]
        excluded_ranges = [(match.start(), match.end()) for match in excluded_matches]

        words = re.findall(r'\b\w+\b', text)
        for word in words:
            start_pos = text.find(word)
            in_excluded_range = any(start <= start_pos < end for start, end in excluded_ranges)
            if not in_excluded_range and self.spell_checker.unknown([word]):
                red_underline = QtGui.QTextCharFormat()
                red_underline.setUnderlineColor(QtCore.Qt.red)
                red_underline.setUnderlineStyle(QtGui.QTextCharFormat.SpellCheckUnderline)

                end_pos = start_pos + len(word)
                cursor.setPosition(start_pos, QtGui.QTextCursor.MoveAnchor)
                cursor.setPosition(end_pos, QtGui.QTextCursor.KeepAnchor)
                cursor.setCharFormat(red_underline)

class CustomInputBox(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

    def insertFromMimeData(self, source):
        if source.hasText():
            text = source.text()
            cursor = self.textCursor()

            if not cursor.atBlockStart():
                cursor.insertBlock()

            cursor.insertText(text)


class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Create input and output boxes
        self.input_box = CustomInputBox()  # Use the new CustomInputBox class
        self.output_box = CustomPlainTextEdit(self)

        # Create search results list widget
        self.search_results_list = QtWidgets.QListWidget()
        self.search_results_list.itemDoubleClicked.connect(self.insert_search_result)
        self.search_results_list.setFixedSize(200, 175)

        # Create button to generate markdown table
        self.generate_button = QtWidgets.QPushButton("Generate Table")
        self.generate_button.clicked.connect(self.generate_table)

        # Create button to clear boxes
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_boxes)

        # Create a button to parse JSON
        self.parse_json_button = QtWidgets.QPushButton("Parse JSON")
        self.parse_json_button.clicked.connect(self.parse_json)

        # Create layout and add widgets
        layout = QtWidgets.QHBoxLayout()
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(QtWidgets.QLabel("Input Data:"))
        left_layout.addWidget(self.input_box)
        left_layout.addWidget(self.generate_button)
        left_layout.addWidget(self.clear_button)
        left_layout.addWidget(QtWidgets.QLabel("Output Table:"))
        left_layout.addWidget(self.output_box)
        left_layout.addWidget(self.parse_json_button)
        self.output_box.number_key_signal = NumberKeyPressedSignal()
        self.output_box.number_key_signal.number_key_pressed.connect(self.select_search_result_by_number)

        layout.addLayout(left_layout)
        layout.addWidget(self.search_results_list)


        self.setLayout(layout)

        # Initialize data and content lists
        self.data = []
        self.content = []
        self.from_keyboard = False
        self.json_object = None

    def parse_json(self):
        json_string = self.input_box.toPlainText()
        try:
            self.json_object = json.loads(json_string)
            pretty_json = json.dumps(self.json_object, indent=4)
            self.output_box.setPlainText(pretty_json)
        except json.JSONDecodeError:
            self.output_box.setPlainText("Invalid JSON string.")
            self.json_object = None

    def search_json(self, json_obj, search_term, path=None):
        if path is None:
            path = []

        results = []

        if isinstance(json_obj, dict):
            for key, value in json_obj.items():
                new_path = list(path)
                new_path.append(key)
                if search_term.lower() in str(key).lower():
                    result = f"{'.'.join(map(str, new_path))}: {value}"
                    results.append(result)
                results.extend(self.search_json(value, search_term, new_path))
        elif isinstance(json_obj, list):
            for i, value in enumerate(json_obj):
                new_path = list(path)
                new_path.append(i)
                results.extend(self.search_json(value, search_term, new_path))
        else:
            if search_term.lower() in str(json_obj).lower():
                result = f"{'.'.join(map(str, path))}: {json_obj}"
                results.append(result)

        return results

    def clear_boxes(self):
        self.input_box.clear()
        self.output_box.clear()
        self.search_results_list.clear()

    def handle_colon_search(self):
        output_text = self.output_box.toPlainText()
        search_term = output_text.lower().split(':')[-1].strip()

        # Search markdown table
        md_search_results = [
            f"{i + 1}. {content}"
            for i, (data, content) in enumerate(zip(self.data, self.content))
            if search_term in data.lower()
        ]

        # Search JSON object
        json_search_results = []
        if self.json_object is not None:
            json_search_results = self.search_json(self.json_object, search_term)
            json_search_results = [f"JSON: {result}" for result in json_search_results]

        # Combine markdown table and JSON search results
        combined_results = md_search_results + json_search_results

        # Update the search results list
        if combined_results:
            self.search_results_list.clear()
            self.search_results_list.addItems(combined_results)
        else:
            self.search_results_list.clear()

        # Update the connection for the itemDoubleClicked signal
        self.search_results_list.itemDoubleClicked.disconnect()
        self.search_results_list.itemDoubleClicked.connect(
            lambda item: self.insert_search_result(item, None)
        )

    def select_search_result_by_number(self, num):
        if num > 0 and num <= self.search_results_list.count():
            item = self.search_results_list.item(num - 1)
            result_text = item.text()

            if result_text.startswith("JSON: "):
                result_text = result_text[6:]  # Remove the "JSON: " prefix
                _, value = result_text.split(': ', 1)
                self.insert_search_result(item, value.strip())
            else:
                self.insert_search_result(item)

            if self.from_keyboard:
                self.output_box.moveCursor(QtGui.QTextCursor.End)
                self.from_keyboard = False

    def insert_search_result(self, item, json_value=None):
        if item is not None:
            result_text = item.text()

            if json_value is not None:
                # Insert only the value from the JSON result
                output_text = self.output_box.toPlainText()
                new_output_text = output_text[:-1] + f' "{json_value}"'
                self.output_box.setPlainText(new_output_text)

            else:
                # Remove the index number for markdown table results
                if result_text.split('. ')[0].isdigit():
                    result_value = result_text.split('. ')[1]

                output_text = self.output_box.toPlainText()
                new_output_text = output_text[:-1] + f' "{result_value}"'
                self.output_box.setPlainText(new_output_text)

            self.search_results_list.clear()

    def insert_search_result(self, item, json_value=None):
        if item is not None:
            result_text = item.text()

            if json_value is not None:
                # Insert only the value from the JSON result
                output_text = self.output_box.toPlainText()
                new_output_text = output_text[:-1] + f' "{json_value}"'
                self.output_box.setPlainText(new_output_text)

            else:
                # Remove the index number for markdown table results
                if result_text.split('. ')[0].isdigit():
                    result_value = result_text.split('. ')[1]

                output_text = self.output_box.toPlainText()
                new_output_text = output_text[:-1] + f' "{result_value}"'
                self.output_box.setPlainText(new_output_text)

            self.search_results_list.clear()

    def handle_search_result_selected(self, item):
        self.insert_search_result(item)

    def generate_hyperlink(self, content):
        url = "https://www.virustotal.com/gui/search/"
        label = "Reputation Check"

        # Check if content is a valid IPv4 or IPv6 address
        try:
            ip = ip_address(content)
            if isinstance(ip, IPv4Address) or isinstance(ip, IPv6Address):
                return f"[{label}]({url}{content})"
        except ValueError:
            pass

        # Check if content is a valid SHA256
        if re.fullmatch(r"[A-Fa-f0-9]{64}", content):
            return f"[{label}]({url}{content})"

        # Check if content is a valid domain
        domain_pattern = r"(?i)(?:https?://)?(?:www\.)?([\w.-]+\.[A-Za-z]{2,})"
        match = re.match(domain_pattern, content)
        if match:
            domain = match.group(1)
            return f"[{label}]({url}{domain})"

        return ""

    def generate_table(self):
        # Clear output box
        self.output_box.clear()

        # Split input text into lines and generate markdown table
        lines = self.input_box.toPlainText().split('\n')
        markdown_table = "| Data | Content | Link |\n| ---- | ------- | ---- |\n"

        for i in range(0, len(lines), 2):
            if i + 1 < len(lines):
                data, content = lines[i], lines[i + 1]
                self.data.append(data)
                self.content.append(content)
                link = self.generate_hyperlink(content)
                markdown_table += f"| {data} | {content} | {link} |\n"

        # Update output box with markdown table
        self.output_box.setPlainText(markdown_table)

        # Add a blank line after the table and set the cursor position
        cursor = self.output_box.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertBlock()
        self.output_box.setTextCursor(cursor)

        # Set focus to the output box
        self.output_box.setFocus()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
