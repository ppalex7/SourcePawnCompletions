# Sublime SourcePawn Completions

Generates SourcePawn completions for all included .inc files.

Based off [SourcePawn Snippet Generator by MCPAN](https://forums.alliedmods.net/showpost.php?p=1866026&postcount=19).

## Installing

Clone this repository into a subfolder of your Packages directory.

## Configuration

Create an `SPCompltions.sublime-settings` file in your User directory that looks like:

    {
        "search_directories": [ ".\\include", "C:\\sourcemod\\scripting\\include" ]
    }

Add directories in the order you want them to be searched. Locations are relative to the current file.

## Usage

SP Completions is automatically active on .sp and .inc files. The completion list updates whenever you stop typing for 1 second or when you save the file.