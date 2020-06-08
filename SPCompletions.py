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

import os
import re
import string
import sys
import sublime, sublime_plugin
import codecs
from collections import defaultdict
from queue import *
from threading import Timer, Thread

sys.path.append(os.path.dirname(__file__))
import watchdog.events
import watchdog.observers
import watchdog.utils
from watchdog.utils.bricks import OrderedSetQueue

class Wrapper:
    def __init__(self):
        self.value = []
    def set(self, newval):
        self.value = newval
    def get(self):
        return self.value


def plugin_loaded():
    load_include_dir(True)


def unload_handler():
    file_observer.stop()
    process_thread.stop()
    # Get process_thread to stop by adding something to the queue
    to_process.put(('', ''))
    # remove callback
    _get_settings().clear_on_change('SourcePawn Completions')


class SPCompletions(sublime_plugin.EventListener):
    def __init__(self):
        process_thread.start()
        self.delay_queue = None
        file_observer.start()


    def on_activated(self, view):
        if not self.is_sourcepawn_file(view):
            return
        if not view.file_name():
            return
        if not view.file_name() in nodes:
            add_to_queue(view)


    def on_activated_async(self, view):
        _save_user_settings()


    def on_modified(self, view):
        self.add_to_queue_delayed(view)


    def on_post_save(self, view):
        self.add_to_queue_now(view)


    def on_load(self, view):
        self.add_to_queue_now(view)


    def add_to_queue_now(self, view):
        if not self.is_sourcepawn_file(view):
            return
        add_to_queue(view)


    def add_to_queue_delayed(self, view):
        if not self.is_sourcepawn_file(view):
            return

        if self.delay_queue is not None:
            self.delay_queue.cancel()

        delay_time = _get_settings().get('live_refresh_delay', 1.0)
        self.delay_queue = Timer(float(delay_time), add_to_queue_forward, [ view ])
        self.delay_queue.start()


    def is_sourcepawn_file(self, view):
        return view.file_name() is not None and view.match_selector(0, 'source.sp') or view.match_selector(0, 'source.inc')


    def on_query_completions(self, view, prefix, locations):
        if not view.match_selector(locations[0], 'source.sp -string -comment -constant') \
        and not view.match_selector(locations[0], 'source.inc -string -comment -constant'):
            return []

        # return (self.generate_funcset(view.file_name()), sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)
        return (self.generate_funcset(view.file_name()), sublime.INHIBIT_WORD_COMPLETIONS)


    def generate_funcset(self, file_name):
        funcset = set()
        visited = set()

        node = nodes[file_name]

        self.generate_funcset_recur(node, funcset, visited)
        return sorted_nicely(funcset)


    def generate_funcset_recur(self, node, funcset, visited):
        if node in visited:
            return

        visited.add(node)
        for child in node.children:
            self.generate_funcset_recur(child, funcset, visited)

        funcset.update(node.funcs)


def _settings_filename():
    return 'SourcePawn Completions.sublime-settings'


def _get_settings():
    return sublime.load_settings(_settings_filename())


def on_settings_modified():
    load_include_dir()


def load_include_dir(register_callback = False):
    settings = _get_settings()
    if register_callback:
        settings.add_on_change('SourcePawn Completions', on_settings_modified)

    dirs = settings.get("include_directory", ".")
    include_dirs.set(dirs)
    if type(dirs) is not list:
        if not os.path.isabs(str(dirs)):
            raise RuntimeError("Invalid 'include_directory' setting (%s): directory doesn't exists" % str(dirs))

        file_observer.unschedule_all()
        file_observer.schedule(file_event_handler, dirs, True)
    else:
        for path in dirs:
            if not os.path.isabs(str(path)):
                raise RuntimeError("Invalid 'include_directory' setting (%s): directory doesn't exists" % str(path))

            file_observer.unschedule_all()
            file_observer.schedule(file_event_handler, path, True)

def sorted_nicely( l ):
    """ Sort the given iterable in the way that humans expect."""
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key[0]) ]
    return sorted(l, key = alphanum_key)


def add_to_queue_forward(view):
    sublime.set_timeout(lambda: add_to_queue(view), 0)


def add_to_queue(view):
    # The view can only be accessed from the main thread, so run the regex
    # now and process the results later
    to_process.put((view.file_name(), view.substr(sublime.Region(0, view.size()))))


def add_include_to_queue(file_name):
    to_process.put((file_name, None))


def _save_user_settings():
    settings = _get_settings()
    if not settings.get('bootstrapped'):
        settings.set('bootstrapped', True)
        sublime.save_settings(_settings_filename())
        # build-system
        build_filename = 'SourcePawn.sublime-build'
        build = sublime.load_settings(build_filename)

        if not build.get('file_patterns'):
            build.set('file_patterns', ["*.sp"])
        if not build.get('quiet'):
            build.set('quiet', true)
        if not build.get('file_regex'):
            build.set('file_regex', '(.*)\\((\\d+)\\) : ()(.*$)')
        if not build.get('selector'):
            build.set('selector', 'source.sp')

        sublime.save_settings(build_filename)


class IncludeFileEventHandler(watchdog.events.FileSystemEventHandler):
    def __init__(self):
        watchdog.events.FileSystemEventHandler.__init__(self)


    def on_created(self, event):
        sublime.set_timeout(lambda: on_modified_main_thread(event.src_path), 0)


    def on_modified(self, event):
        sublime.set_timeout(lambda: on_modified_main_thread(event.src_path), 0)


    def on_deleted(self, event):
        sublime.set_timeout(lambda: on_deleted_main_thread(event.src_path), 0)


def on_modified_main_thread(file_path):
    if not is_active(file_path):
        add_include_to_queue(file_path)


def on_deleted_main_thread(file_path):
    if is_active(file_path):
        return

    node = nodes.get(file_path)
    if node is None:
        return

    node.remove_all_children_and_funcs()


def is_active(file_name):
    return sublime.active_window().active_view().file_name() == file_name


class ProcessQueueThread(watchdog.utils.DaemonThread):
    def run(self):
        while self.should_keep_running():
            (file_name, view_buffer) = to_process.get()
            if view_buffer is None:
                self.process_existing_include(file_name)
            else:
                self.process(file_name, view_buffer)


    def process(self, view_file_name, view_buffer):
        (current_node, node_added) = get_or_add_node(view_file_name)

        base_includes = set()

        includes = includes_re.findall(view_buffer)

        for include in includes:
            self.load_from_file(view_file_name, include, current_node, current_node, base_includes)

        for removed_node in current_node.children.difference(base_includes):
            current_node.remove_child(removed_node)

        process_buffer(view_buffer, current_node)


    def process_existing_include(self, file_name):
        current_node = nodes.get(file_name)
        if current_node is None:
            return

        base_includes = set()

        with codecs.open(file_name, 'r', "utf-8") as f:
            print ('Processing Include File %s' % file_name)
            includes = includes_re.findall(f.read())

        for include in includes:
            self.load_from_file(file_name, include, current_node, current_node, base_includes)

        for removed_node in current_node.children.difference(base_includes):
            current_node.remove_child(removed_node)

        process_include_file(current_node)


    def load_from_file(self, view_file_name, base_file_name, parent_node, base_node, base_includes):
        (file_name, exists) = get_file_name(view_file_name, base_file_name)
        if not exists:
            print ('Include File Not Found: %s' % base_file_name)
            print ('Result: %s' % file_name)

        (node, node_added) = get_or_add_node(file_name)
        parent_node.add_child(node)

        if parent_node == base_node:
            base_includes.add(node)

        if not node_added or not exists:
            return

        with codecs.open(file_name, 'r', "utf-8") as f:
            print ('Processing Include File %s' % file_name)
            includes = re.findall(r'^[ \t]*#include[ \t]+[<"]([^>"]+)[>"]', f.read(), re.MULTILINE)

        for include in includes:
            self.load_from_file(view_file_name, include, node, base_node, base_includes)

        process_include_file(node)


def get_file_name(view_file_name, base_file_name):
    file_name = ''
    if local_re.search(base_file_name) == None:
        dirs = include_dirs.get()
        if type(dirs) is not list:
            file_name = os.path.join(dirs, base_file_name + '.inc')
        else:          
            for path in dirs:
                file_name = os.path.join(path, base_file_name + '.inc')
                if os.path.exists(file_name):
                    break
    else:
        file_name = os.path.join(os.path.dirname(view_file_name), base_file_name)

    return (file_name, os.path.exists(file_name))


def get_or_add_node( file_name):
    node = nodes.get(file_name)
    if node is None:
        node = Node(file_name)
        nodes[file_name] = node
        return (node, True)

    return (node, False)


class Node:
    def __init__(self, file_name):
        self.file_name = file_name
        self.children = set()
        self.parents = set()
        self.funcs = set()


    def add_child(self, node):
        self.children.add(node)
        node.parents.add(self)


    def remove_child(self, node):
        self.children.remove(node)
        node.parents.remove(self)

        if len(node.parents) <= 0:
            nodes.pop(node.file_name)


    def remove_all_children_and_funcs(self):
        for child in self.children:
            self.remove_child(node)
        self.funcs.clear()


class TextReader:
    def __init__(self, text):
        self.text = text.splitlines()
        self.position = -1


    def readline(self):
        self.position += 1

        if self.position < len(self.text):
            retval = self.text[self.position]
            if retval == '':
                return '\n'
            return retval
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
def read_line(file):
    """read_line(File) -> string"""
    line = file.readline()
    if len(line) > 0:
        return line
    return None


def process_buffer(text, node):
    text_reader = TextReader(text)
    process_lines(text_reader, node)


def process_include_file(node):
    with codecs.open(node.file_name, "r", "utf-8") as file:
        process_lines(file, node)


def process_lines(line_reader, node):
    node.funcs.clear()

    found_comment = False
    found_enum = False
    brace_level = 0

    while True:
        buffer = read_line(line_reader)

        if buffer is None:
            break

        # strip multiline comments if only written on single line
        buffer = comment_re.sub('', buffer)
        buffer = buffer.strip()
        if not buffer or buffer.startswith('//'):
            continue
            
        # assumes no nested comments. compiler marks those as invalid
        while buffer.startswith('/*'):
            # print('Skipping multi-line comment')
            pos = buffer.find('*/');
            while pos == -1:
                buffer = read_line(line_reader)
                pos = buffer.find('*/')
            buffer = buffer[pos+2:].strip()

        if not buffer or buffer.startswith('//'):
            continue

        if brace_level == 0:
            m = enum_re.search(buffer)
            if m:
                if not m.group(1): # if struct was found, dont do anything. Unsupported currently
                    print("Found enum: " + m.group(0))
                    found_enum = True
                    enum_contents = ''

            elif buffer.strip().startswith('#pragma deprecated'):
                buffer = read_line(line_reader)
                if buffer is not None and buffer.startswith('stock '):
                    pos = buffer.find('{')
                    if pos != -1: # if line contains {, jump to it
                        buffer = buffer[pos:]
                    buffer = skip_brace_line(line_reader, buffer)
                    continue

            elif buffer.startswith('public ') or buffer.startswith('struct '):
                pos = buffer.find('{')
                print("Skipping public or struct")
                if pos != -1: # if line contains {, jump to it
                    buffer = buffer[pos:]
                else: # otherwise, skip to next line
                    continue

            elif buffer.startswith('methodmap '):
                print('Found methodmap')

                pos = buffer.find('{')
                print("Skipping public, methodmap, or struct")
                if pos != -1: # if line contains {, jump to it
                    buffer = buffer[pos:]
                else: # otherwise, skip to next line
                    continue

            elif function_re.search(buffer):
                (buffer, found_comment, brace_level) = get_full_function_string(line_reader, node, buffer, found_comment, brace_level)

        (buffer, found_comment, brace_level) = read_string(buffer, found_comment, brace_level)

        if not buffer:
            continue

        if found_enum:
            (buffer, enum_contents, found_enum) = process_enum(node, buffer, enum_contents, found_enum)
        elif buffer.startswith('#define '):
            buffer = get_preprocessor_define(node, buffer)


# def process_methodmap(node, buffer):

def process_variable(node, buffer):
    file = os.path.basename(node.file_name).rsplit('.')[0]
    if file:
        file = ' [' + file + ']'

    result = ''
    consumingKeyword = True
    consumingName = False
    consumingBrackets = False

    for c in buffer:
        if consumingKeyword:
            if c == ' ':
                consumingKeyword = False
                consumingName = True
        elif consumingName:
            if c == ':':
                result = ''
            elif c == ' ' or c == '=' or c == ';':
                result = result.strip()
                if result != '':
                    node.funcs.add((result + '\t(variable)' + file, result))
                result = ''
                consumingName = False
                consumingBrackets = False
            elif c == '[':
                consumingBrackets = True
            elif not consumingBrackets:
                result += c
        elif c == ',':
            consumingName = True

    result = result.strip()
    if result != '':
        node.funcs.add((result + '\t(variable)' + file, result))

    return ''


def process_enum(node, buffer, enum_contents, found_enum):
    file = os.path.basename(node.file_name).rsplit('.')[0]
    if file:
        file = ' [' + file + ']'

    print('Processing enum: ' + buffer)

    pos = buffer.find('}')
    if pos != -1:
        buffer = buffer[0:pos]
        found_enum = False

    enum_contents = '%s%s' % (enum_contents, buffer)
    buffer = ''

    enum_type = ''
    m = enum_re.search(enum_contents)
    if m:
        if m.group(2):
            enum_type = ': ' + m.group(2)

    ignore = False
    if not found_enum:
        pos = enum_contents.find('{')
        enum_contents = enum_contents[pos + 1:]

        for c in enum_contents:
            if c == '=':
                ignore = True
            elif c == ':':
                buffer = ''
                continue
            elif c == ',':
                buffer = buffer.strip()
                if buffer != '':
                    node.funcs.add((buffer + '\t(enum' + enum_type + ')' + file, buffer))

                ignore = False
                buffer = ''
                continue

            if not ignore:
                buffer += c

        buffer = buffer.strip()
        if buffer != '':
            node.funcs.add((buffer + '\t(enum' + enum_type + ')' + file, buffer))

        buffer = ''

    return (buffer, enum_contents, found_enum)


def get_preprocessor_define(node, buffer):
    file = os.path.basename(node.file_name).rsplit('.')[0]
    if file:
        file = ' [' + file + ']'

    print("Processing define: " + buffer)
    """get_preprocessor_define(File, string) -> string"""
    # Regex the #define. Group 1 is the name, Group 2 is the value
    define = define_re.search(buffer)
    if define:
        # The whole line is consumed, return an empty string to indicate that
        buffer = ''
        name = define.group(1)
        value = define.group(2).strip()
        node.funcs.add((name + '\t(constant: ' + value + ')' + file, name))
    return buffer


def get_full_function_string(line_reader, node, buffer, found_comment, brace_level):
    """get_full_function_string(File, string, string, bool) -> string"""
    multi_line = False
    temp = ''
    full_func_str = None
    open_paren_found = False
    
    while buffer is not None:
        buffer = buffer.strip()
        if not open_paren_found:
            parenpos = buffer.find('(')
            eqpos = buffer.find('=')

            if eqpos != -1 and (parenpos == -1 or eqpos < parenpos):
                return ('', found_comment, brace_level)

            if buffer.find(';') != -1 and parenpos == -1:
                return ('', found_comment, brace_level)

            if parenpos != -1:
                open_paren_found = True

        pos = buffer.rfind(')')
        if pos != -1:
            full_func_str = buffer[0:pos + 1]

            if (multi_line):
                full_func_str = '%s%s' % (temp, full_func_str)

            break

        multi_line = True
        temp = '%s%s' % (temp, buffer)

        buffer = read_line(line_reader)
        if buffer is None:
            return (buffer, found_comment, brace_level)

        (buffer, found_comment, brace_level) = read_string(buffer, found_comment, brace_level)

    if full_func_str is not None and not full_func_str in DEPRECATED_FUNCTIONS:
        process_function_string(node, full_func_str)

    return (buffer, found_comment, brace_level)


def process_function_string(node, func):
    """process_function_string(string, string, bool)"""
    if re.search(r'deprecated', func):
        return

    print("Processing Function: " + func)

    file = os.path.basename(node.file_name).rsplit('.')[0]
    if file:
        file = ' [' + file + ']'

    func_type = ''
    return_type = ': '
    remaining = ''

    m = fullfunction_re.search(func)
    if m:
        if m.group(1):
            func_type += m.group(1) + ' '
        return_type += func_type + (m.group(2) if m.group(2) else '_')
        remaining = m.group(3)
    else:
        return


    split = remaining.split('(', 1)
    funcname = split[0].strip()
    remaining = split[1].strip()

    if remaining == ')':
        params = []
    else:
        params = remaining.strip()[:-1].split(',')

    autocomplete = funcname + '('
    i = 1
    for param in params:
        if i > 1:
            autocomplete += ', '
        autocomplete += '${%d:%s}' % (i, param.strip())
        i += 1
    autocomplete += ')'

    node.funcs.add((funcname + '\t(function' + return_type + ')' + file, autocomplete))


def skip_brace_line(line_reader, buffer):
    """skip_brace_line(File, string) -> string"""
    num_brace = 0

    while buffer is not None:
        print("Skipping brace: " + buffer.strip())
        count = 0
        pos = 0
        for c in buffer:
            if (c == '{'):
                num_brace += 1
            elif (c == '}'):
                num_brace -= 1
            if num_brace == 0:
                pos = count
            count += 1

        if num_brace == 0:
            buffer = buffer[pos+1:]
            print("Skip End: " + buffer)
            return buffer

        buffer = read_line(line_reader)
    return buffer


def read_string(buffer, found_comment, brace_level):
    """read_string(string, bool) -> (string, bool)"""
    buffer = buffer.replace('\t', ' ').strip()
    result = ''

    i = 0
    while i < len(buffer):
        if buffer[i] == '/' and i + 1 < len(buffer):
            if buffer[i + 1] == '/':
                return (result, found_comment, brace_level + result.count('{') - result.count('}'))
            elif buffer[i + 1] == '*':
                found_comment = True
                i += 1
            elif not found_comment:
                result += '/'
        elif found_comment:
            if buffer[i] == '*' and i + 1 < len(buffer) and buffer[i + 1] == '/':
                found_comment = False
                i += 1
        elif not (i > 0 and buffer[i] == ' ' and buffer[i - 1] == ' '):
            result += buffer[i]

        i += 1

    return (result, found_comment, brace_level + result.count('{') - result.count('}'))

to_process = OrderedSetQueue()
nodes = dict() # map files to nodes
file_observer = watchdog.observers.Observer()
process_thread = ProcessQueueThread()
file_event_handler = IncludeFileEventHandler()
include_dirs = Wrapper()
includes_re = re.compile(r'^[ \t*]*#include[\s]+[<"]([^>"]+)[>"]', re.MULTILINE)
local_re = re.compile(r'\.(sp|inc)$')
enum_re = re.compile(r'^[ \t]*enum\b[ \t]+(struct\b[ \t]+)?([\w_]+)?')
function_re = re.compile(r'^[ \t]*(?:(native|stock|forward)\b[ \t]+)?(?:([\w_]+)(?:[ \t]+|:))?([\w_]+[ \t]*\()')
fullfunction_re = re.compile(r'^[ \t]*(?:(native|stock|forward)\b[ \t]+)?(?:([\w_]+)(?: +|:))?([\w_]+ *\(.*?\))')
define_re = re.compile(r'#define[ \t]+([^\s]+)[\s]+(.+)')
comment_re = re.compile(r'\/\*(.*?)\*\/')
