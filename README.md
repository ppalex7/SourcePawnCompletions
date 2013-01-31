# Sublime SourcePawn Completions

A Sublime Text 2 plugin that dynamically genenerates completions for SourcePawn.

Based off [SourcePawn Snippet Generator by MCPAN](https://forums.alliedmods.net/showpost.php?p=1866026&postcount=19).

## Installing

Clone this repository into a subfolder of your Packages directory.

## Configuration

Create an `SPCompletions.sublime-settings` file in your User directory that looks like:

    {
        "include_directory": "C:\\srcds\\tf\\addons\\sourcemod\\scripting\\include"
    }
    
or edit same file in the installed package folder.

The path must be an absolute path. Relative paths are unsupported. 

If you are upgrading from an older version, note that this configuration option has a different name.

## Usage

SP Completions is automatically active on .sp and .inc files. The completion list updates whenever you stop typing for 1 second or when you save the file.
