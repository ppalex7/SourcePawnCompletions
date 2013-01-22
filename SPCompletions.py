# SourcePawn Completions is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sublime, sublime_plugin
import re
import os
import string
from collections import defaultdict
from threading import Timer, Thread
from Queue import *
import watchdog
import watchdog.events
import watchdog.observers
import watchdog.utils
from watchdog.utils.bricks import OrderedSetQueue

class StringWrapper :
    def __init__(self) :
        self.value = ''
    def set(self, newval) :
        self.value = newval
    def get(self) :
        return self.value

def unload_handler() :
    file_observer.stop()
    process_thread.stop()
    # Get process_thread to stop by adding something to the queue
    to_process.put(('', ''))

class SPCompletions(sublime_plugin.EventListener):
    def __init__(self) :
        process_thread.start()
        self.delay_queue = None
        file_observer.start()
        self.file_event_handler = IncludeFileEventHandler()
        self.load_include_dir(True)

    def on_modified(self, view) :
        self.add_to_queue_delayed(view)

    def on_post_save(self, view) :
        self.add_to_queue_now(view)

    def on_load(self, view) :
        self.add_to_queue_now(view)

    def add_to_queue_now(self, view) :
        if not self.is_sourcepawn_file(view):
            return
        add_to_queue(view)

    def add_to_queue_delayed(self, view) :
        if not self.is_sourcepawn_file(view):
            return

        if self.delay_queue is not None :
            self.delay_queue.cancel()

        delay_time = sublime.load_settings('SPCompletions.sublime-settings').get('live_refresh_delay', 1.0)
        self.delay_queue = Timer(float(delay_time), add_to_queue_forward, [ view ])
        self.delay_queue.start()

    def is_sourcepawn_file(self, view) :
        return view.file_name() is not None and view.match_selector(0, 'source.sp') or view.match_selector(0, 'source.inc')
        
    def on_query_completions(self, view, prefix, locations):
        if not view.match_selector(locations[0], 'source.sp -string -comment -constant') \
        and not view.match_selector(locations[0], 'source.inc -string -comment -constant'):
            return []

        return (self.generate_funcset(view.file_name()), sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def generate_funcset(self, file_name) :
        funcset = set()
        visited = set()
        node = nodes[file_name]

        self.generate_funcset_recur(node, funcset, visited)
        return sorted_nicely(funcset)

    def generate_funcset_recur(self, node, funcset, visited) :
        if node in visited :
            return
        
        visited.add(node)
        for child in node.children :
            self.generate_funcset_recur(child, funcset, visited)

        funcset.update(node.funcs)

    def load_include_dir(self, register_callback = False) :
        settings = sublime.load_settings('SPCompletions.sublime-settings')
        if register_callback :
            settings.add_on_change('SPCompletions', self.on_settings_modified)

        include_dir.set(settings.get('include_directory', '.'))
        if not os.path.isabs(include_dir.get()) :
            raise exception.RuntimeException()

        file_observer.unschedule_all()
        file_observer.schedule(self.file_event_handler, include_dir.get(), True)

    def on_settings_modified(self) :
        self.load_include_dir()

def sorted_nicely( l ): 
    """ Sort the given iterable in the way that humans expect.""" 
    convert = lambda text: int(text) if text.isdigit() else text 
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key[0]) ] 
    return sorted(l, key = alphanum_key)

def add_to_queue_forward(view) :
    sublime.set_timeout(lambda: add_to_queue(view), 0)

def add_to_queue(view) :
    # The view can only be accessed from the main thread, so run the regex
    # now and process the results later
    to_process.put((view.file_name(), view.substr(sublime.Region(0, view.size()))))

def add_include_to_queue(file_name) :
    to_process.put((file_name, None))

class IncludeFileEventHandler(watchdog.events.FileSystemEventHandler) :
    def __init__(self) :
        watchdog.events.FileSystemEventHandler.__init__(self)

    def on_created(self, event) :
        sublime.set_timeout(lambda: on_modified_main_thread(event.src_path), 0)

    def on_modified(self, event) :
        sublime.set_timeout(lambda: on_modified_main_thread(event.src_path), 0)

    def on_deleted(self, event) :
        sublime.set_timeout(lambda: on_deleted_main_thread(event.src_path), 0)

def on_modified_main_thread(file_path) :
    if not is_active(file_path) :
        add_include_to_queue(file_path)

def on_deleted_main_thread(file_path) :
    if is_active(file_path) :
            return

    node = nodes.get(file_path)
    if node is None :
        return

    node.remove_all_children_and_funcs()

def is_active(file_name) :
    return sublime.active_window().active_view().file_name() == file_name

class ProcessQueueThread(watchdog.utils.DaemonThread) :
    def run(self) :
        while self.should_keep_running() :
            (file_name, view_buffer) = to_process.get()
            if view_buffer is None :
                self.process_existing_include(file_name)
            else :
                self.process(file_name, view_buffer)

    def process(self, view_file_name, view_buffer) :
        (current_node, node_added) = get_or_add_node(view_file_name)

        base_includes = set()

        includes = re.findall('^[\\s]*#include[\\s]+<([^>]+)>', view_buffer, re.MULTILINE)

        for include in includes:
            self.load_from_file(view_file_name, include, current_node, current_node, base_includes)

        for removed_node in current_node.children.difference(base_includes) :
            current_node.remove_child(removed_node)

        process_buffer(view_buffer, current_node)
    
    def process_existing_include(self, file_name) :
        current_node = nodes.get(file_name)
        if current_node is None :
            return

        base_includes = set()

        with open(file_name, 'r') as f :
            print 'Processing Include File %s' % file_name
            includes = re.findall('^[\\s]*#include[\\s]+<([^>]+)>', f.read(), re.MULTILINE)

        for include in includes:
            self.load_from_file(view_file_name, include, current_node, current_node, base_includes)

        for removed_node in current_node.children.difference(base_includes) :
            current_node.remove_child(removed_node)
            
        process_include_file(current_node)


    def load_from_file(self, view_file_name, base_file_name, parent_node, base_node, base_includes) :
        (file_name, exists) = get_file_name(view_file_name, base_file_name)
        if not exists :
            print 'Include File Not Found: %s' % base_file_name

        (node, node_added) = get_or_add_node(file_name)
        parent_node.add_child(node)

        if parent_node == base_node :
            base_includes.add(node)

        if not node_added or not exists:
            return

        with open(file_name, 'r') as f :
            print 'Processing Include File %s' % file_name
            includes = re.findall('^[\\s]*#include[\\s]+<([^>]+)>', f.read(), re.MULTILINE)

        for include in includes :
            self.load_from_file(view_file_name, include, node, base_node, base_includes)

        process_include_file(node)


def get_file_name(view_file_name, base_file_name) :
    file_name = os.path.join(include_dir.get(), base_file_name + '.inc')
    return (file_name, os.path.exists(file_name))

def get_or_add_node( file_name) :
    node = nodes.get(file_name)
    if node is None :
        node = Node(file_name)
        nodes[file_name] = node
        return (node, True)

    return (node, False)

class Node :
    def __init__(self, file_name) :
        self.file_name = file_name
        self.children = set()
        self.parents = set()
        self.funcs = set()

    def add_child(self, node) :
        self.children.add(node)
        node.parents.add(self)

    def remove_child(self, node) :
        self.children.remove(node)
        node.parents.remove(self)

        if len(node.parents) <= 0 :
            nodes.pop(node.file_name)

    def remove_all_children_and_funcs(self) :
        for child in self.children :
            self.remove_child(node)
        self.funcs.clear()

class TextReader:
    def __init__(self, text):
        self.text = text.splitlines()
        self.position = -1

    def readline(self) :
        self.position += 1
        
        if self.position < len(self.text) :
            retval = self.text[self.position]
            if retval == '' :
                return '\n'
            else :
                return retval
        else :
            return ''       

DEPRECATED_FUNCTIONS = [
    "native Float:operator*",
    "native Float:operator/",
    "native Float:operator+",
    "native Float:operator-",
    "stock Float:operator*", 
    "stock Float:operator/",
    "stock Float:operator+",
    "stock Float:operator-",
    "stock bool:operator=",
    "stock bool:operator!",
    "stock bool:operator>",
    "stock bool:operator<",
    "forward operator%("
]

loaded_files = set() # to prevent loading files more than once
docs = dict() # map function name to documentation
included_files = defaultdict(set) # map project files to included files
funcs = defaultdict(list) # map include files to functions

# Code after this point adapted from 
# https://forums.alliedmods.net/showpost.php?p=1866026&postcount=19
# Credit to MCPAN (mcpan@foxmail.com)
def read_line(file) :
    """read_line(File) -> string"""
    line = file.readline()
    if len(line) > 0 :
        return line
    else :
        return None

def process_buffer(text, node) :
    text_reader = TextReader(text)
    process_lines(text_reader, node)

def process_include_file(node) :
    with open(node.file_name) as file :
        process_lines(file, node)

def process_lines(line_reader, node) :
    node.funcs.clear()

    found_comment = False
    found_enum = False
    brace_level = 0
    
    while True :
        buffer = read_line(line_reader)

        if buffer is None :
            break 
        (buffer, found_comment, brace_level) = read_string(buffer, found_comment, brace_level)
        if len(buffer) <= 0 :
            continue

        if buffer.startswith('#pragma deprecated') :
            buffer = read_line(line_reader)
            if buffer is not None and buffer.startswith('stock ') :
                buffer = skip_brace_line(line_reader, buffer)
        elif buffer.startswith('#define ') :
            buffer = get_preprocessor_define(node, buffer)
        elif buffer.startswith('enum ') :
            found_enum = True
            enum_contents = ''
        elif buffer.startswith('native ') :
            (buffer, found_comment, brace_level) = get_full_function_string(line_reader, node, buffer, True, found_comment, brace_level)
        elif buffer.startswith('stock ') :
            (buffer, found_comment, brace_level) = get_full_function_string(line_reader, node, buffer, True, found_comment, brace_level)
            buffer = skip_brace_line(line_reader, buffer)
        elif buffer.startswith('forward ') or buffer.startswith('functag ') :
            (buffer, found_comment, brace_level) = get_full_function_string(line_reader, node, buffer, False, found_comment, brace_level)
        elif buffer.startswith('new ') or buffer.startswith('decl ') :
            buffer = process_variable(node, buffer)
        elif brace_level == 0 and not found_enum and not buffer.strip()[0] == '#' and not buffer.startswith('static ') and not buffer.startswith('static const '):
            (buffer, found_comment, brace_level) = get_full_function_string(line_reader, node, buffer, False, found_comment, brace_level)

        if found_enum :
            (buffer, enum_contents, found_enum) = process_enum(node, buffer, enum_contents, found_enum)

def process_variable(node, buffer) :
    result = ''
    consumingKeyword = True
    consumingName = False
    consumingBrackets = False
    for c in buffer :
        if consumingKeyword :
            if c == ' ' :
                consumingKeyword = False
                consumingName = True
        elif consumingName :
            if c == ':' :
                result = ''
            elif c == ' ' or c == '=' or c == ';' :
                result = result.strip()
                if result != '' :
                    node.funcs.add((result + '  (variable)', result))
                result = ''
                consumingName = False
                consumingBrackets = False
            elif c == '[' :
                consumingBrackets = True
            elif not consumingBrackets:
                result += c
        elif c == ',' :
            consumingName = True

    result = result.strip()
    if result != '' :
        node.funcs.add((result + '  (variable)', result))

    return ''

def process_enum(node, buffer, enum_contents, found_enum) :
    pos = buffer.find('}')
    if pos != -1 :
        buffer = buffer[0:pos]
        found_enum = False

    enum_contents = '%s%s' % (enum_contents, buffer)
    buffer = ''

    ignore = False
    if not found_enum :
        pos = enum_contents.find('{')
        enum_contents = enum_contents[pos + 1:]
        
        for c in enum_contents :
            if c == '=' :
                ignore = True
            elif c == ':' :
                buffer = ''
                continue
            elif c == ',' :
                buffer = buffer.strip()
                if buffer != '' :
                    node.funcs.add((buffer + '  (enum)', buffer))

                ignore = False
                buffer = ''
                continue

            if not ignore :
                buffer += c

        buffer = buffer.strip()
        if buffer != '' :
            node.funcs.add((buffer + '  (enum)', buffer))

        buffer = ''

    return (buffer, enum_contents, found_enum)

def get_preprocessor_define(node, buffer) :
    """get_preprocessor_define(File, string) -> string"""
    # Regex the #define. Group 1 is the name, Group 2 is the value 
    define = re.search('#define[\\s]+([^\\s]+)[\\s]+(.+)', buffer)
    if define :
        # The whole line is consumed, return an empty string to indicate that
        buffer = ''
        name = define.group(1)
        value = define.group(2).strip()
        node.funcs.add((name + '  (constant: ' + value + ')', name))
    return buffer

def get_full_function_string(line_reader, node, buffer, is_native, found_comment, brace_level) :
    """get_full_function_string(File, string, string, bool) -> string"""
    multi_line = False
    temp = ''
    full_func_str = None
    open_paren_found = False
    while buffer is not None :
        buffer = buffer.strip()
        if not open_paren_found :
            parenpos = buffer.find('(')
            eqpos = buffer.find('=')
            if eqpos != -1 and (parenpos == -1 or eqpos < parenpos) :
                return ('', found_comment, brace_level)
            if buffer.find(';') != -1 and parenpos == -1 :
                return ('', found_comment, brace_level)
            if parenpos != -1 :
                open_paren_found = True

        pos = buffer.rfind(')')
        if pos != -1 :
            full_func_str = buffer[0:pos + 1]

            if (multi_line) :
                full_func_str = '%s%s' % (temp, full_func_str)

            break

        multi_line = True
        temp = '%s%s' % (temp, buffer)

        buffer = read_line(line_reader)
        if buffer is None :
            return (buffer, found_comment, brace_level)
        (buffer, found_comment, brace_level) = read_string(buffer, found_comment, brace_level)

    if full_func_str is not None and not full_func_str in DEPRECATED_FUNCTIONS :
        process_function_string(node, full_func_str, is_native)

    return (buffer, found_comment, brace_level)

def process_function_string(node, func, is_native) :
    """process_function_string(string, string, bool)"""

    split = func.split(' ', 1)
    if len(split) < 2 :
        functype = ''
        remaining = split[0]
    else :
        functype = split[0].strip()
        remaining = split[1]
    # TODO: Process functags
    if functype == 'functag' :
        return
    split = remaining.split('(', 1)
    if len(split) < 2 :
        return
    remaining = split[1]
    funcname_and_return = split[0].strip()
    split_funcname_and_return = funcname_and_return.split(':')
    if len(split_funcname_and_return) > 1 :
        funcname = split_funcname_and_return[1]
        returntype = split_funcname_and_return[0]
    else :
        funcname = split_funcname_and_return[0]

    remaining = remaining.strip()
    if remaining == ')' :
        params = []
    else :
        params = remaining.strip()[:-1].split(',')
    
    autocomplete = funcname + '('
    i = 1
    for param in params :
        if i > 1 :
            autocomplete += ', '
        autocomplete += '${%d:%s}' % (i, param.strip())
        i += 1
    autocomplete += ')'
    node.funcs.add((funcname + '  (function)', autocomplete))

def skip_brace_line(line_reader, buffer) :
    """skip_brace_line(File, string) -> string"""
    num_brace = 0
    found = False

    while buffer is not None :
        for c in buffer :
            if (c == '{') :
                num_brace += 1
                found = True
            elif (c == '}') :
                num_brace -= 1

        if num_brace == 0 :
            return buffer

        buffer = read_line(line_reader)
    return buffer

def read_string(buffer, found_comment, brace_level) :
    """read_string(string, bool) -> (string, bool)"""
    buffer = buffer.replace('\t', ' ').strip()
    result = ''

    i = 0
    while i < len(buffer) :
        if buffer[i] == '/' and i + 1 < len(buffer):
            if buffer[i + 1] == '/' :
                return (result, found_comment, brace_level + result.count('{') - result.count('}'))
            elif buffer[i + 1] == '*' :
                found_comment = True
                i += 1
            elif not found_comment :
                result += '/'
        elif found_comment :
            if buffer[i] == '*' and i + 1 < len(buffer) and buffer[i + 1] == '/' :
                found_comment = False
                i += 1
        elif not (i > 0 and buffer[i] == ' ' and buffer[i - 1] == ' '):
            result += buffer[i]

        i += 1

    return (result, found_comment, brace_level + result.count('{') - result.count('}'))


to_process = OrderedSetQueue()
nodes = dict() # map files to nodes
include_dir = StringWrapper()
file_observer = watchdog.observers.Observer()
process_thread = ProcessQueueThread()