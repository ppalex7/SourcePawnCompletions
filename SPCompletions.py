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
from collections import defaultdict

class SPCompletions(sublime_plugin.EventListener):
    def on_post_save(self, view) :
        current_node = nodes.get(view.file_name())

        if current_node is None :
            current_node = Node(view.file_name())
            nodes[view.file_name()] = current_node

        for found in view.find_all('^[\\s]*#include') :
            line = view.substr(view.line(found)).strip()
            base_file_name = line.split('<')[1][:-1]
            self.load_from_file(view, base_file_name, current_node)

    def load_from_file(self, view, base_file_name, parent_node) :
        file_name = self.get_file_name(view, base_file_name)
        if file_name is None :
            print 'Include File Not Found: %s' % base_file_name
            return

        stop = True
        node = nodes.get(file_name)
        if node is None :
            node = Node(file_name)
            stop = False

        parent_node.add_child(node)

        if stop :
            return

        with open(file_name, 'r') as f :
            print 'Processing Include File %s' % file_name
            includes = re.findall('^[\\s]*#include[\\s]+<([^>]+)>', f.read(), re.MULTILINE)
            for include in includes :
                self.load_from_file(view, include, node)

        process_include_file(node)


    def get_file_name(self, view, base_file_name) :
        os.chdir(os.path.dirname(view.base_file_name()))
        search_dirs = sublime.load_settings('SPCompletions.sublime-settings').get('search_directories', \
            [ os.path.join('.', 'include') ])

        for dir in search_dirs :
            file_name = os.path.join(dir, base_file_name + '.inc')
            print file_name
            if os.path.exists(file_name) :
                return file_name

        return None

    def on_query_completions(self, view, prefix, locations):
        if not view.match_selector(locations[0], 'source.sp -string -comment -constant') \
        and not view.match_selector(locations[0], 'source.inc -string -comment -constant'):
            return []

        return (self.generate_funclist(view.file_name()), sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def generate_funclist(self, file_name) :
        funclist = [ ]
        visited = set()
        node = nodes[file_name]

        self.generate_funclist_recur(node, funclist, visited)
        funclist.sort()
        return funclist

    def generate_funclist_recur(self, node, list, visited) :
        if node in visited :
            return
        
        visited.add(node)
        for child in node.children :
            self.generate_funclist_recur(child, list, visited)

        list.extend(node.funcs)


nodes = dict() # map files to nodes

class Node :
    def __init__(self, file_name) :
        self.file_name = file_name
        self.children = set()
        self.parents = set()
        self.funcs = [ ]

    def add_child(self, node) :
        self.children.add(node)
        node.parents.add(self)

    def remove_child(self, node) :
        self.children.remove(node)
        node.parents.remove(self)

        if len(node.parents) <= 0 :
            nodes.remove(node)

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

def process_include_file(node) :
    """process_include_file(string)"""
    with open(node.file_name) as file :
        found_comment = False

        while True :
            buffer = read_line(file)
            if buffer is None :
                break 
            (buffer, found_comment) = read_string(buffer, found_comment)
            if len(buffer) <= 0 :
                continue

            if buffer.startswith('#pragma deprecated') :
                buffer = read_line(file)
                if (buffer is not None and buffer.startswith('stock')) :
                    buffer = skip_brace_line(file, buffer)
            elif buffer.startswith('#define') :
                buffer = get_preprocessor_define(file, node, buffer)
            elif buffer.startswith('native') :
                buffer = get_full_function_string(file, node, buffer, True)
            elif buffer.startswith('stock') :
                buffer = get_full_function_string(file, node, buffer, True)
                buffer = skip_brace_line(file, buffer)
            elif buffer.startswith('forward') or buffer.startswith('functag') :
                buffer = get_full_function_string(file, node, buffer, False)
            
def get_preprocessor_define(file, node, buffer) :
    """get_preprocessor_define(File, string) -> string"""
    # Regex the #define. Group 1 is the name, Group 2 is the value 
    define = re.search('#define[\\s]+([^\\s]+)[\\s]+([^\\s]+)', buffer)
    if define :
        # The whole line is consumed, return an empty string to indicate that
        buffer = ''
        group = define.group(1, 1)
        node.funcs.append(group)
    return buffer

def get_full_function_string(file, node, buffer, is_native) :
    """get_full_function_string(File, string, string, bool) -> string"""
    multi_line = False
    temp = ''
    while buffer is not None :
        buffer = buffer.strip()
        pos = buffer.rfind(')')
        if pos != -1 :
            full_func_str = buffer[0:pos + 1]

            if (multi_line) :
                full_func_str = '%s%s' % (temp, full_func_str)

            break

        multi_line = True
        temp = '%s%s' % (temp, buffer)

        buffer = read_line(file)

    if not full_func_str in DEPRECATED_FUNCTIONS :
        process_function_string(node, full_func_str, is_native)

    return buffer

def process_function_string(node, func, is_native) :
    """process_function_string(string, string, bool)"""

    (functype, remaining) = func.split(' ', 1)
    functype = functype.strip()
    # TODO: Process functags
    if functype == 'functag' :
        return
    (funcname_and_return, remaining) = remaining.split('(', 1)
    funcname_and_return = funcname_and_return.strip()
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
    node.funcs.append((funcname, autocomplete))

def skip_brace_line(file, buffer) :
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

        buffer = read_line(file)
    return buffer

def read_string(buffer, found_comment) :
    """read_string(string, bool) -> (string, bool)"""
    buffer = buffer.replace('\t', ' ')

    if (not found_comment) :
        for i in range(len(buffer)) :
            if (buffer[i] == '/' and buffer[i + 1] == '/') :
                buffer = buffer[0:i]
                break

    buffer = buffer.strip()

    comment_start = False
    comment_end = False

    pos = buffer.find('/*')
    if pos != -1 :
        comment_start = True
        temp = buffer[pos + 1]
        buffer = buffer[0:pos].strip()

        pos = temp.find('*/')
        if pos != -1 :
            comment_end = True
            temp = temp[pos + 1].strip()
        else :
            temp = ''

        if buffer != '' or temp != '' :
            buffer = '%s%s' % (buffer, temp)
    else :
        pos = buffer.find('*/')
        if pos != -1 :
            comment_end = True
            if pos + 2 == len(buffer):
                buffer = ''
            else :
                buffer = buffer[pos + 2]

    buffer = buffer.strip()

    return (buffer, comment_start ^ comment_end)
