#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parse the DMD stack trace log format, with included blocks.

import sys
import re


max_frame_len = 150

def boring_frames_regexp():
    boring_frames = ['replace_malloc',
                     'replace_realloc',
                     'replace_calloc',
                     'malloc_zone_malloc',
                     'malloc_zone_calloc',
                     'moz_xmalloc',
                     'moz_xrealloc',
                     'malloc',
                     'realloc',
                     'calloc',
                     'XPT_ArenaMalloc',
                     'XPT_DoHeader',
                     'operator new(unsigned long)',
                     'XREMain::XRE_main(int, char**, nsXREAppData const*)',
                     'XRE_main',
                     'main',
                     '???']

    escaped_boring_frames = []
    for f in boring_frames:
        escaped_boring_frames.append(re.escape(f))

    return '|'.join(escaped_boring_frames)

boring_frames_pattern = re.compile(boring_frames_regexp())

bytes_requested_pattern = re.compile(' [0-9,]+ bytes \(([0-9,]+) requested')


fixed_stacks = True
print_results = False


divider = '------------------------------------------------------------------\n'


def care_about_this_section(section_name):
    return section_name == 'Unreported stack trace records'


def parse_stack_log(f):
    in_header = True
    in_section_header = False
    section_name = None
    record_section = None

    for l in f:
        # Skip comment lines.
        if l.startswith('#'):
            continue

        if in_header:
            if l == divider:
                in_header = False
                in_section_header = True
            continue

        if in_section_header:
            if l == divider:
                in_section_header = False
            else:
                section_name = l[:-1]
                record_section = care_about_this_section(section_name)
                if record_section:
                    print 'SECTION NAME', section_name
            continue

        if l == divider:
            in_section_header = True


    return []


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

    print parse_stack_file(sys.argv[1])







