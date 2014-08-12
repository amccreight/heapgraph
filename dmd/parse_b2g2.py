#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Parse the DMD stack trace log format.

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



first_line_patt = re.compile('^Unreported: \~?([0-9,]+) blocks? in stack trace record [0-9,]+ of [0-9,]+\n$')
second_line_patt = re.compile('^ ~?([0-9,]+) bytes \(~?[0-9,]+ requested \/ ~?[0-9,]+ slop\)\n$')
third_line_patt = re.compile('^.*cumulative\)\n$')


def decomma_number_string(s):
    return int(''.join(s.split(',')))

def filter_record_header(l):
    flm = first_line_patt.match(l)
    if flm:
        # Number of blocks in this record.
        return int(flm.group(1))
    slm = second_line_patt.match(l)
    if slm:
        # Total allocation for blocks with this stack.
        return decomma_number_string(slm.group(1))
    tlm = third_line_patt.match(l)
    if tlm:
        return None
    print 'BAD LINE', l
    exit(-1)


#Unreported: 1 block in stack trace record 1 of 927
# 1,454,080 bytes (1,454,080 requested / 0 slop)
# 4.12% of the heap (4.12% cumulative);  10.31% of unreported (10.31% cumulative)

#Unreported: ~45 blocks in stack trace record 8 of 927
# ~184,185 bytes (~184,185 requested / ~0 slop)
# 0.52% of the heap (15.11% cumulative);  1.31% of unreported (37.77% cumulative)

def parse_stack_log(f):
    in_header = True
    in_section_header = False
    section_name = None
    skip_section = None

    in_record_header = None
    curr_record = None
    record_count = None

    records = []

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
                skip_section = not care_about_this_section(section_name)
                if not skip_section:
                    record_count = 0
            continue

        if l == divider:
            in_section_header = True
            continue

        if skip_section:
            continue

        if l == '\n':
            if curr_record:
                record_count += 1
                records.append(curr_record)

            # Start the new header
            in_record_header = True
            curr_record = []
            continue

        if in_record_header:
            if l == ' Allocated at\n':
                in_record_header = False
                curr_record.append([])
                continue
            r = filter_record_header(l)
            if r:
                curr_record.append(r)
            continue

        curr_record[-1].append(l.lstrip().rstrip())


    return records


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







