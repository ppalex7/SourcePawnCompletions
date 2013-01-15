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
        included_by_file = included_files[view.file_name()]
        del included_by_file[:]
        for found in view.find_all('^[\\s]*#include') :
            line = view.substr(view.line(found)).strip()
            filename = line.split('<')[1][:-1]
            included_by_file.append(filename)
            if not filename in loaded_files :
                loaded_files.add(filename)
                self.load_from_file(view, filename)

        included_files[view.file_name] = included_by_file


    # TODO: Improve loading and caching. Should not require save, should be threaded, 
    #       should detect modified .inc files
    # TODO: After live updating is implemented, generate completions from current file.
    def load_from_file(self, view, filename) :
        path = self.get_file_path(view, filename)
        if path is None :
            return

        with open(path, 'r') as f :
            print 'Processing Include File %s' % path
            includes = re.findall('^[\\s]*#include[\\s]+<([^>]+)>', f.read(), re.MULTILINE)
            for include in includes :
                if not include in loaded_files :
                    loaded_files.add(include)
                    self.load_from_file(view, include)
        process_include_file(path)

    def get_file_path(self, view, filename) :
        # TODO: Don't hardcode this path
        search_dirs = [
            os.path.join(os.path.dirname(view.file_name()), 'include'),
            'C:\\srcds\\tf\\addons\\sourcemod\\scripting\\include'
        ]

        for dir in search_dirs :
            file_path = os.path.join(dir, filename + '.inc')
            if os.path.exists(file_path) :
                return file_path

        return None

    def on_query_completions(self, view, prefix, locations):
        if not view.match_selector(locations[0], 'source.sp -string -comment -constant') \
        and not view.match_selector(locations[0], 'source.inc -string -comment -constant'):
            return []

        included_by_file = included_files[view.file_name()]
        accessible_funcs = list()

        for include in included_by_file :
            accessible_funcs.extend(funcs[include])

        return (accessible_funcs, sublime.INHIBIT_WORD_COMPLETIONS |
            sublime.INHIBIT_EXPLICIT_COMPLETIONS)

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

all_funcs = []
loaded_files = set() # to prevent loading files more than once
docs = dict() # map function name to documentation
included_files = defaultdict(list) # map project files to included files
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

def process_include_file(file_path) :
    """process_include_file(string)"""
    with open(file_path) as file :
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
                buffer = get_preprocessor_define(file, buffer)
            elif buffer.startswith('native') :
                buffer = get_full_function_string(file, file_path, buffer, True)
            elif buffer.startswith('stock') :
                buffer = get_full_function_string(file, file_path, buffer, True)
                buffer = skip_brace_line(file, buffer)
            elif buffer.startswith('forward') or buffer.startswith('functag') :
                buffer = get_full_function_string(file, file_path, buffer, False)
            
def get_preprocessor_define(file, buffer) :
    """get_preprocessor_define(File, string) -> string"""
    # Regex the #define. Group 1 is the name, Group 2 is the value 
    define = re.search('#define[\\s]+([^\\s]+)[\\s]+([^\\s]+)', buffer)
    if define :
        # The whole line is consumed, return an empty string to indicate that
        buffer = ''
        group = define.group(1, 1)
        all_funcs.append(group)
    return buffer

def get_full_function_string(file, file_path, buffer, is_native) :
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
        process_function_string(file_path, full_func_str, is_native)

    return buffer

def process_function_string(file_path, func, is_native) :
    """process_function_string(string, string, bool)"""

    (functype, remaining) = func.split(' ', 1)
    functype = functype.strip()
    # TODO: Process functags
    if functype == 'functag' :
        return
    (funcname, remaining) = remaining.split('(', 1)
    funcname = funcname.strip()
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
    all_funcs.append((funcname, autocomplete))
    key = os.path.basename(file_path)[0:-4]
    funclist = funcs[key]
    funclist.append((funcname, autocomplete))
    funcs[key] = funclist

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
