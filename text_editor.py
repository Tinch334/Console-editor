import utils, curses, curses.ascii, math, re, yaml, sys, getopt, datetime, time, os
from dataclasses import dataclass, field
from typing import Union, Callable, Iterable, Any



#Each line is stored as a dataclass. They are similar to structs in other languages, however they retain all the
#characteristics of a class.
@dataclass
class Line:
    line_text: str = ""



#This class is what makes the search function work. It handles all the search cursor logic. It stores the variables needed for
#the search function. They are separated manly to avoid cluttering the program's class with variables.
@dataclass
class SearchMatch:
    #This dictionary contains the line and index of a match. The line is the key for the dictionary entry.
    line_and_index: dict = field(default_factory=dict)
    #This dictionary contains the length of every match found, to account for the possibility of matches with different
    #lengths.
    line_match_length: dict = field(default_factory=dict)
    #Whether or not the find function is currently active
    find_enabled: bool = False
    #The line of the the match the cursor was last set to.
    current_match_line: int = 0
    #The number of match in the line the cursor was last set to.
    current_match_number_in_line: int = 0



#A simple prompt, with default text and the option to change it for a specified period of time. Beware that the prompt class
#only takes care of the actual text of the prompt, printing has to be handled by the user.
class Prompt:
    def __init__(self, default_prompt: str, restore_time_ms: int):
        self.default_prompt = default_prompt
        #How long the modified prompt will last in ms before being changed back to the default prompt.
        self.restore_time_ms = restore_time_ms

        self.prompt = default_prompt
        self.restore_time_counter = 0
        self.prompt_enabled = True


    def toggle_prompt(self) -> None:
        self.prompt_enabled = not self.prompt_enabled


    def change_prompt(self, new_prompt: str) -> None:
        self.prompt = new_prompt
        self.restore_time_counter = time.time()


    #Changes the new prompt back to the default prompt once the specified time has passed. Has to be called each program loop.
    def prompt_handler(self) -> None:
        if time.time() > self.restore_time_counter + self.restore_time_ms:
            self.prompt = self.default_prompt



#A simple FPS counter. It's very important to note that this simple class doesn't actually count the times the console buffer
#is printed, instead it counts how many times it was called in a second. Therefore to use this function it should be placed in
#your programs main loop so it's called every time it runs.
class FPSMeter:
    def __init__(self) -> None:
        self.start_time = 0
        self.fps_count = 0
        #Use this to get the FPS, it's updated once a second.
        self.fps_final_count = 0


    #Has to be called every "frame" that the program runs. In console applications this function should be called from the
    #main program loop.
    def fps_handler(self) -> None:
        if time.time() - self.start_time > 1:
            self.fps_final_count = self.fps_count
            self.fps_count = 0

            self.start_time = time.time()
        else:
            self.fps_count += 1



class TextEditor(utils.CursesUtils):
    def __init__(self) -> None:
        super().__init__()

        #####CONFIGURATION#####
        #Make "getch" non-blocking.
        self.stdscr.nodelay(True)

        #####GENERAL VARIABLES#####
        #Last pressed key.
        self.key = 0
        #The text in the editor, a list of lines.
        self.text = [Line()]
        #The file currently being edited.
        self.file = None

        #####CURSOR VARIABLES#####
        #The y position of the cursor.
        self.cursor_pos_y = 0
        #The x position of the cursor.
        self.cursor_pos_x = 0
        #The x position one desires the cursor to be in. What this means is that if someone goes to a shorter line, and then
        #to a longer line again the cursor will go to the end. Best way to explain is with an example.
        """
        Example text:
        Hello friend
        Hi mate
        How are you doing
        I'm doing fine, thank you
        -----
        To use the example first enter the text into the editor. Then move to the end of the third line using the left and
        right arrows. Then with the up and down arrows move the two lines above. You will notice that the cursor snaps to the
        end, because it wants to get to the x position it had on the third line. If you however move to the last line you will
        see the cursor just stay in the same x position it was because the cursor can move to the same x position it had in
        the last line, whilst it couldn't in the other lines.
        """
        self.desired_cursor_x_pos = 0

        #The text displayed at the bottom of the editor, can be used for messages.
        self.prompt = Prompt("COMMANDS: Ctrl+S - save | Alt+S - save as | Ctrl+O - open | Ctrl+F - find | Ctrl+Q - quit | Ctrl+T - tools", 3.5)

        #####SCROLLING#####
        #The line to which the editor is scrolled, vertically. IE: the topmost visible line.
        self.vertical_scroll_line = 0
        #The character to which the editor is scrolled, horizontally. IE: the leftmost visible character.
        self.horizontal_scroll_character = 0

        #####BUFFER DISPLAY#####
        self.max_displayed_lines = self.y_size - 2
        #Maximum allowed text width, in chars. The -2 is an approximation expecting a file with less than a thousand lines
        #to be loaded. 
        self.max_text_width = self.x_size - 3

        #####SEARCH FUNCTION#####
        """
        The editor enters "search mode" when something is searched using "Ctrl+F", when this happens the "Page Up" and
        "Page Down" keys can be used to move through the matches. The escape key can be used to leave this mode.
        """
        self.find_results = SearchMatch()

        #####EXIT CONFIRMATION#####
        #Counts how many times the buffer's been modified since the file was loaded or saved. That way we can determine if
        #are unsaved changes.
        self.buffer_modification_counter = 0
        #Used to count how many times a certain key combination that would result in losing unsaved changes has been pressed.
        self.confirmation_counter = 0

        #####CONFIGURATION FILE#####
        self.config_file = None

        #####FPS HANDLING#####
        self.fps_meter = FPSMeter()

        #####NOTES#####
        """
        Something very important to remember about the editor is that the cursor and text are independent from the displayed
        text. The displayed text just matches wherever the cursor is, via "scroll_handler".
        """


    #Parse any given command line arguments.
    def parse(self) -> None:
        #Short and long version of all options.
        short_options = "vh"
        long_options = ["version", "help"]

        version_text = "Text editor - Version 1.2 - January 2021\n"
        usage_text = "Usage: python {} [-v/--version] | [-h/--help] <file>\n".format(sys.argv[0])

        options, arguments = getopt.getopt(sys.argv[1:], short_options, long_options)

        #Parse all the options.
        for o, a in options:
            if o in ("-v", "--version"):
                raise SystemExit(version_text)
            elif o in ("-h", "--help"):
                raise SystemExit(usage_text)
            else:
                raise SystemExit(usage_text)

        #If more than one file was given as an argument show usage and exit.
        if len(arguments) > 1:
            raise SystemExit(usage_text)

        if len(arguments) == 1:
            path = os.path.join(os.getcwd(), arguments[0])

            #If a file was passed as an argument check if it exists. If so open it, otherwise simply set the given name as the
            #name of the file that's being edited.
            if os.path.lexists(path):
                self.load_file(path)
            else:
                self.file = arguments[0]



    #The setup preformed before the editor starts.
    def setup(self) -> None:
        #Parses arguments.
        self.parse()

        #Loads the configuration file.
        with open("config.yaml", "r") as f:
            self.config_file = yaml.safe_load(f)


    def editor(self) -> None:
        while True:
            self.stdscr.clear()
            self.get_size()

            self.detect_key()
            self.scroll_handler()

            self.fps_meter.fps_handler()

            self.print_screen()
            self.prompt.prompt_handler()

            self.stdscr.refresh()
            self.key = self.stdscr.getch()

    """
    INPUT HANDLING
    """
    def detect_key(self) -> None:
        #Text characters, this range covers all of extended ASCII.
        if self.key >= 32 and self.key <= 253:
            self.insert_char(chr(self.key))

            #Disables find function and increments buffer modification counter.
            self.modification_handler()

        #Backspace
        elif self.key == 8:
            #If the line isn't empty delete the corresponding character.
            if len(self.text[self.cursor_pos_y].line_text) > 0 and self.cursor_pos_x > 0:
                #Copy all the text in the current line except the char to the left of the cursor.
                text_with_removed_char = self.text[self.cursor_pos_y].line_text[:self.cursor_pos_x - 1]
                text_after = self.text[self.cursor_pos_y].line_text[self.cursor_pos_x:]
                self.text[self.cursor_pos_y].line_text = text_with_removed_char + text_after

                self.cursor_pos_x -= 1

            #If at the begging of a line and not at the first line. The current line's text should join the end of the line
            #above. This also works for "deleting" empty lines, since you are appending an empty string.
            elif self.cursor_pos_x == 0 and self.cursor_pos_y > 0:
                #Make the cursor's x position be at the end of the line to which you are moving. This has to be done first
                #because otherwise the cursor would be at the end of the line with the appended new text.
                self.cursor_pos_x = len(self.text[self.cursor_pos_y - 1].line_text)

                self.text[self.cursor_pos_y - 1].line_text += self.text[self.cursor_pos_y].line_text
                self.text.pop(self.cursor_pos_y)
                self.cursor_pos_y -= 1

            #Update the desired cursor position
            self.desired_cursor_x_pos = self.cursor_pos_x

            #Disables find function and increments buffer modification counter.
            self.modification_handler()

        #"SUPR" key.
        elif self.key == curses.KEY_DC:
            #Make sure there's text to delete.
            if self.cursor_pos_x < len(self.text[self.cursor_pos_y].line_text):
                #Copy all the text in the current line except the char to the right of the cursor.
                text_before = self.text[self.cursor_pos_y].line_text[:self.cursor_pos_x]
                text_with_removed_char = self.text[self.cursor_pos_y].line_text[self.cursor_pos_x + 1:]
                self.text[self.cursor_pos_y].line_text = text_before + text_with_removed_char

            #Move the line below to the current line. Make sure there's a line to move up.
            elif len(self.text) - 1 > self.cursor_pos_y:
                self.text[self.cursor_pos_y].line_text += self.text[self.cursor_pos_y + 1].line_text
                self.text.pop(self.cursor_pos_y + 1)

            #Disables find function and increments buffer modification counter.
            self.modification_handler()

        #Enter key
        #The actual code given by the enter key is 10, however the rest are left here for compatibility. Beware that
        #"CTRL+J" also has a keycode of 10.
        elif self.key == 10 or self.key == 13 or self.key == curses.KEY_ENTER:
            #Since the text is accessed multiple times store it in a variable.
            line_text = self.text[self.cursor_pos_y].line_text

            #When enter is pressed all the text to the right of the cursor goes down to the new line.
            text_before = line_text[:self.cursor_pos_x]
            text_after = line_text[self.cursor_pos_x:]
            #Calculates the amount of spaces at the beginning of the new line by getting the amount of spaces at the
            #beginning of the old line.
            spaces_to_add = len(line_text) - len(line_text.lstrip(" "))

            #The old line retains what was left of the cursor.
            self.text[self.cursor_pos_y].line_text = text_before

            #Create the new line and add corresponding text.
            self.text.insert(self.cursor_pos_y + 1, Line())

            #Creates the new line by adding the corresponding spaces and then the text that was right of the cursor.
            self.text[self.cursor_pos_y + 1].line_text = (" " * spaces_to_add) + text_after

            self.cursor_pos_y += 1
            self.cursor_pos_x = spaces_to_add
            self.desired_cursor_x_pos = self.cursor_pos_x

            #Disables find function and increments buffer modification counter.
            self.modification_handler()

        #TAB key
        elif self.key == 9:
            #Add the remaining spaces to reach the desired tab width.
            spaces_to_add = 4 - (self.cursor_pos_x % self.config_file["MISC"]["tabstop-width"])

            for x in range(spaces_to_add):
                self.insert_char(" ")

            #Disables find function and increments buffer modification counter.
            self.modification_handler()


        #Moves the cursor. Before doing so check that there's text to move it to.
        elif self.key == curses.KEY_LEFT:
            #Move the cursor normally.
            if self.cursor_pos_x > 0:
                self.cursor_pos_x -= 1
            #If the cursor is at the beginning of the line then it should move to the end of the line above. Make sure there's
            #a line to move up to.
            elif self.cursor_pos_y > 0:
                    self.cursor_pos_y -= 1
                    self.cursor_pos_x = len(self.text[self.cursor_pos_y].line_text)

            #Update the desired cursor position
            self.desired_cursor_x_pos = self.cursor_pos_x

        elif self.key == curses.KEY_RIGHT:
            #Move the cursor normally.
            if self.cursor_pos_x < len(self.text[self.cursor_pos_y].line_text):
                self.cursor_pos_x += 1

            #If the cursor is at the end of the line then it should move to the beginning of the line below. Make sure there's
            #a line to move down to.
            elif len(self.text) - 1 > self.cursor_pos_y:
                    self.cursor_pos_y += 1
                    self.cursor_pos_x = 0

            #Update the desired cursor position
            self.desired_cursor_x_pos = self.cursor_pos_x

        elif self.key == curses.KEY_DOWN and len(self.text) - 1 > self.cursor_pos_y:
            self.interline_cursor_handler(1)

        elif self.key == curses.KEY_UP and self.cursor_pos_y > 0:
            self.interline_cursor_handler(-1)

        #"HOME" and "END" keys.
        elif self.key == curses.KEY_HOME:
            self.cursor_pos_x = 0
            #Update the desired cursor position
            self.desired_cursor_x_pos = 0

        elif self.key == curses.KEY_END:
            self.cursor_pos_x = len(self.text[self.cursor_pos_y].line_text)
            #Update the desired cursor position
            self.desired_cursor_x_pos = self.cursor_pos_x


        #"Page Up" and "Page Down" keys.
        elif self.key == curses.KEY_PPAGE:
            if self.find_results.find_enabled:
                self.match_line_handler(-1)
            else:
                #Move the y cursor "up" by the size of the screen.
                new_cursor_pos = self.cursor_pos_y - self.max_displayed_lines

                #If the cursor goes past the beginning of the text set it to the first line.
                if new_cursor_pos < 0:
                    new_cursor_pos = 0

                #So that the cursor moves to the correct x position. This is required because when we change lines we have
                #to handle the cursor, otherwise we'll be prone to getting index errors.
                self.interline_cursor_handler(-abs(new_cursor_pos - self.cursor_pos_y))


        elif self.key == curses.KEY_NPAGE:
            if self.find_results.find_enabled:
                self.match_line_handler(1)
            else:
                #Move the y cursor "down" by the size of the screen.
                new_cursor_pos = self.cursor_pos_y + self.max_displayed_lines

                #If the cursor goes past the end of the text set it to the last line.
                if new_cursor_pos >= len(self.text):
                    new_cursor_pos = len(self.text) - 1

                #So that the cursor moves to the correct x position. This is required because when we change lines we have
                #to handle the cursor, otherwise we'll be prone to getting index errors.
                self.interline_cursor_handler(abs(new_cursor_pos - self.cursor_pos_y))

        #"ESC" key.
        elif self.key == 27:
            if self.find_results.find_enabled:
                self.find_results.find_enabled = False

        #"CTRL" keys.
        #NOTE: The way in which "CTRL" works is, it takes the keycode of the key that was pressed in conjunction with "CTRL"
        #(ex: CTRL+A, the key is "A") and returns it's value, using the uppercase ASCII code minus 64. So if you pressed
        #CTRL+E you would get a keycode of 5.

        #"CTRL+Q"
        elif self.key == ord("Q") - 64:
            required_confirmation = self.config_file["MISC"]["confirmation-key-count"]

            #If the buffer has been modified since the last save check if "Ctrl+Q" has been pressed the required number of
            #times to exit.
            if self.buffer_modification_counter > 0:
                if self.confirmation_counter < required_confirmation:
                    self.prompt.change_prompt("File has unsaved changes, press Ctrl+Q {} more times to quit".format(required_confirmation - self.confirmation_counter))
                    self.confirmation_counter += 1

                    return

            #Properly exit curses and exit the program.
            curses.endwin()
            quit()


        #"CTRL+S" key combination.
        elif self.key == ord("S") - 64:
            #If there's no filename get one from the user.
            if self.file == None:
                self.save_handler(True)
            else:
                self.save_handler()

        #"CTRL+O" key combination.
        elif self.key == ord("O") - 64:
            self.load_handler()

        #"CTRL+F" key combination.
        elif self.key == ord("F") - 64:
            self.find_handler()

        #"CTRL+T" key combination. Activates the "tool console", which allows to write commands in a VIM like console.
        elif self.key == ord("T") - 64:
            self.tool_console_handler()

        #"ALT" keys.
        #NOTE: "ALT" keys use the same principle as the "CTRL" keys, but you add 352 instead of subtracting 64.
        elif self.key == ord("S") + 352:
            self.get_save_name()


    #Handles everting that happens whenever the buffer's modified.
    def modification_handler(self) -> None:
        #Increment the buffer modification counter.
        self.buffer_modification_counter += 1
        #Whenever the buffer is modified we also reset the number of times "Ctrl+Q" has to be pressed to exit.
        self.confirmation_counter = 0

        #Disable the find function since the buffer was modified.
        self.find_results.find_enabled = False


    def insert_char(self, char: str) -> None:
        #Insert the given char at the current cursor position. Since python strings are immutable we create a new string
        #consisting of the previous string split where the cursor is plus the added character.
        text_before = self.text[self.cursor_pos_y].line_text[:self.cursor_pos_x]
        text_after = self.text[self.cursor_pos_y].line_text[self.cursor_pos_x:]
        self.text[self.cursor_pos_y].line_text = text_before + char + text_after

        #Move the cursor's position in that line.
        self.cursor_pos_x += 1
        #Update the desired cursor position
        self.desired_cursor_x_pos = self.cursor_pos_x


    """
    CURSOR HANDLING
    """
    #Allows for vertical and horizontal scrolling.
    def scroll_handler(self) -> None:
        #Vertical scrolling
        #If the cursor is above the scroll line simply make it equal to the cursor.
        if self.cursor_pos_y < self.vertical_scroll_line:
            self.vertical_scroll_line = self.cursor_pos_y
        #If the cursor gets to the end of the text window then move it down by one.
        elif self.cursor_pos_y > (self.vertical_scroll_line + self.max_displayed_lines) - 1:
            self.vertical_scroll_line = self.cursor_pos_y - self.max_displayed_lines + 1

        #Horizontal scrolling
        #If the cursor is further left than the scroll line simply make it equal to the cursor.
        if self.cursor_pos_x < self.horizontal_scroll_character:
            self.horizontal_scroll_character = self.cursor_pos_x
        #If the cursor gets to the end of the text window move it right by one.
        elif self.cursor_pos_x > (self.horizontal_scroll_character + self.max_text_width) - 1:
            self.horizontal_scroll_character = self.cursor_pos_x - self.max_text_width + 1


    #Handles what happens when the cursor changes lines via the up and down arrow. "line_index" is the index to the line the
    #cursor is moving, relative to the current line.
    def interline_cursor_handler(self, line_index: int) -> None:
        moving_to_line_length = len(self.text[self.cursor_pos_y + line_index].line_text)

        #If the line to move to is shorter than the desired cursor length go to the end of the line.
        if self.desired_cursor_x_pos > moving_to_line_length:
            self.cursor_pos_x = moving_to_line_length
        #Otherwise just keep the desired cursor position.
        else:
            self.cursor_pos_x = self.desired_cursor_x_pos

        #Update the y position of the cursor.
        self.cursor_pos_y += line_index


    #Allows to choose which of all the matched texts is selected and automatically moves the cursor to it. Performance wise it
    #doesn't matter that this function accesses a dataclass a lot. This is because this function is only called when either
    #"PPAGE" or "NPAGE" are pressed, not every frame.
    def match_line_handler(self, change: int) -> None:
        self.find_results.current_match_number_in_line += change

        #Check whether we are on a line with matches, if so cycle through them normally.
        if self.cursor_pos_y in self.find_results.line_and_index:
            #Check if we are on a line with matches. If so check if there are any remaining matches in the current line.
            if self.find_results.current_match_number_in_line >= len(self.find_results.line_and_index[self.cursor_pos_y]) or self.find_results.current_match_number_in_line < 0:
                #Move to the corresponding line depending on what the change was.
                self.find_results.current_match_line += change

                #If we get to the end or the beginning of the file go to the other end.
                if self.find_results.current_match_line < 0:
                    self.find_results.current_match_line = len(self.find_results.line_and_index) - 1
                elif self.find_results.current_match_line >= len(self.find_results.line_and_index):
                    self.find_results.current_match_line = 0

                #If we change lines in which match the cursor ends depends on whether we are moving "up" or "down". If we are
                #moving down we simply start at the first match in the next line. However if we are moving up we start on the
                #last match of the previous line. To do this we set "current_match_number_in_line" to the length of the list
                #of matches in that line -1.
                if change > 0:
                    self.find_results.current_match_number_in_line = 0
                else:
                    self.find_results.current_match_number_in_line = len(self.find_results.line_and_index[list(self.find_results.line_and_index.keys())[self.find_results.current_match_line]]) - 1

                #Move the cursor to the corresponding line.
                self.cursor_pos_y = list(self.find_results.line_and_index.keys())[self.find_results.current_match_line]

            #Update the x position of the cursor. The x position of the cursor is set to the last char of the matched word
            #in case it's out of the screen so it will scroll and show the match.
            self.cursor_pos_x = self.find_results.line_and_index[self.cursor_pos_y][self.find_results.current_match_number_in_line] + self.find_results.line_match_length[self.cursor_pos_y][self.find_results.current_match_number_in_line]

        #Otherwise go to the closest match.
        else:
            #Set the first match as the initial closest line.
            closest_line = list(self.find_results.line_and_index.keys())[0]

            for line in list(self.find_results.line_and_index.keys()):
                #If the difference between the cursor and the line is smaller than the difference to the current closest line
                #we have found a new closest line.
                if abs(self.cursor_pos_y - line) < abs(self.cursor_pos_y - closest_line):
                    closest_line = line

            self.cursor_pos_y = closest_line

            #Update the x position of the cursor to the first match in that line.
            self.cursor_pos_x = self.find_results.line_and_index[closest_line][0] + self.find_results.line_match_length[closest_line][0]


    """
    PRINTING FUNCTIONS
    """
    #Displays the buffer and cursor. Also handles search function highlighting.
    def display(self) -> None:
        line_count = len(self.text)
        #The number of characters required to fit the line counter.
        line_display_width = int(math.log10(line_count)) + 1
        #Makes the width of the line number display a minimum of 3.
        line_display_width = max(line_display_width, 2)

        #The variable is set in the function because it depends on "line_display_width"
        self.max_text_width = self.x_size - line_display_width

        #What is the y coordinate to print to, doesn't represent the y position of the cursor.
        print_y = 0
        #What is the x coordinate to print to, doesn't represent the x position of the cursor.
        print_x = 0

        #The index for the matched text in the current line. If there's no matched text on the line it's set to "None".
        matched_text_index = None
        #Same operation as that of "matched_text_index".
        matched_text_length = None

        #Since all the colours are going to be used a significant number of times they are stored in variables. It would be
        #inefficient to access a dictionary several hundred times per cycle.
        text_colour = self.config_file["TEXT-COLOUR"]["text-colour"]
        normal_cursor_colour = self.config_file["TEXT-COLOUR"]["normal-cursor-colour"]
        over_text_cursor_colour = self.config_file["TEXT-COLOUR"]["over-text-cursor-colour"]
        find_match_colour = self.config_file["TEXT-COLOUR"]["find-match-colour"]
        line_colour = self.config_file["EDITOR-COLOUR"]["line-colour"]
        empty_line_colour = self.config_file["EDITOR-COLOUR"]["empty-line-colour"]

        #Prints the text, matched text from the found function and the cursor.
        for y in range(self.vertical_scroll_line, self.vertical_scroll_line + self.max_displayed_lines):
            #This is so that if there are less than "self.vertical_scroll_line + self.max_displayed_lines" lines(Empty lines)
            #the program doesn't try to address non existing lines. Instead it shows "~" to denote no lines.
            if y > line_count - 1:
                self.stdscr.addstr(print_y, 0, "~", self.get_colour(empty_line_colour))

            else:
                line = self.text[y]
                print_x = line_display_width

                #Sets the array containing the indexes of all matches in the current line, if there are any. The reason for
                #using a variable instead of doing a check on every iteration of the x for loop is that computationally
                #speaking it's expensive to check whether a certain element is a key in a dictionary, therefore we want to do
                #it as little as possible.
                #Furthermore make sure that find mode is enabled, to avoid printing anything left in the dictionary after the
                #search has finished.
                if self.find_results.find_enabled and y in self.find_results.line_and_index:
                    matched_text_indexes = self.find_results.line_and_index[y]
                    matched_text_length = self.find_results.line_match_length[y]
                else:
                    matched_text_indexes = None
                    matched_text_length = None

                #Print line number. Since we're printing y + 1 we must also use y + 1 in the length calculation with the 
                #logarithm. This also solves the problem with index 0 since 0 + 1 = 1.
                line_number_text = " " * (line_display_width - (int(math.log10(y + 1)) + 1)) + str(y + 1)
                self.stdscr.addstr(print_y, 0, line_number_text, self.get_colour(line_colour))

                #Print line. The text we want to print is the one between the horizontal scroll and the end of the screen            
                for x in range(self.horizontal_scroll_character, self.horizontal_scroll_character + self.max_text_width):
                    #In case the text is shorter than the range of the for loop.
                    if x > len(line.line_text) - 1:
                        break

                    char = line.line_text[x]

                    self.stdscr.addstr(print_y, print_x, char, self.get_colour(text_colour))

                    #If the current line has matched text that has to be highlighted, and the current x char is on the correct
                    #range highlight it by printing over the original white text.
                    if matched_text_indexes != None and matched_text_length != None:
                        #Get match and length for each occurrence.
                        for match, length in zip(matched_text_indexes, matched_text_length):
                            if x >= match and x < match + length:
                                self.stdscr.addstr(print_y, print_x, char, self.get_colour(find_match_colour))

                    print_x += 1

            #Print the cursor, it has to be printed after the text to appear over it.
            if self.cursor_pos_y == y:
                #Apart of taking the line display into account the horizontal scroll has to be subtracted, so in case it's
                #not zero and the text is shifted the cursor will follow.
                cursor_x_print_pos = self.cursor_pos_x + line_display_width - self.horizontal_scroll_character

                #Detect if you are in the last char or and react accordingly.
                if self.cursor_pos_x == len(line.line_text):
                    self.stdscr.addstr(print_y, cursor_x_print_pos, " ", self.get_colour(normal_cursor_colour))
                else:
                    self.stdscr.addstr(print_y, cursor_x_print_pos, line.line_text[self.cursor_pos_x], self.get_colour(over_text_cursor_colour))

            print_y += 1
            

    #Shows the status and help bar.
    def status_bar(self) -> None:
        left_status_text, right_status_text = self.build_statusbar()

        #The complete status bar.
        status_text = left_status_text + " " * (self.x_size - len(left_status_text) - len(right_status_text)) + right_status_text

        #Note: In this case we directly access the dictionary instead of using a variable because this only occurs once per
        #program loop.
        #Print the status bar.
        self.stdscr.addstr(self.max_displayed_lines, 0, status_text, self.get_colour(self.config_file["STATUS-BAR"]["status-bar-colour"]))

        #If the editor prompt is enabled print it.
        if self.prompt.prompt_enabled:
            self.stdscr.addstr(self.max_displayed_lines + 1, 0, self.prompt.prompt, self.get_colour(self.config_file["EDITOR-COLOUR"]["prompt-colour"]))


    #Creates the status-bar based on the style in the configuration file.
    def build_statusbar(self) -> None:
        #If there's nothing for the style return empty strings.
        if self.config_file["STATUS-BAR"]["status-bar-style"] == None:
            return "", ""

        #Whether we add elements to the left or right status text
        switch_right = False

        #Declared so we can append to them without problems
        left_status_text = ""
        right_status_text = ""

        #Automatically determines what the displayed filename should be, depending on whether or not a name has been given.
        filename_text = self.file if self.file != None else "[No filename]"
        line_text = str(len(self.text)) + " lines"
        #Whether or not the file is "dirty", if it's been modified since loading or saving.
        modified_text = " (modified)" if self.buffer_modification_counter > 0 else ""
        #FPS meter it's mainly there for efficiency testing.
        fps_text = "FPS: " + str(self.fps_meter.fps_final_count)
        #The cursors position.
        cursor_text = str(self.cursor_pos_y + 1) + "," + str(self.cursor_pos_x + 1) + " "
        #Time, only displays hours and minutes, in 24 hs format.
        current_time = datetime.datetime.now()
        time_text = "{:02d}:{:02d}".format(current_time.hour, current_time.minute)

        #A dictionary containing all possible elements for the status bar.
        status_elements_dict = {"filename" : filename_text, "lines" : line_text, "modified" : modified_text, "fps" : fps_text, "cursor" : cursor_text, "time" : time_text}

        #Isolates the added elements.
        status_added_elements = re.findall("\w+", self.config_file["STATUS-BAR"]["status-bar-style"])
        #Isolates the separators.
        status_added_separators = re.findall("[-\\\/]", self.config_file["STATUS-BAR"]["status-bar-style"])

        #Create left and right status-bar.
        for element, separator in zip(status_added_elements, status_added_separators):
            #The contents are used as a way to avoid repeating the switch check.
            contents = ""

            match separator:
                case "-":
                    contents += " - "

                case "\\":
                    pass

                case "/":
                    switch_right = True

                case _:
                    raise Exception("Invalid separator in statusbar configuration!")

            #Make sure the element exists and is valid.
            try:
                #Get proper value from dictionary.
                contents += status_elements_dict[element]
            except:
                raise Exception("Invalid element, \"{}\" in statusbar configuration!".format(element))

            #Check whether the element must be added to left or right status-bar.
            if switch_right:
                right_status_text += contents
            else:
                left_status_text += contents

        return left_status_text, right_status_text

    #Has all the functions that need to be called to properly display all screen elements. It's mostly for ease of use of the
    #"BasicInput" class.
    def print_screen(self) -> None:
        self.display()
        self.status_bar()


    """
    SAVE AND LOAD FUNCTIONS
    """
    #Handles the calling of the actual save function.
    def save_handler(self, filename: str = False) -> None:
        #To allow for entering a filename to load
        if filename:
            #Disable editor prompt.
            self.prompt.toggle_prompt()

            #Get the filename.
            basic_input = utils.BasicInput(self, self.y_size - 1, 0, "Save file: ", self.get_colour(self.config_file["EDITOR-COLOUR"]["input-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["normal-cursor-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["over-text-cursor-colour"]))
            #The "basic_input" method halts the program.
            file = basic_input.basic_input()

            #Re-enable editor prompt.
            self.prompt.toggle_prompt()

            #In case the user pressed the escape key.
            if file == None:
                return

            #Otherwise set filename.
            else:
                self.file = file

        #Get complete filepath.
        path = os.path.join(os.getcwd(), self.file)

        #Save the file in the given path.
        if self.save_file(path) == 0:
            #Change the prompt to display how many bytes have been written.
            self.prompt.change_prompt("{} bytes written to disk".format(str(os.path.getsize(path))))
        else:
            self.prompt.change_prompt("Failed to save file, please try again")


    #Saves the current file to the given path, returns false if it was successful.
    def save_file(self, path: str) -> bool:
        file_text = ""

        try:
            #Put all lines in one variable, separated by newlines.
            for line in self.text:
                file_text += line.line_text
                #Separate lines
                file_text += "\n"

            #Write to the file.
            file = open(path, "w")
            file.write(file_text)
            file.close()

            #Reset the modification counter.
            self.buffer_modification_counter = 0

            return False

        #In case an unexpected error occurs.
        except:
            return True


    #Handles the calling of the actual load function.
    def load_handler(self, file: str = None) -> None:
        if file == None:
            #Disable editor prompt.
            self.prompt.toggle_prompt()

            basic_input = utils.BasicInput(self, self.y_size - 1, 0, "Open file: ", self.get_colour(self.config_file["EDITOR-COLOUR"]["input-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["normal-cursor-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["over-text-cursor-colour"]))
            #The "basic_input" method halts the program.
            file = basic_input.basic_input()

            #Re-enable editor prompt.
            self.prompt.toggle_prompt()

            #If the "file" is still "None" that means that the escape key was pressed.
            if file == None:
                return

        #Save the file the user is currently working on. If it has a name.
        if self.file != None:
            self.save_file(os.path.join(os.getcwd(), self.file))

        #Get complete filepath.
        path = os.path.join(os.getcwd(), file)

        #Make sure the path we are trying to read exists.
        if os.path.lexists(path):
            #Open the file in the given path.
            if self.load_file(path) == 0:
                #If the file could be opened set the filename.
                self.file = file
                #Change the prompt to display how many bytes have been red.
                self.prompt.change_prompt("Loaded {} bytes from {}".format(str(os.path.getsize(path)), self.file))
            else:
                self.prompt.change_prompt("Failed to read file, please try again")

            #Reset the cursor position, so it's at the begging of the file.
            self.cursor_pos_y = 0
            self.cursor_pos_x = 0

        else:
            self.prompt.change_prompt("The entered file doesn't exist")    


    #Loads the file in the given path, returns false if it was successful.
    def load_file(self, path: str) -> bool:
        try:
            #Empty the text only if the file we are trying to read exists.
            self.text = []

            file = open(path, "r")

            for line in file.readlines():
                line = line.replace("\n", "")
                self.text.append(Line(line))

            file.close()

            #Reset the cursor so it starts at the beginning of the file.
            self.cursor_pos_y = 0
            self.cursor_pos_x = 0

            #Reset the modification counter.
            self.buffer_modification_counter = 0

            return False

        #In case an unexpected error occurs.
        except:
            return True


    """
    SEARCH FUNCTIONS
    """
    def find_handler(self, pattern: str = None) -> None:
        if pattern == None:
            #Disable editor prompt.
            self.prompt.toggle_prompt()

            #Get the text to search, supports regular expressions.
            basic_input = utils.BasicInput(self, self.y_size - 1, 0, "Find: ", self.get_colour(self.config_file["EDITOR-COLOUR"]["input-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["normal-cursor-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["over-text-cursor-colour"]))
            #The "basic_input" method halts the program.
            pattern_to_find = basic_input.basic_input()

            #Re-enable editor prompt.
            self.prompt.toggle_prompt()
        else:
            #If a pattern was given assign it to the proper variable.
            pattern_to_find = pattern

        #Remove any previous matched text.
        self.find_results.line_and_index = {}

        #Used to display how many matches were found using the prompt. It's more efficient to simply have a counter
        #than accessing a dictionary.
        match_counter = 0

        #Gets every match in a line and puts it in an array. Then that array is added to the dictionary using the line
        #as it's key.
        for y in range(0, len(self.text)):
            line_matches = []
            matches_length = []
                    
            for match in re.finditer(pattern_to_find, self.text[y].line_text):
                line_matches.append(match.start(0))
                #Gets the length of the match by subtracting it's start index to it's end index.
                matches_length.append(match.end(0) - match.start(0))

            if line_matches != []:
                self.find_results.line_and_index[y] = line_matches
                self.find_results.line_match_length[y] = matches_length
                #Add the lines matches to the counter.
                match_counter += len(line_matches)

        #Changes the prompt to show how many matches were found for the entered pattern.
        self.prompt.change_prompt("Found {} matches for \"{}\"".format(match_counter, pattern_to_find))

        if len(self.find_results.line_and_index) != 0:
            #Set the length of the current matched string.
            self.find_results.find_enabled = True
            self.find_results.current_match_line = 0

            #If matches were found set the cursor to the first one. The match handler can be used to set the cursor
            #to the current match by just passing 0 as the change.
            self.match_line_handler(0)


    """
    TOOL CONSOLE FUNCTIONS
    """
    #Handles the console and processes it's commands.
    def tool_console_handler(self) -> None:
        #Disable editor prompt.
        self.prompt.toggle_prompt()

        #Get the command.
        basic_input = utils.BasicInput(self, self.y_size - 1, 0, "Command: ", self.get_colour(self.config_file["EDITOR-COLOUR"]["input-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["normal-cursor-colour"]), self.get_colour(self.config_file["TEXT-COLOUR"]["over-text-cursor-colour"]))
        #The "basic_input" method halts the program.
        full_command = basic_input.basic_input()

        #Re-enable editor prompt.
        self.prompt.toggle_prompt()

        #In case the user pressed the escape key.
        if full_command == None:
            return

        command_name = full_command.split()[0]
        command_arguments = full_command.split()[1:]

        match command_name:
            #Save and save as.
            case "s":
                #No filename was given.
                if len(command_arguments) == 0:
                    #If there's no filename given and no file then we cannot save.
                    if self.file == None:
                        self.prompt.change_prompt("No filename specified, cannot save")
                        return
                    else:
                        self.save_handler("Invalid argument type for save function")

                #A filename was given.
                elif len(command_arguments) == 1:
                    #Check if argument is a string.
                    if not isinstance(command_arguments[0], str):
                        return 1

                    #If a name was given then set it as the filename.
                    self.file = command_arguments[0]
                    self.save_handler()
                else:
                    self.prompt.change_prompt("Too many arguments for save function")
                    return

            #Load.
            case "o":
                #In case there are too many or to few arguments
                if self.argument_count(command_arguments, [str],"No filename specified, cannot load", "load function"):
                    return

                #Load file
                self.load_handler(command_arguments[0])

            #Exit.
            case "q":
                #In case there are too many or to few arguments
                if self.argument_count(command_arguments, [], "", "quit function"):
                    return

                #Check if there are unsaved changes.
                if self.buffer_modification_counter > 0:
                    self.prompt.change_prompt("Unsaved changes, use \"qf\" to quit without saving")
                else:
                    #Exit editor.
                    curses.endwin()
                    quit()

            #Force exit.
            case "qf":
                #In case there are too many or to few arguments
                if self.argument_count(command_arguments, [], "", "force quit function"):
                    return

                #Exit editor.
                curses.endwin()
                quit()

            #Find.
            case "f":
                #In case there are too many or to few arguments
                if self.argument_count(command_arguments, [str], "No text specified, cannot find", "find function"):
                    return

                self.find_handler(command_arguments[0])

            #Word count.
            case "wc":
                #In case there are too many or to few arguments
                if self.argument_count(command_arguments, [], "", "word count function"):
                    return

                words = 0

                #Counts all strings composed of alphanumeric characters separated by spaces.
                for line in self.text:
                    for word in line.line_text.split():
                        if (word.isalpha()):
                            words += 1

                #Show the count as a prompt
                self.prompt.change_prompt("There are {} words".format(words))


            case "j":
                #In case there are too many or to few arguments
                if self.argument_count(command_arguments, [int], "No line number specified, cannot jump", "jump function"):
                    return

                #Make sure the line number is valid.
                if int(command_arguments[0]) < 0 or int(command_arguments[0]) > len(self.text):
                    self.prompt.change_prompt("Please enter a valid line number")
                    return

                #Calculates the amount to jump, the result is negated to then use the interline handler.
                new_cursor_pos = -(self.cursor_pos_y - int(command_arguments[0]) + 1)
                #Jump to desired line.
                self.interline_cursor_handler(new_cursor_pos)


            case "r":
                #In case there are too many or to few arguments
                if self.argument_count(command_arguments, [str, str], "Please specify a pattern to search and it's replacement", "replace function"):
                    return


            case _:
                self.prompt.change_prompt("Please enter a valid command!")


    #Automatically checks if the number of arguments supplied is correct, along with their types. Returns false if so,
    #otherwise returns true.
    def argument_count(self, args: list[str], args_type: list[Union[int, str, bool, float]], under_text: str, over_text: str) -> bool:
        #Make sure the correct number of arguments were passed.
        if (len(args) < len(args_type)):
            self.prompt.change_prompt(under_text)
            return True
        elif (len(args) > len(args_type)):
            self.prompt.change_prompt("Too many arguments for {}".format(over_text))
            return True

        #Check all arguments against their supposed type. The last variable in the for loop, "arg_num" is used in case
        #there's an error to show the position of the argument.
        for arg, arg_t, arg_num in zip(args, args_type, range(len(args))):
            #Check if the type is correct for every argument.
            if self.check_type(arg, arg_t):
                #If it's not get the types as strings. The cutting is done to eliminate the additional text added when
                #printing type. Ex: Removing everything in this string: "<class 'int'>" except "int".
                supposed_type = str(arg_t)[8:-2]

                #Change prompt to show type error.
                self.prompt.change_prompt("Invalid argument type, expected \"{}\" for argument in position {}".format(supposed_type, (arg_num + 1)))

                return True

        return False


    #Checks the given value against the given type, if successful returns 0.
    def check_type(self, value: Any, type: Callable) -> bool:
        #Tries to cast the value to the given type.
        try:
            type(value)
            return False
        #If the value
        except:
            return True



text_editor = TextEditor()
text_editor.setup()
text_editor.editor()