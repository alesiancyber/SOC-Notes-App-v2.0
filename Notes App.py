import re
import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from ipaddress import ip_address, IPv4Address, IPv6Address
from PyQt5.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, QListWidget
from spellchecker import SpellChecker  # Import the SpellChecker class
import json
import os
from datetime import datetime
from PyQt5.QtWebEngineWidgets import QWebEngineView
import markdown2

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

        words = re.finditer(r'\b\w+\b', text)
        for match in words:
            word = match.group(0)
            start_pos = match.start()
            in_excluded_range = any(start <= start_pos < end for start, end in excluded_ranges)
            if not in_excluded_range and self.spell_checker.unknown([word]):
                red_underline = QtGui.QTextCharFormat()
                red_underline.setUnderlineColor(QtCore.Qt.red)
                red_underline.setUnderlineStyle(QtGui.QTextCharFormat.SpellCheckUnderline)

                end_pos = start_pos + len(word)
                cursor.setPosition(start_pos, QtGui.QTextCursor.MoveAnchor)
                cursor.setPosition(end_pos, QtGui.QTextCursor.KeepAnchor)
                cursor.setCharFormat(red_underline)

    def contextMenuEvent(self, event):
        # Create the default context menu
        menu = self.createStandardContextMenu()

        # Get the cursor position and selected text
        cursor = self.textCursor()
        selected_text = cursor.selectedText()

        # Get spelling suggestions
        suggestions = self.spell_checker.candidates(selected_text)

        # If there are suggestions, add them to the context menu
        if suggestions:
            # Add a separator before the suggestions
            menu.addSeparator()

            # Add suggestions to the context menu
            for suggestion in suggestions:
                action = QtWidgets.QAction(suggestion, menu)
                action.triggered.connect(lambda _, s=suggestion: self.replace_misspelled_word(s))
                menu.addAction(action)

        # Show the context menu
        menu.exec_(event.globalPos())

    def replace_misspelled_word(self, suggestion):
        cursor = self.textCursor()
        cursor.insertText(suggestion)

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
        button_layout = QHBoxLayout()
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

        main_layout.addLayout(top_layout)

        # Add the input box
        self.input_box = QTextEdit(self)
        middle_layout.addWidget(self.input_box)

        # Add the HTML view
        self.html_view = QWebEngineView(self)
        self.html_view.setMinimumSize(400, 300)
        middle_layout.addWidget(self.html_view)

        main_layout.addLayout(middle_layout)

        # Add buttons for building table, clearing, parsing JSON, and saving to file
        self.build_table_button = QPushButton('Build Table', self)
        button_layout.addWidget(self.build_table_button)
        self.build_table_button.clicked.connect(self.build_table)

        self.clear_button = QPushButton('Clear', self)
        button_layout.addWidget(self.clear_button)
        self.clear_button.clicked.connect(self.clear_boxes)

        self.parse_json_button = QPushButton('Parse JSON', self)
        button_layout.addWidget(self.parse_json_button)
        self.parse_json_button.clicked.connect(self.parse_json)

        self.save_button = QPushButton('Save', self)
        button_layout.addWidget(self.save_button)
        self.save_button.clicked.connect(self.save_to_file)

        main_layout.addLayout(button_layout)

        # Add the output box and search results list widget
        self.output_box = CustomPlainTextEdit(self)
        bottom_layout.addWidget(self.output_box)

        self.search_results_list = QListWidget(self)
        bottom_layout.addWidget(self.search_results_list)
        self.search_results_list.itemDoubleClicked.connect(self.insert_search_result)
        self.search_results_list.setMaximumSize(200, 200)

        main_layout.addLayout(bottom_layout)

        # Set the main layout
        self.setLayout(main_layout)

        # Initialize data and content lists
        self.data = []
        self.content = []
        self.from_keyboard = False
        self.json_object = None
        self.json_objects = []

        # Connect the textChanged signal to update_html_view
        self.output_box.textChanged.connect(self.update_html_view)

    def is_json(self, data):
        try:
            json.loads(data)
        except ValueError:
            return False
        return True

    def update_html_view(self):
        markdown_text = self.output_box.toPlainText()

        # Split the text by the delimiter and only process the Markdown part
        delimiter = "---JSON---"
        if delimiter in markdown_text:
            markdown_text = markdown_text.split(delimiter)[0]

        # Continue with the existing code to render the Markdown text as HTML
        html = markdown2.markdown(markdown_text, extras=["tables", "fenced-code-blocks"])
        html = f"""<!DOCTYPE html>
        <html>
        <head>
            <style>
                table {{
                    border-collapse: collapse;
                }}
                th, td {{
                    border: 1px solid black;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
                pre {{
                    background-color: #f8f8f8;
                    border: 1px solid #cccccc;
                    border-radius: 3px;
                    padding: 6px 10px;
                }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        self.html_view.setHtml(html)

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
        # Initialize json_objects as an empty list in the __init__ method
        self.json_objects = []

        # Split input text into lines
        lines = self.input_box.toPlainText().split('\n')

        # Define the regex pattern for JSON data
        pattern = r'\{.*\}'

        # Iterate through lines and parse JSON data if found
        for line in lines:
            json_match = re.search(pattern, line)
            if json_match and self.is_json(json_match.group(0)):
                json_object = json.loads(json_match.group(0))
                self.json_objects.append(json_object)

        if not self.json_objects:
            QtWidgets.QMessageBox.warning(self, "Invalid JSON", "No valid JSON string found in the input box.")

        # Update the output box with the parsed JSON data
        combined_text = self.output_box.toPlainText().split('---JSON---')[0]  # Extract the markdown table

        json_data = ""
        for json_object in self.json_objects:
            formatted_json = json.dumps(json_object, indent=4)
            json_data += f"\n{formatted_json}"

        if json_data:
            combined_text += f"\n---JSON---{json_data}\n---JSON---"

        self.output_box.setPlainText(combined_text)

        # Update the self.json_object for searching
        if len(self.json_objects) > 0:
            self.json_object = self.json_objects[0]
        else:
            self.json_object = None

    def search_json(self, obj, search_term):
        results = []

        def _search(obj, path):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = path + [key]
                    if search_term.lower() in key.lower():  # Search for the search term as a substring in the key
                        results.append((new_path, value))
                    _search(value, new_path)
            elif isinstance(obj, list):
                for index, item in enumerate(obj):
                    new_path = path + [index]
                    _search(item, new_path)

        _search(obj, [])
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

        # Extract the search term
        search_term_pattern = r'([\w]+)\s*:'
        search_term_match = re.search(search_term_pattern, output_text.lower())
        if search_term_match:
            search_term = search_term_match.group(1)
        else:
            search_term = ""

        # Extract data and content from the output text
        table_lines = output_text.strip().split('\n')[2:]
        data_content_pairs = []
        for line in table_lines:
            line_parts = line.split('|')
            if len(line_parts) >= 3:
                data = line_parts[1].strip().lower()
                content = line_parts[2].strip()
                data_content_pairs.append((data, content))

        # Search data for the search term
        md_search_results = [
            content for data, content in data_content_pairs if search_term in data
        ]

        # Search JSON for the search term
        if self.json_object is not None:
            json_search_results = self.search_json(self.json_object, search_term)
            json_search_results = [result[1] for result in json_search_results]
        else:
            json_search_results = []

        # Combine markdown table and JSON search results
        combined_results = [f"{i + 1}. {result}" for i, result in enumerate(md_search_results + json_search_results)]

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

            # Check if the result is from the JSON search
            if json_value is not None:
                # Insert only the value from the JSON result
                output_text = self.output_box.toPlainText()
                new_output_text = output_text[:-1] + f' "{json_value}"'
                self.output_box.setPlainText(new_output_text)

                # Update the markdown table (self.data and self.content)
                # Get the key path from the result_text
                key_path = result_text.split(': ')[0]
                self.data.append(key_path.lower())
                self.content.append(json_value)
            else:
                # Remove the index number for markdown table results
                if result_text.split('. ')[0].isdigit():
                    result_value = result_text.split('. ')[1]

                output_text = self.output_box.toPlainText()
                new_output_text = output_text[:-1] + f' "{result_value}"'
                self.output_box.setPlainText(new_output_text)

            self.search_results_list.clear()
            self.output_box.setPlainText(new_output_text)

    def handle_search_result_selected(self, item):
        self.insert_search_result(item)

    def generate_hyperlink(self, content):
        label = "Reputation Check"

        # Check if content is a valid IPv4 or IPv6 address
        try:
            ip = ip_address(content)
            if isinstance(ip, ipaddress.IPv4Address) or isinstance(ip, ipaddress.IPv6Address):
                url = f"https://www.virustotal.com/gui/ip-address/{content}/detection"
                return f"[{label}]({url})"
        except ValueError:
            pass

        # Check if content is a valid SHA256, SHA1, or MD5 hash
        if re.fullmatch(r"[A-Fa-f0-9]{64}|[A-Fa-f0-9]{40}|[A-Fa-f0-9]{32}", content):
            url = f"https://www.virustotal.com/gui/file/{content}/detection"
            return f"[{label}]({url})"

        # Check if content is a valid domain
        domain_pattern = r"(?i)(?:https?://)?(?:www\.)?([\w.-]+\.[A-Za-z]{2,})"
        match = re.match(domain_pattern, content)
        if match:
            domain = match.group(1)
            url = f"https://www.virustotal.com/gui/domain/{domain}/detection"
            return f"[{label}]({url})"

        return ""

    def build_table(self):
        input_text = self.input_box.toPlainText().strip()
        lines = re.split("\n+", input_text)

        new_table = "| Data | Content | Link |\n| --- | --- | --- |\n"

        i = 0
        while i < len(lines):
            if not lines[i].strip():  # Skip empty lines
                i += 1
                continue

            if "{" in lines[i] and "}" in lines[i]:  # Skip lines containing JSON data
                i += 1
                continue

            data = lines[i].strip()
            i += 1

            content = lines[i].strip() if i < len(lines) and lines[i].strip() else ""
            i += 1

            link = ""
            # placeholder for regex
            if False:  # Replace this condition with the appropriate regex checks
                link = f"[Reputation Check](https://www.virustotal.com/gui/search/{content})"

            new_table += f"| {data} | {content} | {link} |\n"

        # Extract existing table and separate it from the rest of the contents in the output box
        output_text = self.output_box.toPlainText()
        table_pattern = r'(^|\n)(\| Data \| Content \| Link \|\n\| --- \| --- \| --- \|)((\n\|.*\|.*\|.*\|)*)'
        table_match = re.search(table_pattern, output_text)
        if table_match:
            existing_table = table_match.group(0)
            rest_of_contents = output_text.replace(existing_table, '', 1)
        else:
            rest_of_contents = output_text

        # Combine the rebuilt table with the rest of the contents
        combined_text = f"{new_table}\n{rest_of_contents}"

        # Update the output box with the combined text
        self.output_box.setPlainText(combined_text)

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
