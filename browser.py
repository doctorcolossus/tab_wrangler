#!/bin/env python

from asyncio import get_event_loop, new_event_loop, set_event_loop
from os import listdir, mkdir
from os.path import expanduser, isdir, isfile, join, relpath
from re import match
from typing import Dict, List, TypedDict

from brotab.api import MultipleMediatorsAPI
from brotab.main import create_clients
from urllib.error import HTTPError


api = MultipleMediatorsAPI(create_clients()) # TODO should i use single mediator API instead?

folder = join(expanduser('~'), "urls-tab_wrangler")

if not isdir(folder):
  mkdir(folder)

class Tab(TypedDict):
  id:    str
  title: str
  url:   str

def get_windows() -> dict[str, list[Tab]]:

  set_event_loop(new_event_loop())
  tabs = api.list_tabs([])
  get_event_loop().close()

  windows: dict[str, list[Tab]] = {}

  for tab in tabs:

    tab_info = tab.split("\t")

    identifier = tab_info[0]

    window_id = identifier.rsplit('.', maxsplit=1)[0]

    if window_id not in windows:
      windows[window_id] = []

    windows[window_id].append({"id":    tab_info[0],
                               "title": tab_info[1].replace("💤 ", ''),
                               "url":   tab_info[2]})

  return windows

class Window(TypedDict):
  title: str
  tabs:  List[Tab]

def close(windows: List[Window]) -> str | HTTPError:

  set_event_loop(new_event_loop())

  try:
    api.close_tabs([tab["id"]
                    for window in windows
                    for tab in window["tabs"]])
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

  if not isdir(subfolder):
    mkdir(subfolder)

  folder_contents = listdir(subfolder)

  file_indices = [int(filename)
                  for filename in listdir(subfolder)
                  if match(r"^[0-9]+$", filename)]

  if len(file_indices):
    index = max(file_indices) + 1

  else:
    index = 0

  set_event_loop(new_event_loop())

  for window in windows:

    contents = "\n".join([f"{tab['title']}\t{tab['url']}"
                          for tab in window["tabs"]])

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

    with open(file_path, 'a') as output: # FIXME IsADirectoryError: [Errno 21] Is a directory: '/home/casey/urls-tab_wrangler/linkedin'
      output.write(contents)

    try:
      api.close_tabs([tab["id"] for tab in window["tabs"]])
    except HTTPError as http_error:
      return http_error

  get_event_loop().close()

  if len(windows) == 1:
    return (f"window with {len(windows[0]['tabs'])} tab"
            + ("s " if len(windows[0]['tabs']) > 1 else ' ')
            + ("appended to " if appended else "saved as ")
            + relpath(file_path, folder))

  else:
    return (f"{len(windows)} windows "
            + f"and {sum([len(window['tabs']) for window in windows])} tabs "
            + "saved and closed")
