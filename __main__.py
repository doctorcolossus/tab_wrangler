#!/bin/env python

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
from urwid.signals import MetaSignals

from tab_wrangler.browser import get_windows, close, save_and_close


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

    self.window_count  = Text(markup='')
    self.tab_count = Text(markup='')

    self.update_window_list()

    connect_signal(obj=self, name="modified", callback=self._update_tab_list)

  @property
  def window_ids(self):
    return [window.id for window in self]

  def update_window_list(self):

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("update_window_list()\n")

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

    self.window_count.set_text(
      markup = f" {len(self.windows)} windows,"
               f" {sum([len(window) for window in self.windows])} tabs")

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("\n")

  def _update_tab_list(self):

    if len(self):

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

    self._save_prompt = EditBox()

    self._status_bar = Text(markup='')

    connect_signal(obj=self._save_prompt, name="done", callback=self._write_windows)

    self._single_footer = Frame(body   = columns,
                                footer = self._save_prompt)

    self.focus_position = 0 # FIXME ensure at least one window

    self._remember_relative_position()

    self.main_loop = MainLoop(widget  = self._split_footers,
                              palette = palette)

    # from os.path import isfile
    # if isfile("/tmp/debug"):
      # from os import remove
      # remove("/tmp/debug")

  def _remember_relative_position(self):

   # FIXME ensure at least one window before trying to access self.focus_position
    self._ids_preceding = self.body.window_ids[:self.focus_position]
    self._ids_following = self.body.window_ids[(self.focus_position + 1):]

    # with open("/tmp/debug", 'a') as debug:
      # debug.write(f"self.focus_position: {self.focus_position}\n")
      # debug.write(f"self.body.window_ids: {self.body.window_ids}\n")
      # debug.write(f"ids preceding: {self._ids_preceding}\n")
      # debug.write(f"ids following: {self._ids_following}\n")
      # debug.write("\n")

  def _set_position(self, index):
    self.focus_position = index
    self._remember_relative_position()

  def _decrement_position(self):

    index = len(self.body) - 1

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("decrementing position...\n")
      # debug.write(f"current focus: {self.body[self.focus_position].id} at index {self.focus_position}\n")
      # debug.write(f"ids preceding: {self._ids_preceding}\n")
      # debug.write(f"ids following: {self._ids_following}\n")

    for window_id in reversed(self._ids_preceding):

      try:
        index = self.body.window_ids.index(window_id)
        # with open("/tmp/debug", 'a') as debug:
          # debug.write(f"previous window: {window_id}, at index {index}\n")
      except ValueError:
        continue

      break

    self._set_position(index)

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("\n")

    # if  self.focus_position > 0:
      # self.focus_position -= 1
    # else:
      # self.focus_position = len(self.body) - 1

  def _increment_position(self):

    index = None

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("incrementing position...\n")
      # debug.write(f"current focus: {self.body[self.focus_position].id} at index {self.focus_position}\n")
      # debug.write(f"ids preceding: {self._ids_preceding}\n")
      # debug.write(f"ids following: {self._ids_following}\n")

    for window_id in self._ids_following:

      try:
        index = self.body.window_ids.index(window_id)
        # with open("/tmp/debug", 'a') as debug:
          # debug.write(f"next window: {window_id}, at index {index}\n")
      except ValueError:
        continue

      break

    if index is None:

      index = self.focus_position + 1

      if len(self.body) <= index:
        index = 0

      # with open("/tmp/debug", 'a') as debug:
        # debug.write(f"no next window found - setting index to {index}\n")

    self._set_position(index)

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("\n")

    # if self.focus_position < (len(self.body) - 1):
      # self.focus_position += 1
    # else:
      # self.focus_position = 0

  def keypress(self, size, key):

    if key == 'q':
      raise ExitMainLoop()

    self.main_loop.widget = self._split_footers # hide any recent status message

    self.body.update_window_list()

    if key == ' ':
      checkbox = self.body[self.focus_position].base_widget
      checkbox.state = not checkbox.state

    if key in ('k', 'up'):
      self._decrement_position()

    if key in (' ', 'j', "down"): # TODO make ' ' continue in the last-used direction (up or down)
      self._increment_position()

    if key == 'g':
      self._set_position(0)

    if key == 'G':
      self._set_position(len(self.body) - 1)

    if key == 'd':

      status = close(windows = self._selected_windows_with_tabs)

      self._update_and_set_status(status=status)

    if key == 's':

      status = save_and_close(windows = self._selected_windows_with_tabs)

      self._update_and_set_status(status=status)

    if key == 'w':

      if len(self._selected_windows) == 1:
        # TODO check if the window has a title
          # if so, prompt for FOLDER name (rather than file name)
          # if not, prompt for filename
        self._save_prompt.set_caption("filename: ")
      else: # len(self._selected_windows) > 1
        self._save_prompt.set_caption("folder name: ")

      # TODO somehow lock the window list if possible until input is complete
        # otherwise the selected windows could change, and they shouldn't at this point

      self._single_footer.footer = self._save_prompt

      self._single_footer.focus_position = "footer"

      self.main_loop.widget = self._single_footer

  @property
  def _selected_windows(self):

      selected_windows = []

      for item in self.body:
        checkbox = item.base_widget
        if checkbox.state == True:
          selected_windows.append(item)

      if len(selected_windows) == 0:
        selected_windows.append(self.body[self.focus_position])

      return selected_windows

  @property
  def _selected_windows_with_tabs(self):

    # FIXME handle window(s) already closed

    return [{"title": None, # TODO
             "tabs": self.body.windows[item.id]}
             for item in self._selected_windows]

  def _write_windows(self, save_prompt):

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("_write_windows()\n")

    name = save_prompt.get_edit_text()

    save_prompt.set_caption('')

    status = save_and_close(windows = self._selected_windows_with_tabs,
                            name    = name)

    self._update_and_set_status(status=status)

  def _set_status(self, status):

    self._status_bar.set_text(str(status))

    self._single_footer.footer = self._status_bar

    self.main_loop.widget = self._single_footer

  def _update_and_set_status(self, status):

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("_update_and_set_status()\n")

    self._set_status(status)

    if not isinstance(status, HTTPError):

      focus_position = self.focus_position

      # with open("/tmp/debug", 'a') as debug:
        # debug.write(f"current focus: {self.body[focus_position].id} at index {focus_position}\n")

      window_count = len(self.body)

      index = 0

      selected_window_ids = [window.id for window in self._selected_windows]

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
        # debug.write(f"new focus: {self.body[focus_position].id} at index {self.focus_position}\n")
        # debug.write("\n")

      self._set_position(focus_position)

      self._single_footer.focus_position = "body"

    # with open("/tmp/debug", 'a') as debug:
      # debug.write("\n")

palette = [("window browser", "default",    "default"),
           ("focused",        "black",      "light gray"),
           ("tab browser",    "dark green", "default")]

terminal_title = "tabwrangler"
print(f'\33]0;{terminal_title}\a', end='', flush=True)

WindowListBox(body=WindowListWalker()).main_loop.run()
