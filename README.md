# Tab Wrangler

a text user interface (TUI) for tabaholics* with vim-like keybindings

\* one known to have hundreds or thousands of browser tabs open

![screenshot](https://github.com/doctorcolossus/tab_wrangler/assets/731937/de09934c-d614-4c20-a997-b112372ff238)

## Features

This program currently helps mainly:

- to give a readable overview of all open windows and tabs,

- to find and get back to things you know you have open in some window, and

- to save and close windows of tabs, or groups of them.

Saved windows are currently saved to `~/urls-tab_wrangler`
as lists of tab-separated values with two columns: title and URL.
Untitled ones are numbered and thrown into the `untitled` subfolder.

## Future

The next main features I would like to implement are:

- searching through and reloading *previously* closed windows

- naming windows, hopefully with some mechanism for persistence across runs

- breaking a group of tabs out into a new or existing window

- implementing "undo"

## Support

I wrote this for my own use and use it on a daily basis.
This means I didn't design it with other people's environments in mind.
I use [Sway window manager](https://swaywm.org/) in Arch Linux.
The feature to shift focus to an open window depends on Sway's `swaymsg`.
I have also been able to test this in Ubuntu 22.04 (Jammy Jellyfish),
and was able to get that same functionality using `wmctrl` -
see the commented-out line at the end of `browser.py` for how.
In the future, maybe I'll try to support and detect different environments,
but for now that's a low priority on the distant horizon.

## Why I'm sharing

I'm sharing this mainly in the hope of helping to keep my main dependency,
the amazing [brotab](https://github.com/balta2ar/brotab), alive,
by contributing to its ecosystem. I figure the more useful software there is
out there which depends on it, the greater the incentive will be for everyone
to help keep that project alive and up-to-date. Maybe eventually people will
help contribute to my project to, but at least for now, at first, I can say
that I unfortunately won't have much time to offer support.

## Dependencies

- [brotab](https://github.com/balta2ar/brotab)

- [urwid](https://urwid.org/index.html)

- for shifting focus to a window:
    - [jq](https://jqlang.github.io/jq/)
    - [Sway window manager](https://swaywm.org/),
      or alternatively `wmctrl` if using Ubuntu
      (in which case uncomment the commented-out line at end of `browser.py`)

## Usage

Currently I just keep this in `~/tab_wrangler`
and run it from `~` as  `python -m tab_wrangler`.

If there's interest, I could work on making this into a proper Python package
and/or providing packages for Arch Linux or Debian/Ubuntu.
But for now I am lazy. Pull requests welcome!

### Keybindings

`c`: Close *all* browser windows, saving their contents to untitled files.
Careful, as "undo" is not yet implemented!

`d`: Close ("(d)elete") a window, or group of windows.

`s`: (S)ave and close a window, or group of windows.

`w`: Name, save, and close ("(w)rite") a window, or group of windows.

`enter`: Focus the selected window.

`/`: Search forwards.

`?`: Search backwards.

`n`: Repeat last search.

`N`: Repeat last search in reverse.

`space`: Select a window. Multiple windows can be selected to save and/or close them as a group.

`j`: Move down a window.

`k`: Move up a window.

`g`: Jump to the first window in the list.

`G`: Jump to the last window in the list.

`q`: Quit.
