# Sublime SourcePawn Completions

Generates SourcePawn completions for all included .inc files.

## Installing

Clone this repository into a subfolder of your Packages directory.

## Configuration

There are currently no configuration files, but you will need to configure the include file search path.

By default the search paths are `.\include` and `C:\srcds\tf\addons\sourcemod\scripting\include`

To modify the path, search for `'C:\\srcds\\tf\\addons\\sourcemod\\scripting\\include'` in SPCompletion.py and set this to the path containing your include files.

## Usage

SP Completions is automatically active on .sp and .inc files. To generate the completion list, save the source file.

## Known Bugs

* Completions lists are shared. All completions from other files will be available even if the include line does not exist in the current file.
* Completion lists do not update. If an include file is modified, after it has been loaded by SP Completions, Sublime must be restarted to pick up this change.
