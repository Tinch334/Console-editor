# Console-editor
A simple console text editor made in Python using the curses library

Both files(_text_editor.py_ and _utils.py_) need to be in the same folder in order for the editor to work. To run it run _text_editor.py_.

__Additional notes:__
* The save and open function use a relative path. Meaning they use the path from the directory in which the program files are located.
* Tabulations are not yet supported, mainly due to them requiring the rewrite of the display, cursor and scroll handling functions.
* Pasting and copying text can be done, _however_ it's not supported by the editor. It has to be done using the console, hoping it doesn't produce any problems, not reliable in its current state.

__TODO:__
- [ ] Add tabulations
- [ ] Add save as and exit confirmation
- [ ] Add syntax highlighting
- [ ] Add configuration file
