import sublime, sublime_plugin

class PythonCompletions(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        if not view.match_selector(locations[0], 'source.python -string -comment -constant'):
            return []
        return []

    def on_modified(view):
        return None