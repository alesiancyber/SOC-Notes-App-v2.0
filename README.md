# SOC-Notes-App-v2.0
My Idea for a SOC notes app but switching from tkinter to PyQt5 to support some features that were not available in tkinter due to limited graphics support.

# SOC-Notes-App-v2.0

### Current Features:
- Formats markdown table based on newline character (it ignores empty lines) splitting them into  | data | content |
  - Example: user /n test would be: | user | test |  |
- SHA 256, IPv4 & IPv6, and domains prefixed with http(s):// in the conten column will have a link column that is hyperlinked to the VT detection page for that item.
  - hyperlink is in format | reputation check |
- Indexes the markdown table and JSON data and allows searching based on a colon (:) keypress
- Autocomplete: search results list is numbered and pressing the number will insert that value in the format of {user: "test"} which searched "user" and returned "test" to the search results list box.
- Has red underlining for spell check
- Save to file C:\Users\***\Documents\Case Files. Format: Customer_name_Alert_Name_mm-dd-yyyy
- Parses Json and stores key:value for searching with colon keypress
- Has a markdown renderer that displays what content should render like in a markdown supported environment



#### Future changes/Roadmap (in order of future implementation)
- Excluding json from the html render of the markdown (the notes preview feature)
- Right Click for spell check suggestions
- Append selected json values from autocomplete list to the markdown table
- Export to PDF
- Support Images/screenshots
- Packaged as self contained program using py installer

##### Notes
- I user curly brackets "{}" to identify the json to keep it from being overwritten, if you use curly brackets it will be identified as JSON data and may prompt an error.
- HTML render currently supports code blocks (``` ```) but the code block support is buggy. and the text can expand beyond the borders. Its on my fix list but is not
a priority
- I do want to support syntax highlighting in the codeblocks but unsure of its usefulness, not putting it on the roadmap for now until i make a determination
