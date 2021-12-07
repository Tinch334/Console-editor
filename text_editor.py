from dataclasses import dataclass, field
import utils, curses, curses.ascii, math, os, re



#Each line is stored as a dataclass. They are similar to structs in other languages, however they retain all the
#characteristics of a class.
@dataclass
class Line:
    line_text: str = ""



#This class is what makes the search function work. It handles all the search cursor logic.
@dataclass
class SearchMatch:
    #This dictionary contains the line and index of a match. The line is the key for the dictionary entry.
    line_and_index:dict = field(default_factory=dict)
    #The length of the matched text.
    matched_text_length:int = 0
    #Whether or not the find function is currently active
    find_enabled:bool = False
    #The line of the the match the cursor was last set to.
    current_match_line:int = 0
    #The number of match in the line the cursor was last set to.
    current_match_number_in_line:int = 0


    #Allows to choose which of all the matched texts is selected. Automatically moves the cursor to it.
    def current_match_line_handler(self, change, class_ref):
        self.current_match_number_in_line += change

        #Check whether we are on a line with matches, if so cycle through them normally.
        if class_ref.cursor_pos_y in self.line_and_index:
            #Check if we are on a line with matches. If so check if there are any remaining matches in the current line.
            if self.current_match_number_in_line >= len(self.line_and_index[class_ref.cursor_pos_y]) or self.current_match_number_in_line < 0:
                #Move to the corresponding line depending on what the change was.
                self.current_match_line += change

                #If we get to the end or the beginning of the file go to the other end.
                if self.current_match_line < 0:
                    self.current_match_line = len(self.line_and_index) - 1
                elif self.current_match_line >= len(self.line_and_index):
                    self.current_match_line = 0

                #If we change lines in which match the cursor ends depends on whether we are moving "up" or "down". If we are
                #moving down we simply start at the first match in the next line. However if we are moving up we start on the
                #last match of the previous line. To do this we set "current_match_number_in_line" to the length of the list
                #of matches in that line -1.
                if change > 0:
                    self.current_match_number_in_line = 0
                else:
                    self.current_match_number_in_line = len(self.line_and_index[list(self.line_and_index.keys())[self.current_match_line]]) - 1

                #Move the cursor to the corresponding line.
                class_ref.cursor_pos_y = list(self.line_and_index.keys())[self.current_match_line]

            #Update the x position of the cursor. The x position of the cursor is set to the last char of the matched word
            #in case it's out of the screen so it will scroll and show the match.
            class_ref.cursor_pos_x = self.line_and_index[class_ref.cursor_pos_y][self.current_match_number_in_line] + self.matched_text_length

        #Otherwise go to the closest match.
        else:
            #Set the first match as the initial closest line.
            closest_line = list(self.line_and_index.keys())[0]

            for line in list(self.line_and_index.keys()):
                #If the difference between the cursor and the line is smaller than the difference to the current closest line
                #we have found a new closest line.
                if abs(class_ref.cursor_pos_y - line) < abs(class_ref.cursor_pos_y - closest_line):
                    closest_line = line

            class_ref.cursor_pos_y = closest_line

            #Update the x position of the cursor to the first match in that line.
            class_ref.cursor_pos_x = self.line_and_index[closest_line][0] + self.matched_text_length


#A simple prompt, with default text and the option to change it for a specified period of time. Beware that the prompt class
#only takes care of the actual text of the prompt, printing has to be handled by the user.
class Prompt:
    def __init__(self, default_prompt, restore_time_ms):
        self.default_prompt = default_prompt
        #How long the modified prompt will last in ms before being changed back to the default prompt.
        self.restore_time_ms = restore_time_ms

        self.prompt = default_prompt
        self.restore_time_counter = 0
        self.prompt_enabled = True


    def toggle_prompt(self):
        self.prompt_enabled = not self.prompt_enabled


    def change_prompt(self, new_prompt):
        self.prompt = new_prompt
        self.restore_time_counter = utils.ms_time()


    #Changes the new prompt back to the default prompt once the specified time has passed. Has to be called each program loop.
    def prompt_handler(self):
        if utils.ms_time() > self.restore_time_counter + self.restore_time_ms:
            self.prompt = self.default_prompt



#A simple FPS counter. It's very important to note that this simple class doesn't actually count the times the console buffer
#is printed, instead it counts how many times it was called in a second. Therefore to use this function it should be placed in
#your programs main loop so it's called every time it runs.
class FPSMeter:
    def __init__(self):
        self.start_time = 0
        self.fps_count = 0
        #Use this to get the FPS, it's updated once a second.
        self.fps_final_count = 0


    def fps_handler(self):
        if utils.ms_time() > self.start_time + 1000:
            self.fps_final_count = self.fps_count
            self.fps_count = 0

            self.start_time = utils.ms_time()
        else:
            self.fps_count += 1



class TextEditor(utils.CursesUtils):
    def __init__(self):
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
        self.prompt = Prompt("COMMANDS: Ctrl+S - save | Ctrl+O - open | Ctrl+F - find | Ctrl+Q - quit ", 3500)
        self.fps_meter = FPSMeter()

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

        #####NOTES#####
        """
        Something very important to remember about the editor is that the cursor and text are independent from the displayed
        text. The displayed text just matches wherever the cursor is, via "scroll_handler".
        """


    def editor(self):
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


    def detect_key(self):
        #Inserting text characters, this range covers all of extended ASCII.
        if self.key >= 32 and self.key <= 253:
            #Insert the given char at the current cursor position. Since python strings are immutable we create a new string
            #consisting of the previous string split where the cursor is plus the added character.
            text_before = self.text[self.cursor_pos_y].line_text[:self.cursor_pos_x]
            text_after = self.text[self.cursor_pos_y].line_text[self.cursor_pos_x:]
            self.text[self.cursor_pos_y].line_text = text_before + chr(self.key) + text_after

            #Move the cursor's position in that line.
            self.cursor_pos_x += 1
            #Update the desired cursor position
            self.desired_cursor_x_pos = self.cursor_pos_x

            #Disable the find function since the buffer was modified.
            self.find_results.find_enabled = False
            #Increment the buffer modification counter.
            self.buffer_modification_counter += 1

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

            #Disable the find function since the buffer was modified.
            self.find_results.find_enabled = False
            #Increment the buffer modification counter.
            self.buffer_modification_counter += 1

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

            #Disable the find function since the buffer was modified.
            self.find_results.find_enabled = False
            #Increment the buffer modification counter.
            self.buffer_modification_counter += 1

        #Enter key
        #The actual code given by the enter key is 10, however the rest are left here for compatibility. Beware that
        #"CTRL+J" also has a keycode of 10.
        elif self.key == 10 or self.key == 13 or self.key == curses.KEY_ENTER:
            #When enter is pressed all the text to the right of the cursor goes down to the new line.
            text_before = self.text[self.cursor_pos_y].line_text[:self.cursor_pos_x]
            text_after = self.text[self.cursor_pos_y].line_text[self.cursor_pos_x:]

            #The old line retains what was left of the cursor.
            self.text[self.cursor_pos_y].line_text = text_before

            #Create the new line and add corresponding text.
            self.text.insert(self.cursor_pos_y + 1, Line())
            self.text[self.cursor_pos_y + 1].line_text = text_after

            self.cursor_pos_y += 1
            self.cursor_pos_x = 0
            self.desired_cursor_x_pos = 0

            #Disable the find function since the buffer was modified.
            self.find_results.find_enabled = False
            #Increment the buffer modification counter.
            self.buffer_modification_counter += 1

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
                self.find_results.current_match_line_handler(-1, self)
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
                self.find_results.current_match_line_handler(1, self)
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

        #"CTRL+Q" - TEMPORARY
        elif self.key == ord("Q") - 64:
            curses.endwin()
            quit()


        #"CTRL+S" key combination.
        elif self.key == ord("S") - 64:
            if self.file == None:
                #Disable editor prompt.
                self.prompt.toggle_prompt()

                basic_input = utils.BasicInput(self, self.y_size - 1, 0, "Open file: ", self.get_colour("WHITE_BLACK"))
                #The "basic_input" method halts the program.
                file = basic_input.basic_input()

                #Re-enable editor prompt.
                self.prompt.toggle_prompt()

                #In case the user pressed escape to cancel.
                if file == None:
                    return
                #Set the file.
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

        #"CTRL+O" key combination.
        elif self.key == ord("O") - 64:
            #Save the file the user is currently working on. If it has a name.
            if self.file != None:
                self.save_file(os.path.join(os.getcwd(), self.file))
           
            #Disable editor prompt.
            self.prompt.toggle_prompt()

            basic_input = utils.BasicInput(self, self.y_size - 1, 0, "Open file: ", self.get_colour("WHITE_BLACK"))
            #The "basic_input" method halts the program.
            file = basic_input.basic_input()

            #Re-enable editor prompt.
            self.prompt.toggle_prompt()

            #In case the user pressed escape to cancel.
            if file == None:
                return
            else:
                #Get complete filepath.
                path = os.path.join(os.getcwd(), file)

                #Make sure the path we are trying to read exists.
                if os.path.lexists(path):
                    #Open the file in the given path.
                    if self.load_file(path, True) == 0:
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

        #"CTRL+F" key combination.
        elif self.key == ord("F") - 64:
            #Disable editor prompt.
            self.prompt.toggle_prompt()

            basic_input = utils.BasicInput(self, self.y_size - 1, 0, "Find: ", self.get_colour("WHITE_BLACK"))
            #The "basic_input" method halts the program.
            pattern_to_find = basic_input.basic_input()

            #Re-enable editor prompt.
            self.prompt.toggle_prompt()

            #The user actually pressed enter and not the escape key.
            if pattern_to_find != None:
                #Remove any previous matched text.
                self.find_results.line_and_index = {}

                #Used to display how many matches were found using the prompt. It's more efficient to simply have a counter
                #than accessing a dictionary .
                match_counter = 0

                #Gets every match in a line and puts it in an array. Then that array is added to the dictionary using the line
                #as it's key.
                for y in range(0, len(self.text)):
                    line_matches = []
                    
                    for match in re.finditer(pattern_to_find, self.text[y].line_text):
                        line_matches.append(match.start(0))

                    if line_matches != []:
                        self.find_results.line_and_index[y] = line_matches
                        #Add the lines matches to the counter.
                        match_counter += len(line_matches)

                #Changes the prompt to show how many matches were found for the entered pattern.
                self.prompt.change_prompt("Found {} matches for \"{}\"".format(match_counter, pattern_to_find))

                if len(self.find_results.line_and_index) != 0:
                    #Set the length of the current matched string.
                    self.find_results.matched_text_length = len(pattern_to_find)
                    self.find_results.find_enabled = True
                    self.find_results.current_match_line = 0

                    #If matches were found set the cursor to the first one. The match handler can be used to set the cursor
                    #to the current match by just passing 0 as the change.
                    self.find_results.current_match_line_handler(0, self)


    #Allows for vertical and horizontal scrolling.
    def scroll_handler(self):
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
    def interline_cursor_handler(self, line_index):
        moving_to_line_length = len(self.text[self.cursor_pos_y + line_index].line_text)

        #If the line to move to is shorter than the desired cursor length go to the end of the line.
        if self.desired_cursor_x_pos > moving_to_line_length:
            self.cursor_pos_x = moving_to_line_length
        #Otherwise just keep the desired cursor position.
        else:
            self.cursor_pos_x = self.desired_cursor_x_pos

        #Update the y position of the cursor.
        self.cursor_pos_y += line_index


    #Displays the buffer and cursor. Also handles search function highlighting.
    def display(self):
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
        matched_text_index = 0


        #Prints the text, matched text from the found function and the cursor.
        for y in range(self.vertical_scroll_line, self.vertical_scroll_line + self.max_displayed_lines):
            #This is so that if there are less than "self.vertical_scroll_line + self.max_displayed_lines" lines(Empty lines)
            #the program doesn't try to address non existing lines. Instead it shows "~" to denote no lines.
            if y > line_count - 1:
                self.stdscr.addstr(print_y, 0, "~", self.get_colour("WHITE_BLACK"))

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
                else:
                    matched_text_indexes = []

                #Print line number. Since we're printing y + 1 we must also use y + 1 in the length calculation with the 
                #logarithm. This also solves the problem with index 0 since 0 + 1 = 1.
                line_number_text = " " * (line_display_width - (int(math.log10(y + 1)) + 1)) + str(y + 1)
                self.stdscr.addstr(print_y, 0, line_number_text, self.get_colour("BLACK_WHITE"))

                #Print line. The text we want to print is the one between the horizontal scroll and the end of the screen            
                for x in range(self.horizontal_scroll_character, self.horizontal_scroll_character + self.max_text_width):
                    #In case the text is shorter than the range of the for loop.
                    if x > len(line.line_text) - 1:
                        break

                    char = line.line_text[x]

                    self.stdscr.addstr(print_y, print_x, char, self.get_colour("WHITE_BLACK"))

                    #If the current line has matched text that has to be highlighted, and the current x char is on the correct
                    #range highlight it by printing over the original white text.
                    if matched_text_indexes != []:
                        for match in matched_text_indexes:
                            if x >= match and x < match + self.find_results.matched_text_length:
                                self.stdscr.addstr(print_y, print_x, char, self.get_colour("WHITE_BLUE"))

                    print_x += 1

            #Print the cursor, it has to be printed after the text to appear over it.
            if self.cursor_pos_y == y:
                #Apart of taking the line display into account the horizontal scroll has to be subtracted, so in case it's
                #not zero and the text is shifted the cursor will follow.
                cursor_x_print_pos = self.cursor_pos_x + line_display_width - self.horizontal_scroll_character

                #Detect if you are in the last char or and react accordingly.
                if self.cursor_pos_x == len(line.line_text):
                    self.stdscr.addstr(print_y, cursor_x_print_pos, " ", self.get_colour("WHITE_WHITE"))
                else:
                    self.stdscr.addstr(print_y, cursor_x_print_pos, line.line_text[self.cursor_pos_x], self.get_colour("BLACK_WHITE"))

            print_y += 1
            

    #Shows the status and help bar.
    def status_bar(self):
        #Automatically determines what the displayed filename should be, depending on whether or not a name has been given.
        #Also displays whether or not the file is "dirty", if it's been modified since loading or saving. Shows the FPS meter,
        #it's mainly there for efficiency testing.
        filename_text = self.file if self.file != None else "[No filename]"
        line_text = str(len(self.text)) + " lines"
        modified_text = " (modified)" if self.buffer_modification_counter > 0 else ""
        fps_text = "FPS: " + str(self.fps_meter.fps_final_count)
        left_status_text = filename_text + " - " + line_text + modified_text + " - " + fps_text
        
        #The cursor position indicator.
        right_status_text = str(self.cursor_pos_y + 1) + "," + str(self.cursor_pos_x + 1) + " "

        #The complete status bar.
        status_text = left_status_text + " " * (self.x_size - len(left_status_text) - len(right_status_text)) + right_status_text

        #Print the status bar
        self.addstrex(self.max_displayed_lines, 0, status_text, self.get_colour("WHITE_BLUE"))

        #If the editor prompt is enabled print it.
        if self.prompt.prompt_enabled:
            self.stdscr.addstr(self.max_displayed_lines + 1, 0, self.prompt.prompt, self.get_colour("WHITE_BLACK"))


    #Has all the functions that need to be called to properly display all screen elements. It's mostly for ease of use of the
    #"BasicInput" class.
    def print_screen(self):
        self.display()
        self.status_bar()

    #Saves the current file to the given path, returns 1 if it was successful.
    def save_file(self, path):
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

            return 0

        #In case an unexpected error occurs.
        except:
            return 1


    #Loads the file in the given path, returns 1 if it was successful.
    def load_file(self, path, prompt = True):
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

            return 0

        #In case an unexpected error occurs.
        except:
            return 1



text_editor = TextEditor()
text_editor.editor()