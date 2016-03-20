# SourcePawn Completions for SublimeText 3

A Sublime Text 3 plugin that dynamically genenerates completions for SourcePawn.

Based on [sublime-sourcepawn](https://github.com/austinwagner/sublime-sourcepawn).
Includes [watchdog python module](https://https://github.com/gorakhargosh/watchdog)

## Installing

### Via package control

1. **Package control: Add repository**, enter `http://s.ppalex.com/packagecontrol/packages.json`
2. **Package control: Install package**, enter *SourcePawn Completions*

### Manually

Clone this repository into a subfolder of your Packages directory:
* Mac OS `~/Library/Application Support/Sublime Text 3/Packages/`
* Windows `%APPDATA%/Sublime Text 3/Packages/`

## Configuration
**Note:** All paths must be an absolute. Relative paths are unsupported.

1. Open *Sublime Text* -> *Preferences* -> *Package Settings* -> *SourcePawn Completions* -> *Auto-completion settings*.
2. Change `include_directory` setting to your path with SourceMod include files.
3. Save and close file.
4. Open *Sublime Text* -> *Preferences* -> *Package Settings* -> *SourcePawn Completions* -> *Build settings*.
5. Uncomment one of `cmd` settings and ajust path to `spcomp`. This allows you to use **Build** feature in SublimeText.
6. Save and close file.

## Usage

SP Completions is automatically active on .sp and .inc files. The completion list updates whenever you stop typing for 1 second or when you save the file.
