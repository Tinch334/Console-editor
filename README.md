
# Console-editor
A simple console text editor made in Python using the curses library. For now the editor remains not usable for proper coding, mainly due to the lack of syntax highlighting and tabulations.

## Requirements
The console editor requires the following:
- Python 3.10 or higher (https://www.python.org/downloads/)
- The curses module. If you are using Linux then you already have it, if instead you use Windows see (https://pypi.org/project/windows-curses/)

<br/>

## Configuration file
The editor now has a configuration file, in YAML
### Colours
Each colour in the editor is composed of a foreground and background colour, the first one is the foreground colour (The colour of the characters), and the second one the background colour. The colours must be one of the following:
> ``BLACK, BLUE, CYAN, GREEN, MAGENTA, RED, WHITE, YELLOW``

For example the colour ``BLUE_WHITE`` would have a blue foreground and a white background.

### Configuring the statusbar
The status bar is the blue bar at the bottom of the editor, it contains useful information. To customise it the ``status-bar-style`` field in the configuration file can be edited. It consists of elements and separators, elements are the actual information (line count, cursor position, etc) and separators are what goes between them.  It must start with a ``\``, and end with no separator, but after that you can configure it in any way you want.

The available elements:
* ``filename:`` The name of the file being edited, if it has no name it displays ``[No filename]``.
* ``lines:`` The amount of lines the current file has.`
* ``modified:`` Whether the file has been modified and has unsaved changes.
* ``fps:`` Displays the FPS the editor is currently running at.
* ``cursor:`` Shows the position of the cursor, first vertical then horizontal.

The available separators:
* ``\:`` An empty separator, nothing will be inserted between the elements.
* ``-:`` The string ``" - "`` will be inserted between the elements.
* ``/:`` The rest of the elements after this separator will be right aligned.

<br/>
 
## Tool console
The tool console is very similar in concept and function to VIM's console, it's activated with ``Ctrl+T``. All editor functions can be called from the console. Note that an ``(o)`` next to an argument indicates it's optional. The available commands are:
* ``wc`` for word count, which counts the number of words (strings composed of alphanumeric characters) in the file
* ``l <line>`` for line jump, jumps to the specified line.
* ``s <filename>(o)`` for save. If no filename is specified the editor will use the current one, if it exists. If a filename is provided then the function will act as "Save as".
* ``o <filename>`` for open.
* ``q`` for quit, cannot quit with unsaved changes.
* ``qf`` for force quit, quit without saving.
* ``f <text to find>`` for finding text, does not support regular expressions at the moment.

<br/>

## Running
To ensure the editor runs make sure all three necessary files are in the same folder:
> ``text_editor.py, utils.py, config.yaml``

<br/>

### Additional notes:
* The save and open functions use a relative path. They use the path from the directory in which the program files are located.
* Tabulations are not yet supported, mainly due to them requiring the rewrite of the display, cursor and scroll handling functions.
* Copying and pasting text can be done, _however_ it's not supported by the editor. It has to be done using the console, hoping it doesn't produce any problems. It's not reliable in its current state.
* Syntax highlighting is in the works but is currently too inefficient to be officially added to the editor, specially on large files the performance hit is significant.