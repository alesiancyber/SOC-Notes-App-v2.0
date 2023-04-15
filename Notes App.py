import re
import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from ipaddress import ip_address, IPv4Address, IPv6Address
from PyQt5.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, QListWidget
from spellchecker import SpellChecker  # Import the SpellChecker class
import json
import os
from datetime import datetime

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

        self.setWindowTitle('Notes App')
        self.setGeometry(100, 100, 1200, 800)

        # Set up layout
        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        middle_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # Add QLineEdit fields for customer name, alert name, and alert link
        self.customer_name_input = QLineEdit(self)
        self.customer_name_input.setPlaceholderText('Customer Name')
        top_layout.addWidget(self.customer_name_input)

        self.alert_name_input = QLineEdit(self)
        self.alert_name_input.setPlaceholderText('Alert Name')
        top_layout.addWidget(self.alert_name_input)

        self.alert_link_input = QLineEdit(self)
        self.alert_link_input.setPlaceholderText('Alert Link')
        top_layout.addWidget(self.alert_link_input)

        main_layout.addLayout(top_layout)  # Move the top_layout here

        # Add the input box
        self.input_box = QTextEdit(self)
        main_layout.addWidget(self.input_box)

        # Add buttons for building table, clearing, parsing JSON, and saving to file
        self.build_table_button = QPushButton('Build Table', self)
        middle_layout.addWidget(self.build_table_button)
        self.build_table_button.clicked.connect(self.build_table)

        self.clear_button = QPushButton('Clear', self)
        middle_layout.addWidget(self.clear_button)
        self.clear_button.clicked.connect(self.clear_boxes)

        self.parse_json_button = QPushButton('Parse JSON', self)
        middle_layout.addWidget(self.parse_json_button)
        self.parse_json_button.clicked.connect(self.parse_json)

        self.save_button = QPushButton('Save', self)
        middle_layout.addWidget(self.save_button)
        self.save_button.clicked.connect(self.save_to_file)

        # Add the output box and search results list widget
        self.output_box = CustomPlainTextEdit(self)
        bottom_layout.addWidget(self.output_box)

        self.search_results_list = QListWidget(self)
        bottom_layout.addWidget(self.search_results_list)
        self.search_results_list.itemDoubleClicked.connect(self.insert_search_result)

        # Add the layouts to the main layout
        main_layout.addLayout(middle_layout)
        main_layout.addLayout(bottom_layout)

        # Set the main layout
        self.setLayout(main_layout)

        # Initialize data and content lists
        self.data = []
        self.content = []
        self.from_keyboard = False
        self.json_object = None

    def save_to_file(self):
        try:
            customer_name = self.customer_name_input.text().strip()
            alert_name = self.alert_name_input.text().strip()
            alert_link = self.alert_link_input.text().strip()

            if not customer_name or not alert_name or not alert_link:
                QMessageBox.warning(self, "Warning", "Please fill in all required fields.")
                return

            # Create the directories if they don't exist
            documents_folder = os.path.expanduser("~/Documents")
            case_files_folder = os.path.join(documents_folder, "Case Files")
            month_year_folder = os.path.join(case_files_folder, f"{datetime.now().strftime('%B %Y')}")

            for folder in [case_files_folder, month_year_folder]:
                if not os.path.exists(folder):
                    os.makedirs(folder)

            # Save the file
            output_text = self.output_box.toPlainText()
            file_content = f"{alert_link}\n\n{output_text}"
            file_name = f"{customer_name}_{alert_name}_{datetime.now().strftime('%m-%d-%Y')}.md"
            file_path = os.path.join(month_year_folder, file_name)

            with open(file_path, "w") as file:
                file.write(file_content)

            QMessageBox.information(self, "Success", f"File saved at {file_path}")
        except Exception as e:
            import traceback
            print("Error in save_to_file:", traceback.format_exc())
            QMessageBox.critical(self, "Error", "An error occurred while saving the file.")

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
                    result = (f"{'.'.join(map(str, new_path))[5:]}", value)
                    results.append(result)
                results.extend(self.search_json(value, search_term, new_path))
        elif isinstance(json_obj, list):
            for i, value in enumerate(json_obj):
                new_path = list(path)
                new_path.append(i)
                results.extend(self.search_json(value, search_term, new_path))
        else:
            if search_term.lower() == str(json_obj).lower():
                result = (f"{'.'.join(map(str, path))[5:]}", json_obj)
                results.append(result)

        return results

    def get_json_value(self, json_obj, keys):
        current_value = json_obj
        for key in keys:
            try:
                key = int(key)
            except ValueError:
                pass

            current_value = current_value[key]

        return current_value

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
            json_search_results = [result[1] for result in json_search_results]

        # Combine markdown table and JSON search results
        combined_results = md_search_results + json_search_results

        # Add numbering to JSON results and limit combined results to 9
        combined_results = combined_results[:9]
        json_index_offset = len(md_search_results)
        for i, result in enumerate(json_search_results):
            if json_index_offset + i < 9:
                combined_results[json_index_offset + i] = f"{json_index_offset + i + 1}. {result}"

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
                key_path, value = result_text.split(': ', 1)
                keys = key_path.split('.')
                value = self.get_json_value(self.json_object, keys)
                self.insert_search_result(item, value)
            else:
                self.insert_search_result(item)

            if self.from_keyboard:
                self.output_box.moveCursor(QtGui.QTextCursor.End)
                self.from_keyboard = False

    def insert_search_result(self, item, json_value=None):
        if item is not None:
            result_text = item.text()

            if result_text.startswith("JSON: "):
                result_text = result_text[6:]  # Remove the "JSON: " prefix
                key_path, value = result_text.split(': ', 1)
                keys = key_path.split('.')
                value = self.get_json_value(self.json_object, keys)
                json_value = value

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

    def build_table(self):
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
