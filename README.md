# Console-editor
A simple console text editor made in Python using the curses library. For now the editor remains not usable for proper coding, mainly due to the lack of syntax highlighting and tabulations.

## Requirements
The console editor requires the following:
- Python 3.8 or higher (https://www.python.org/downloads/)
- The curses module. If you are using Linux then you already have it, if instead you use Windows see (https://pypi.org/project/windows-curses/)

## Configuration file
The editor now has a configuration file, in YAML. For now it only really controls the colours in the editor. Each colour in the editor is composed of a foreground and background colour, the first one is the foreground colour (The colour of the characters), and the second one the background colour. The colours must be one of the following:
> ``BLACK, BLUE, CYAN, GREEN, MAGENTA, RED, WHITE, YELLOW``

For example the colour ``BLUE_WHITE`` would have a blue foreground and a white background.
 
## Tool console
The tool console is very similar in concept and function to VIM's console, it's activated with ``Ctrl+T``. There are currently two functions that can only be called through the console:
* Word count, which count's the number of words (strings composed of alphanumeric characters) in the file. Uses command ``wc``.
* Line jump, jumps to the specified line. Uses command ``l <line>``.

The other functions that are already present in the editor can also be accessed with the console, however they still don't support arguments, they just invoke their respective functions. They use the commands:
* ``s`` for save
* ``sa`` for save as
* ``o`` for open
* ``f`` for find

## Running
To ensure the editor runs make sure all three necessary files are in the same folder:
> ``text_editor.py, utils.py, config.yaml``

<br/>

### Additional notes:
* The save and open function use a relative path. Meaning they use the path from the directory in which the program files are located.
* Tabulations are not yet supported, mainly due to them requiring the rewrite of the display, cursor and scroll handling functions.
* Copying and pasting text can be done, _however_ it's not supported by the editor. It has to be done using the console, hoping it doesn't produce any problems. It's not reliable in its current state.
* Syntax highlighting is in the works but is currently too inefficient to be officially added to the editor, specially on large files the performance hit is significant.