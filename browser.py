#!/bin/env python

from asyncio import get_event_loop, new_event_loop, set_event_loop
from json import loads
from os import listdir, mkdir
from os.path import expanduser, isdir, isfile, join, relpath
from re import match
from subprocess import getoutput, run
from typing import Dict, List, TypedDict, Union

from brotab.api import MultipleMediatorsAPI
from brotab.main import create_clients
from urllib.error import HTTPError


# TODO warn if bt-mediator down!

# TODO document jq dependency... or replicate its used functionality in python

# TODO indicate which windows belong to which browser

# TODO whitelist/blacklist browser(s)


ignored_urls = ["about:blank",
                "https://www.facebook.com/",
                "https://www.linkedin.com/feed/"]

folder = join(expanduser('~'), "urls-tab_wrangler")

if not isdir(folder):
  mkdir(folder)

class Tab(TypedDict):
  id:    str
  title: str
  url:   str

def get_windows() -> Dict[str, List[Tab]]:

  api = MultipleMediatorsAPI(create_clients())

  set_event_loop(new_event_loop())

  tabs = api.list_tabs(args=[]) # FIXME catch TimeoutError

  get_event_loop().close()

  windows: dict[str, list[Tab]] = {}

  for tab in tabs:

    tab_info = tab.split("\t")

    try:

      identifier = tab_info[0]

      window_id = identifier.rsplit('.', maxsplit=1)[0]

      if window_id not in windows:
        windows[window_id] = []

      windows[window_id].append({"id":    tab_info[0],
                                 "title": tab_info[1].replace("💤 ", ''),
                                 "url":   tab_info[2]})

      # FIXME crash on browser closed or bt-mediator down
        # File "/home/casey/tab_wrangler/browser.py", line 57, in get_windows
          # "title": tab_info[1].replace("💤 ", ''),
                   # ~~~~~~~~^^^
      # IndexError: list index out of range

      # hmm, ran into a rare case where a tab lacked a url
        # print(tab_info)
        # ['a.85.10', 'It is']
      # this page caused & reproducibly causes it:
        # https://www.really-learn-english.com/it-is-vs-there-is.html
      # a normal one looks like:
        # ['a.85.17', 'There is...', 'https://learnenglishteens...']
      # FIXME handle this!

    except IndexError as error:

      if  len(tab_info) != 3:

        with open("/tmp/debug", 'w') as debugging_log:
          debugging_log.write(f"incorrect tab_info length {len(tab_info)}: "
                              f"{tab_info}\n")
        # after browser crash:
          # incorrect tab_info length 1: ['b.<ERROR>']

      raise error # TODO handle, don't crash
        # display temporary error message
        # try to reestablish connection on regain focus

      # FIXME
        # File "/home/casey/tab_wrangler/browser.py", line 57, in get_windows
          # "title": tab_info[1].replace("💤 ", ''),
          # IndexError: list index out of range

  return windows

class Window(TypedDict):
  title: str
  tabs:  List[Tab]

def close(windows: List[Window]) -> Union[str, HTTPError]:

  tab_list = [tab["id"]
                    for window in windows
                    for tab in window["tabs"]]

  api = MultipleMediatorsAPI(create_clients())

  set_event_loop(new_event_loop())

  if len(tab_list) == len(api.list_tabs(args=[])):
    api.open_urls(urls=["about:blank"], prefix="a.")

  try:
    api.close_tabs(tab_list)
  except HTTPError as http_error:
    return http_error

  get_event_loop().close()

  return (f"closed {len(windows)} window"
          + ("s " if len(windows) > 1 else ' ')
          + f"and {sum([len(window['tabs']) for window in windows])} tab"
          + ("s " if len(windows[0]['tabs']) > 1 else ' '))

def save_and_close(windows: List[Window],
                   name:    str = None
                   ) -> Union[str, HTTPError]:

  subfolder = folder

  if name is None:
    if any([window["title"] is None for window in windows]):
      subfolder = join(folder, "untitled")
  elif (len(windows) > 1
        or windows[0]["title"] is not None
        or isdir(join(folder, name))):
    subfolder = join(folder, name)
    name = None
  # TODO why the elIF clause above if no else clause?
    # i guess then subfolder stays folder and name does NOT become None
    # but the logic of what is going on here is not very clear... do better.

  if not isdir(subfolder):
    mkdir(subfolder)

  file_indices = [int(filename)
                  for filename in listdir(subfolder)
                  if match(r"^[0-9]+$", filename)]

  if len(file_indices):
    index = max(file_indices) + 1

  else:
    index = 0

  api = MultipleMediatorsAPI(create_clients())

  set_event_loop(new_event_loop())

  window_count = len(windows)

  for window_number, window in enumerate(windows):

    contents = "\n".join([f"{tab['title']}\t{tab['url']}"
                          for tab in window["tabs"]
                          if tab['url'] not in ignored_urls])

    if contents:

      # TODO prevent duplicates

      if window["title"] is not None:
        file_path = join(subfolder, window["title"])

      else: # window["title"] is None
        if len(windows) == 1 and name is not None:
          file_path = join(folder, name)
        else:
          file_path = join(subfolder, f"{index:04}")
          index += 1

      appended = False

      if isfile(file_path):
        appended = True
        contents = "\n" + contents

      with open(file_path, 'a') as output:
        # FIXME IsADirectoryError: [Errno 21] Is a directory:
          # '/home/casey/urls-tab_wrangler/linkedin'
        output.write(contents)

      with open("/tmp/debug", 'w') as debugging_log:
        # TODO remove this block after hopefully figuring out the error below
        debugging_log.write(f"{window_number}\n")
        debugging_log.write(f"{window_count - 1}\n")

    if (    window_number == window_count - 1
        and len(api.list_tabs(args=[])) == len(window["tabs"])):

          api.open_urls(urls=["about:blank"], prefix="a.")

          # TODO consider multiple browsers, different prefixes

    try:
      # FIXME urllib.error.URLError:
        # <urlopen error [Errno 99] Cannot assign requested address>
      api.close_tabs([tab["id"] for tab in window["tabs"]])
    except HTTPError as http_error:
      return http_error

  get_event_loop().close()

  if len(windows) == 1:

    if contents:
      return (f"window with {len(windows[0]['tabs'])} tab"
              + ("s " if len(windows[0]['tabs']) > 1 else ' ')
              + ("appended to " if appended else "saved as ")
              + relpath(file_path, folder))

    else:
      return (f"window with {len(windows[0]['tabs'])} tab"
              + ("s " if len(windows[0]['tabs']) > 1 else ' ')
              + "discarded")

  return (f"{len(windows)} windows "
          + f"and {sum([len(window['tabs']) for window in windows])} tabs "
          + "saved and closed")

def focus_window(window_id: str) -> None:

  target_browser, target_window_id = window_id.split('.')

  api = MultipleMediatorsAPI(create_clients())

  set_event_loop(new_event_loop())

  for browser in api.get_active_tabs(args=[]):
    # FIXME urllib.error.URLError: <urlopen error [Errno 99] Cannot assign requested address>
      # just retry once?

    for id in browser:

      browser, window_id, tab_id = id.split('.')

      if browser != target_browser:
        break

      if window_id == target_window_id:

        for tab in api.list_tabs(args=[]):

          tab_id, tab_title, _ = tab.split("\t")

          if tab_id == id:

            # FIXME doesn't work if window title is non-unique
            # FIXME doesn't work if window title contains an apostrophe

            if "'" in tab_title:
              tab_title =  tab_title[:tab_title.index("'")]

            if '"' in tab_title:
              tab_title =  tab_title.replace('"', '\\"')

            # TODO yeah, i should really do away with the jq dependency and be able to handle apostrophes...

            # TODO at least add back in: select(.type?=="con") 

            con_id = getoutput("swaymsg -t get_tree "
                               "| jq '.. | objects | .nodes?[]? | "
                               "select(.type? == \"con\") | "
                               "select(.name? != null) | "
                               f"select(.name? | startswith(\"{tab_title}\")) "
                               "| .id?'")

            if "\n" in con_id:
              con_id = con_id.split("\n")[0] # FIXME temporary workaround cheat

            # TODO account for different browsers

            # TODO move sway stuff into its own module

            # TODO how to reliably check if sway vs. x11, or neither?
            run(["swaymsg", f"[con_id={con_id}]", "focus"])
            # run(["wmctrl", "a", f"{tab_title}"]) # iirc... TODO double-check

  get_event_loop().close()
