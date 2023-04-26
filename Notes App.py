import re
import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from ipaddress import ip_address, IPv4Address, IPv6Address
from PyQt5.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit, QMessageBox, QListWidget, \
    QApplication, QMenu, QPlainTextEdit
from spellchecker import SpellChecker  # Import the SpellChecker class
import json
import os
from datetime import datetime
from PyQt5.QtWebEngineWidgets import QWebEngineView
import markdown2
from PyQt5.QtGui import QTextCursor, QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt5.QtCore import Qt, QRect
import string


class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super(SpellCheckHighlighter, self).__init__(parent)
        self.spell_checker = SpellChecker()

    def highlightBlock(self, text):
        text = text.strip()

        # Ignore JSON
        if text.startswith("---JSON---"):
            return

        # Ignore Markdown tables
        if text.startswith("|"):
            return

        # Ignore text within quotes
        text = re.sub(r'".*?"', '', text)

        if text:
            words = self.spell_checker.split_words(text)
            for word in words:
                if self.spell_checker.unknown([word]):
                    format = QTextCharFormat()
                    format.setUnderlineColor(QColor(Qt.red))
                    format.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
                    index = text.index(word)
                    self.setFormat(index, len(word), format)


class CustomPlainTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spell_check_highlighter = SpellCheckHighlighter(self.document())
        self.colon_pressed = False  # Add a flag to track the colon keypress

    def keyPressEvent(self, event):
        stripped_text = ""

        if event.text() == ':':
            super().keyPressEvent(event)
            self.colon_pressed = True

            cursor_position = self.textCursor().position()
            input_text = self.toPlainText()

            # Extract the word before the colon using regex
            match = re.search(r'(\S+)\s*:$', input_text[:cursor_position])
            if match:
                stripped_text = match.group(1)
            else:
                stripped_text = ""

            print(f"Stripped text: {stripped_text}")
            self.parent().search_key_value_pairs(stripped_text)

            cursor_position = self.textCursor().position()
            print(f"Cursor position: {cursor_position}")

            # Get the position of the beginning of the current line
            current_line_position = input_text.rfind('\n', 0, cursor_position)
            if current_line_position == -1:
                current_line_position = 0
            print(f"Current line position: {current_line_position}")

            # Get the position of the last colon in the current line
            last_colon_position = input_text.rfind(':', current_line_position, cursor_position)
            print(f"Last colon position: {last_colon_position}")

            # Get the position of the last space before the colon
            last_space_position = input_text.rfind(' ', current_line_position, last_colon_position)
            print(f"Last space position: {last_space_position}")

            if last_space_position == -1:
                stripped_text = input_text[current_line_position:last_colon_position].strip()
            else:
                stripped_text = input_text[last_space_position + 1:last_colon_position].strip()
            print(f"Stripped text: {stripped_text}")
            if stripped_text:  # Add this line
                self.parent().search_key_value_pairs(stripped_text)
        elif event.text().isdigit() and self.colon_pressed:  # Check if the colon key was pressed
            index = int(event.text())
            self.parent().select_search_result_by_number(index)
            self.colon_pressed = False  # Reset the flag
            return
        else:
            self.colon_pressed = False  # Reset the flag if any other key is pressed
            super().keyPressEvent(event)
            if stripped_text:
                self.parent().search_key_value_pairs(stripped_text)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()

        # Get the cursor position and the word under the cursor
        cursor = self.cursorForPosition(event.pos())
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        selected_word = cursor.selectedText()

        # Check if the word is misspelled
        if self.spell_check_highlighter.spell_checker.unknown([selected_word]):
            suggestions = self.spell_check_highlighter.spell_checker.candidates(selected_word)
            if suggestions:
                menu.insertSeparator(menu.actions()[0])
                for suggestion in suggestions:
                    action = QtWidgets.QAction(suggestion, self)
                    action.triggered.connect(lambda _, s=suggestion, c=cursor: self.replace_word(c, s))
                    menu.insertAction(menu.actions()[0], action)
            else:
                no_suggestions_action = QtWidgets.QAction("No suggestions", self)
                no_suggestions_action.setEnabled(False)
                menu.insertSeparator(menu.actions()[0])
                menu.insertAction(menu.actions()[0], no_suggestions_action)

        menu.exec_(event.globalPos())

    def replace_word(self, cursor, new_word):
        cursor.beginEditBlock()
        cursor.removeSelectedText()
        cursor.insertText(new_word)
        cursor.endEditBlock()


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
        self.input_box = QPlainTextEdit(self)
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
        self.output_box.textChanged.connect(self.preview_output)  # Add this line

        self.search_results_list = QListWidget(self)
        bottom_layout.addWidget(self.search_results_list)
        self.search_results_list.itemDoubleClicked.connect(self.display_search_results)
        self.search_results_list.setMaximumSize(200, 200)

        main_layout.addLayout(bottom_layout)

        # Set the main layout
        self.setLayout(main_layout)

        self.key_value_pairs = {}
        self.json_key_value_pairs = {}
        self.selected_search_result = None

    def input_box_text_changed(self):
        print("Input box text changed:")
        print(repr(self.input_box.toPlainText()))

    def clear_boxes(self):
        self.input_box.clear()
        self.output_box.clear()
        self.search_results_list.clear()
        self.customer_name_input.clear()
        self.alert_name_input.clear()
        self.alert_link_input.clear()
        self.key_value_pairs = {}
        self.json_key_value_pairs = {}
        self.selected_search_result = None

    def preview_output(self):
        current_output = self.output_box.toPlainText()

        # Remove content within ---JSON--- tags
        current_output = re.sub(r'---JSON---(?:.|\n)*?---JSON---', '', current_output)

        html = markdown2.markdown(current_output, extras=["tables", "fenced-code-blocks"])

        html_with_css = f"""
                <style>
                /* Add your custom CSS styles here */
                pre {{
                    white-space: pre-wrap;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                }}
                th, td {{
                    border: 1px solid black;
                    padding: 8px;
                    text-align: left;
                }}
                /* Custom CSS for code blocks */
                pre code {{
                    display: block;
                    overflow-x: auto;
                    white-space: pre;  /* Changed from nowrap to pre */
                    border: 1px solid #ccc;
                    padding: 1em;
                    background-color: #f5f5f5;  /* Background color added */
                    border-radius: 4px;
                }}
                </style>
                {html}
                """

        self.html_view.setHtml(html_with_css)

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

    def display_search_results(self, results):
        self.search_results_list.clear()
        self.selected_search_result = results
        print(f"Search results: {self.selected_search_result}")

        for i, result in enumerate(results):
            result_text = f"{i + 1}. {result[1]}"
            print(f"Adding result to list: {result_text}")
            self.search_results_list.addItem(result_text)

    def select_search_result_by_number(self, index):
        if self.selected_search_result and 0 < index <= len(self.selected_search_result):
            selected_result = self.selected_search_result[index - 1]
            self.insert_selected_result_text(selected_result[1])
            self.clear_search_results()  # Clear search results after selecting a result
        else:
            print("Invalid index or no search results available.")

    def clear_search_results(self):
        self.search_results_list.clear()
        self.selected_search_result = None

    def insert_selected_result_text(self, result_text):
        cursor = self.output_box.textCursor()
        cursor.insertText(f' "{result_text}"')

    def search_key_value_pairs(self, search_term):
        print(f"Search term: {search_term}")

        # Search non-JSON key-value pairs
        non_json_results = [(key, value[0]) for key, value in self.key_value_pairs.items() if
                            search_term.lower() in key.lower()]

        # Search JSON key-value pairs
        json_results = [(key, value) for key, value in self.json_key_value_pairs.items() if
                        search_term.lower() in key.lower()]

        # Combine both search results
        results = non_json_results + json_results
        print(f"Search results: {results}")

        self.display_search_results(results)

    def parse_json(self):
        input_text = self.input_box.toPlainText()

        # 1. Recognize JSON objects using a custom function
        json_objects = self.extract_json_objects(input_text)

        # 2. Parse and store key-value pairs in a dictionary
        self.json_key_value_pairs = {}
        for json_object in json_objects:
            try:
                json_data = json.loads(json_object)
                self.json_key_value_pairs.update(json_data)
            except json.JSONDecodeError:
                QMessageBox.warning(self, "Invalid JSON", f"The following JSON object is invalid: {json_object}")

        print(f"JSON Key-Value Pairs: {self.json_key_value_pairs}")  # Debugging print statement

        # 3. Display the parsed JSON in the output box between ---JSON--- tags
        formatted_json = json.dumps(self.json_key_value_pairs, indent=2)
        output_text = f"\n\n---JSON---\n{formatted_json}\n---JSON---"
        current_output = self.output_box.toPlainText()
        if current_output:
            self.output_box.setPlainText(current_output + "\n" + output_text)
        else:
            self.output_box.setPlainText(output_text)

    def extract_json_objects(self, text):
        json_objects = []
        open_brackets = 0
        start_index = -1

        for i, char in enumerate(text):
            if char == '{':
                if open_brackets == 0:
                    start_index = i
                open_brackets += 1
            elif char == '}':
                open_brackets -= 1
                if open_brackets == 0:
                    json_objects.append(text[start_index:i + 1])

        return json_objects

    def is_domain_ip_or_sha256(self, value):
        try:
            ip = ip_address(value)
            return ip.is_global
        except ValueError:
            pass

        if re.match(r'http[s]?://', value):
            return True

        # Check for SHA-256 hash
        if re.match(r'^[A-Fa-f0-9]{64}$', value):
            return True

        return False

    def build_table(self):
        # Save the current cursor position
        current_cursor_position = self.output_box.textCursor().position()

        # Move the cursor to the beginning of the text
        self.output_box.moveCursor(QtGui.QTextCursor.Start)
        input_text = self.input_box.toPlainText()

        # Remove text between curly brackets
        input_text = re.sub(r'\{[^}]*\}', '', input_text)

        # Split the input text by lines
        lines = input_text.split('\n')

        # Ignore empty lines
        non_empty_lines = [line for line in lines if line.strip() != '']

        # Store key-value pairs
        self.key_value_pairs = {}  # Change this line
        for i in range(0, len(non_empty_lines) - 1, 2):
            key = non_empty_lines[i]
            value = non_empty_lines[i + 1]

            # Check if the value is a domain, public IPv4, IPv6, URL with http:// or https://, or SHA-256 hash
            if self.is_domain_ip_or_sha256(value):
                self.key_value_pairs[key] = (value, "Reputation Check")  # Change this line
            else:
                self.key_value_pairs[key] = (value, "")  # Change this line

        # Generate the markdown table
        table_header = "| Data | Content | Link |\n|------|---------|------|\n"
        table_rows = []
        for key, value in self.key_value_pairs.items():
            content = re.sub(r'(?:http(s)?://)?(?:www\.)?', '', value[0])
            if value[1] == "Reputation Check":
                link = f"https://www.virustotal.com/gui/search/{content}"
                table_rows.append(f"| {key} | {content} | [{value[1]}]({link}) |")
            else:
                table_rows.append(f"| {key} | {content} |  |")

        new_markdown_table = table_header + '\n'.join(table_rows)

        # Remove the existing table (if exists) from the output
        existing_table_pattern = r'\| Data \| Content \| Link \|\n\|------\|---------\|------\|.*?(?=\n\n|$)'
        existing_table = re.search(existing_table_pattern, self.output_box.toPlainText(), flags=re.DOTALL)
        if existing_table:
            self.output_box.setPlainText(
                re.sub(existing_table_pattern, '', self.output_box.toPlainText(), flags=re.DOTALL))

        # Insert the table at the beginning of the output box
        self.output_box.insertPlainText(new_markdown_table + "\n\n")

        # Restore the cursor position
        new_cursor_position = self.output_box.textCursor()
        new_cursor_position.setPosition(current_cursor_position + len(new_markdown_table) + 2)
        self.output_box.setTextCursor(new_cursor_position)

        self.preview_output()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
