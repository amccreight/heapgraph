#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parse the DMD stack trace log format, post-bug 1035570, which landed in Firefox 34.

import sys
import re

blank_line_patt = re.compile('^\w*$')

trim_print_line_to = 80

def print_scope(scope, indent=''):
    for header_line in scope[0]:
        print indent + header_line[:trim_print_line_to]
    for subtree in scope[1]:
        print indent + subtree[0]
        print_scope(subtree[1], indent + '  ')
        if len(indent) == 0:
            print


def scope_frame():
    return ([], [])

def parse_stack_log(f):
    outer = scope_frame()
    scopes = [outer]

    count = 0

    for l in f:
        # Skip comment lines and blank lines.
        if l.startswith('#'):
            continue

        if blank_line_patt.match(l):
            continue

        # Lines ending in '{' start a new section.
        if l[-2] == '{':
            new_section = l[:-2].strip()
            new_scope = scope_frame()
            scopes[-1][1].append((new_section, new_scope))
            scopes.append(new_scope)
            continue

        # Lines ending in '}' end a section.
        if l[-2] == '}':
            scopes.pop()
            if len(scopes) == 1:
                count += 1
                if count == 3:
                    break
            continue

        # Other lines are data for the current record.
        scopes[-1][0].append(l.strip())

    return outer


def parse_stack_file(fname):
    try:
        f = open(fname, 'r')
    except:
        sys.stderr.write('Error opening file ' + fname + '\n')
        exit(-1)

    r = parse_stack_log(f)
    f.close()
    return r


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    print_scope(parse_stack_file(sys.argv[1]))








