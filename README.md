# SourcePawn Completions for SublimeText 3

A Sublime Text 3 plugin that dynamically genenerates completions for SourcePawn.

Based on [sublime-sourcepawn](https://github.com/austinwagner/sublime-sourcepawn).
Includes [watchdog python module](https://https://github.com/gorakhargosh/watchdog)

## Installing

### Via [package control](https://packagecontrol.io/installation)

1. Press `Control+Shift+P` or `Cmd+Shift+P` (on Mac)
2. Type **Package Control: Install Package**, hit enter.
3. Type in **SourcePawn Completions**, hit enter again.

### Manually

Clone this repository into a subfolder of your Packages directory:
* Mac OS `~/Library/Application Support/Sublime Text 3/Packages/`
* Windows `%APPDATA%/Sublime Text 3/Packages/`

## Configuration
**Note:** All paths must be an absolute. Relative paths are unsupported.

1. Open *Sublime Text* -> *Preferences* -> *Package Settings* -> *SourcePawn Completions* -> *Settings - User*.
2. Add `include_directory` setting with path to your SourceMod include files (`sourcemod/scripting` folder). (You could look for some exmaples in *Settings - Default*)
3. Save and close file.
4. Open *Sublime Text* -> *Preferences* -> *Package Settings* -> *SourcePawn Completions* -> *Build settings - Example* and *Build settings - User*
5. Copy one of `cmd` settings from `SourcePawn.sublime-build.example`, paste it to `SourcePawn.sublime-build` and ajust path to `spcomp`. This allows you to use **Build** feature in SublimeText.
6. Save and close file.

## Usage

SourcePawn Completions is automatically active on .sp and .inc files. The completion list updates whenever you stop typing for 1 second or when you save the file.

## Aslo recommend
To take full advantage recommend to install the following packages:
* [SourcePawn Syntax Highlighting](https://github.com/Dillonb/SublimeSourcePawn) _(available in Package control)_
