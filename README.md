# Sublime SourcePawn Completions

Generates SourcePawn completions for all included .inc files.

## Installing

Clone this repository into a subfolder of your Packages directory.

## Configuration

Create a copy of `SPCompltions.sublime-settings` in your User directory.

Add directories in the order you want them to be searched. Locations are relative to the current file.

## Usage

SP Completions is automatically active on .sp and .inc files. To generate the completion list, save the source file.

## Known Bugs

* Completion lists do not update. If an include file is modified, after it has been loaded by SP Completions, Sublime must be restarted to pick up this change.
