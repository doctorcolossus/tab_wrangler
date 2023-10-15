#!/bin/env python

from asyncio import get_event_loop, new_event_loop, set_event_loop
from os import listdir, mkdir
from os.path import expanduser, isdir, isfile, join, relpath
from re import match
from typing import Dict, List, TypedDict

from brotab.api import MultipleMediatorsAPI
from brotab.main import create_clients
from urllib.error import HTTPError


ignored_urls = ["about:blank",
                "https://www.facebook.com/",
                "https://www.linkedin.com/feed/"]

api = MultipleMediatorsAPI(create_clients())

folder = join(expanduser('~'), "urls-tab_wrangler")

if not isdir(folder):
  mkdir(folder)

class Tab(TypedDict):
  id:    str
  title: str
  url:   str

def get_windows() -> dict[str, list[Tab]]:

  set_event_loop(new_event_loop())
  tabs = api.list_tabs(args=[])
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

    except IndexError as error:

      if  len(tab_info) != 3:
        print(f"incorrect tab_info length {len(tab_info)}: {tab_info}")

      raise error

  return windows

class Window(TypedDict):
  title: str
  tabs:  List[Tab]

def close(windows: List[Window]) -> str | HTTPError:

  tab_list = [tab["id"]
                    for window in windows
                    for tab in window["tabs"]]

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

def save_and_close(windows: List[Window], name=None) -> str | HTTPError:

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
