#!/bin/env python

from atexit import register

from urwid import (AttrMap,
                   Button,
                   CheckBox,
                   Columns,
                   Divider,
                   Edit,
                   ExitMainLoop,
                   Frame,
                   LineBox,
                   ListBox,
                   MainLoop,
                   Overlay,
                   Pile,
                   SelectableIcon,
                   SolidFill,
                   Text,
                   SimpleFocusListWalker,
                   connect_signal,
                   emit_signal)

from urllib.error import HTTPError
from urwid.raw_display import Screen
from urwid.signals import MetaSignals

from tab_wrangler.browser \
  import get_windows, close, save_and_close, focus_window
  # TODO focus_window should be imported from WM/DE module - not browser


class EditBox(Edit):

  _metaclass_ = MetaSignals  
  signals = ["done"]

  def keypress(self, size, key):

    if key == "enter":
      emit_signal(self, "done", self)
      super().set_edit_text('')
      return

    elif key == "esc":
      super().set_edit_text('')
      return

    Edit.keypress(self, size, key)

class WindowListWalker(SimpleFocusListWalker):

  def __init__(self, *args, **kwargs):

    super().__init__(contents=[], *args, **kwargs)

    self.tab_list_walker = SimpleFocusListWalker(contents=[])

    self.window_count = Text(markup='')
    self.tab_count = Text(markup='')

    self.update_window_list()

    self._remember_relative_position()

    connect_signal(obj      = self,
                   name     = "modified",
                   callback = self._update_tab_list)

    connect_signal(obj      = self,
                   name     = "modified",
                   callback = self._remember_relative_position)

  @property
  def window_ids(self):
    return [window.id for window in self]

  def update_window_list(self):

    # FIXME if the browser is closed and all windows thus get deselected, tab list must be cleared

    # TODO read enough closed windows to fill list
      # _, terminal_height = Screen().get_cols_rows()

    self.windows = get_windows()

    window_ids = list(self.windows.keys())

    window_count = len(self)

    index = 0

    while index < window_count:

      window_id = self[index].id

      if window_id not in window_ids:
        # with open("/tmp/debug", 'a') as debug:
          # debug.write(f"removing window {window_id} at index {index}\n")
        del self[index]
        window_count -= 1

      else:

        tab_count = len(self.windows[window_id])
        checkbox = self[index].base_widget
        checkbox.set_label(f"{tab_count} tab{'s' if tab_count > 1 else ''}")

        index += 1

    listed_window_ids = [window.id for window in self]

    unlisted_windows = list(set(window_ids) - set(listed_window_ids))

    for window_id in unlisted_windows:

      tabs = self.windows[window_id]

      tab_count = len(tabs)

      checkbox = CheckBox(
        label = f"{tab_count} tab{'s' if tab_count > 1 else ''}")

      attribute_map = AttrMap(w         = checkbox,
                              attr_map  = "window browser",
                              focus_map = "focused")

      attribute_map.id = window_id

      # with open("/tmp/debug", 'a') as debug:
        # debug.write(f"adding window {window_id} at index {len(self)}\n")

      self.append(attribute_map)

    tab_count = sum([len(window) for window in self.windows.values()])

    self.window_count.set_text(
      markup = (  f" {len(self.windows)} "
                + "window" + ('s' if len(self.windows) > 1 else '') + ", "
                + f"{tab_count} "
                + "tab" + ('s' if tab_count > 1 else '')))

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("\n")

  def _update_tab_list(self):

    if self.focus is None:

      self.tab_list_walker.clear()

    else:

      focused_item = self.get_focus()[0]
    
      if focused_item is not None:

        window_id = focused_item.id

        self.tab_list_walker.clear()

        if window_id in self.windows:

            # TODO different colors for title & url
            self.tab_list_walker.extend([SelectableIcon(tab["title"] +
                                                        f" [{tab['url']}]")
                                         for tab in self.windows[window_id]])

            for item in self.tab_list_walker:
              item.set_layout(align="left", wrap="ellipsis")

            tab_count = len(self.windows[window_id])

            self.tab_count.set_text(
              f" {tab_count} tab{'s' if tab_count > 1 else ''}")

  def _remember_relative_position(self):

    if self.focus is not None:

      self._ids_preceding = self.window_ids[:self.focus]

      self._ids_following = self.window_ids[(self.focus + 1):]

  def decrement_position(self):

    if self.focus is None:
      return

    index = len(self) - 1

    for window_id in reversed(self._ids_preceding):

      try:
        index = self.window_ids.index(window_id)
      except ValueError:
        continue

      break

    self.set_focus(index)

  def increment_position(self):

    if self.focus is None:
      return

    index = None

    for window_id in self._ids_following:

      try:
        index = self.window_ids.index(window_id)
      except ValueError:
        continue

      break

    if index is None:

      index = self.focus + 1

      if len(self) <= index:
        index = 0

    self.set_focus(index)


class WindowListBox(ListBox):

  def __init__(self, *args, **kwargs):

    super().__init__(*args, **kwargs)

    tab_listbox = ListBox(body=self.body.tab_list_walker)

    left_column, right_column = [LineBox(Overlay(top_w    = listbox,
                                                 bottom_w = SolidFill(),
                                                 align    = "center",
                                                 width    = ("relative", 100),
                                                 valign   = "middle",
                                                 height   = ("relative", 100),
                                                 left     = 1,
                                                 right    = 1,
                                                 ))
                                 for listbox in (self, tab_listbox)]

    left_column_frame  = Frame(body   = left_column,
                               footer = self.body.window_count)

    right_column_frame = Frame(body   = right_column,
                               footer = self.body.tab_count)

    self._split_footers = Columns(widget_list=[(32, left_column_frame),
                                               right_column_frame])

    columns = Columns(widget_list=[(32, left_column), right_column])

    self._mode = "normal"

    self._control_sequence = False

    self._focus_position_before_search = None

    self._search_query = None

    self._search_forwards = True

    self._save_prompt = EditBox()

    self._status_bar = Text(markup='')

    connect_signal(obj      = self._save_prompt,
                   name     = "done",
                   callback = self._write_windows)

    self._single_footer = Frame(body   = columns,
                                footer = self._save_prompt)

    if self.focus is not None:
      self.focus_position = 0

    self.main_loop = MainLoop(widget  = self._split_footers,
                              palette = palette)

    # from os.path import isfile
    # if isfile("/tmp/debug"):
      # from os import remove
      # remove("/tmp/debug")

  def keypress(self, size, key):

    if key == "meta [":

      self._control_sequence = True

      return

    if self._control_sequence is True:

      self._control_sequence = False

      if key == 'I': # focus gained
        self.body.update_window_list()

      return

    if self._mode == "search":
      # TODO remember starting selection, to revert in case search canceled
      # TODO actually implement search
        # start from the currently-selected window, wrap around... then search saved?
          # or simply start from the "first" window and work down?
        # case insensitive or nah?
      # TODO handle 'enter'
      # TODO filter out any unexpected non-alphanumeric keys... while still allowing weird languages
      # TODO save last query for n/N
      # TODO implement search direction with ?-/
      # TODO handle cursor with left/write arrow keys
      # TODO handle delete
      # TODO handle ctrl+w

      if key == "enter":
        # TODO actually to be like vim, for enter i should exit search mode but leave search query displayed without cursor until next keystroke
          # or should enter immediately activate and focus the tab?
        self._mode = "normal"
        self.main_loop.widget = self._split_footers # TODO make a method which does this, for readability
        return

      if (   (key == "esc")
          or (key == "backspace" and len(self._status_bar.text) == 2)):
        # TODO restore previous selection on canceling search
        self.focus_position = self._focus_position_before_search
        self._mode = "normal"
        self.main_loop.widget = self._split_footers # TODO make a method which does this, for readability
        return

      if key == "backspace":
        if len(self._status_bar.text) > 2:
          self._status_bar.set_text(self._status_bar.text[:-2] + '█')
      elif key == "ctrl u":
        self._status_bar.set_text(self._status_bar.text[0] + '█')
      else:
        self._status_bar.set_text(self._status_bar.text[:-1] + key + '█')

      self._search_query = self._status_bar.text[1:-1].lower()

      self._search()

      return

    if key == 'q':
      raise ExitMainLoop()

    self.main_loop.widget = self._split_footers # hide any recent status

    self.body.update_window_list()

    # TODO allow click to select but not check

    if key == '/':

      if self.focus is not None:
        self._focus_position_before_search = self.focus_position

      self._search_forwards = True

      self._set_status(status="/█")

      self._mode = "search"

      return

    if key == '?':

      if self.focus is not None:
        self._focus_position_before_search = self.focus_position

      self._search_forwards = False

      self._set_status(status="?█")

      self._mode = "search"

      return

    if key == 'n':

      if self.focus is not None:
        self._focus_position_before_search = self.focus_position

      self._search()

      return

    if key == 'N':

      if self.focus is not None:
        self._focus_position_before_search = self.focus_position

      self._search(reverse=True)

      return

    # Any & all keybindings depending on nonempty list should go below this.
    if len(self.body) == 0: 
      return

    if key == "enter":
      focus_window(self.body[self.focus_position].id)
      return

    if key == ' ':
      checkbox = self.body[self.focus_position].base_widget
      checkbox.state = not checkbox.state
      return

    if key in ('k', 'up'):
      self.body.decrement_position()
      return

    if key in (' ', 'j', "down"):
      # TODO make ' ' continue in the last-used direction (up or down)
      self.body.increment_position()
      return

    if key == 'g':
      self.focus_position = 0
      return

    if key == 'G':
      self.focus_position = len(self.body) - 1
      return

    if key == 'd':

      status = close(windows = self._selected_windows)

      self._set_status(status=status)

      self.body.update_window_list()

      self.focus_position = self.focus_position # trigger update tab list

      return

    if key == 's':

      status = save_and_close(windows = self._selected_windows)

      self._update_and_set_status(status=status)

      return

    if key == 'w':

      # TODO check selected window if no window checked
        # i think this is inferred somewhere in the browser code
          # but when user is prompted for a filename and list loses focus...
            # it's not visible which window is being saved
          # so simplify that code in the browser
            # and make it explicit here
      # TODO alternatively...
        # consider getting rid of the whole "save_prompt" thing
          # status bar can be used on its own...
            # i just need to handle backspace and other specific bindings
            # hmm, not so easy to implement cursor... and mouse bindings...
              # but with save prompt selected, listbox selection isn't visible

      # TODO handle blank input

      # TODO allow escape to cancel

      if len(self._selected_window_ids) == 1:
        # TODO check if the window has a title
          # if so, prompt for FOLDER name (rather than file name)
          # if not, prompt for filename
        self._save_prompt.set_caption("filename: ")
      else: # len(self._selected_window_ids) > 1
        self._save_prompt.set_caption("folder name: ")

      # TODO somehow lock the window list if possible until input is complete
        # otherwise selected windows could change
          # and they shouldn't at this point

      self._single_footer.footer = self._save_prompt

      self._single_footer.focus_position = "footer"

      self.main_loop.widget = self._single_footer

      return

    if key == 'c': # TODO add a key to just discard all WITHOUT saving

      status = save_and_close(windows = self._all_windows)
      # TODO update list dynamically, as each window is closed
        # i guess that'd require passing each window individually - not a list

      self._set_status(status=status)

      self.body.update_window_list()

      self.focus_position = 0 # trigger update tab list

    # TODO keys to switch between window & tabs list
      # key to toggle (tab?)
      # key to focus window/tab lists respectively
        # 'w' is taken... hmm... maybe 'h'/'l' like vim

  def _search(self, reverse=False):

    # TODO save search query history

    search_forwards = self._search_forwards

    if reverse is True:
      search_forwards = not search_forwards

    window_list = []

    if len(self.body) > 0:
      window_list = [*self.body[self._focus_position_before_search + 1: ],
                     *self.body[:self._focus_position_before_search]]

    if search_forwards is False:
      window_list = reversed(window_list)

    for window in window_list:
      tab_list = self.body.windows[window.id]
      if search_forwards is False:
        tab_list = reversed(tab_list)
      for tab in tab_list:
        if self._search_query in tab["title"].lower():
          self.focus_position = self.body.index(window)
          # TODO select the particular tab
            # TODO make tabs even selectable/browsable at all
          return

  @property
  def _selected_window_ids(self):

    selected_window_ids = []

    for item in self.body:
      checkbox = item.base_widget
      if checkbox.state == True:
        selected_window_ids.append(item.id)

    if len(selected_window_ids) == 0:
      selected_window_ids.append(self.body[self.focus_position].id)

    return selected_window_ids

  @property
  def _selected_windows(self):

    # FIXME handle window(s) already closed

    return [{"title": None, # TODO
             "tabs": self.body.windows[window_id]}
             for window_id in self._selected_window_ids]

  @property
  def _all_windows(self):

    # FIXME handle window(s) already closed

    return [{"title": None, # TODO
             "tabs": self.body.windows[item.id]}
             for item in self.body]

  def _write_windows(self, save_prompt):

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("_write_windows()\n")

    name = save_prompt.get_edit_text()

    save_prompt.set_caption('')

    status = save_and_close(windows = self._selected_windows,
                            name    = name)

    self._update_and_set_status(status=status)

  def _set_status(self, status):

    self._status_bar.set_text(str(status))

    self._single_footer.footer = self._status_bar

    self.main_loop.widget = self._single_footer

  def _update_and_set_status(self, status):
    """sets status, removes selected windows from list"""

    # TODO method should really be renamed, it's confused me numerous times now
      # only removes windows closed, doesn't add added ones (e.g. about:blank)
      # and perhaps setting status should simply always be done separately

    self._set_status(status)

    if not isinstance(status, HTTPError):

      focus_position = self.focus_position

      # with open("/tmp/debug", 'a') as debug:
        # debug.write(f"current focus: {self.body[focus_position].id} "
                    # f"at index {focus_position}\n")

      window_count = len(self.body)

      index = 0

      selected_window_ids = [window_id for window_id
                             in self._selected_window_ids]

      while index < window_count:

        window_id = self.body[index].id

        if window_id in selected_window_ids:

          if ((index < focus_position and focus_position > 0)
              or (focus_position == len(self.body) - 1)):
            focus_position -= 1

          # with open("/tmp/debug", 'a') as debug:
            # debug.write(f"removing window {window_id} at index {index}\n")

          del self.body[index]

          window_count -= 1

        else:
          index += 1

      # with open("/tmp/debug", 'a') as debug:
        # debug.write(f"new focus: {self.body[focus_position].id} "
                    # f"at index {self.focus_position}\n")

      self.focus_position = self.focus_position

      self._single_footer.focus_position = "body"

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("\n")

palette = [("window browser", "default",    "default"),
           ("focused",        "black",      "light gray"),
           ("tab browser",    "dark green", "default")]

terminal_title = "tabwrangler"
print(f'\33]0;{terminal_title}\a', end='', flush=True)

print('\x1b[?1004h', end='') # enable focus events
register(lambda: print('\x1b[?1004l', end='')) # disable focus events atexit
# https://unix.stackexchange.com/a/480138/85161

WindowListBox(body=WindowListWalker()).main_loop.run()
