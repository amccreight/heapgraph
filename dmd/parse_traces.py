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


def parse_stack_log(f):
    num_traces = 0
    incomplete = False

    in_trace = False
    blocks = None

    in_actual_trace = False
    curr_trace = None

    traces = {}
    req_sizes = {}

    for l in f:
        if not in_trace:
            if l.startswith('Live:'):
                if l.startswith('Live: stopping'):
                    incomplete = True
                    break
                in_trace = True
                num_traces += 1

            continue

        if len(l) <= 2:
            in_trace = False
            in_actual_trace = False
            continue

        if in_actual_trace:
            assert(l.startswith('   '))
            if fixed_stacks:
                fun_name = l[3:-12]
            else:
                fun_name = l[3:l.rfind('[')]

            if not boring_frames_pattern.match(fun_name):
                curr_trace.append(fun_name)
            continue

        if l.startswith(' blocks:'):
            curr_trace = []
            blocks = set(l.split()[1:])
            for b in blocks:
                traces[b] = curr_trace
            continue

        if l.startswith(' Allocated at'):
            in_actual_trace = True
            continue

        brm = bytes_requested_pattern.match(l)
        if brm:
            requested = int(brm.group(1).replace(',',''))
            for b in blocks:
                req_sizes[b] = requested

    for b, stack in traces.iteritems():
        print b, ':', req_sizes[b]
        for l in stack:
            print ' ', l[:max_frame_len]
        print

#    print req_sizes

    print
    print 'Num traces:', num_traces
    if incomplete:
        print 'Incomplete traces in file.'


def parse_stack_file(fname):
    try:
        f = open(fname, 'r')
    except:
        sys.stderr.write('Error opening file ' + fname + '\n')
        exit(-1)

    parse_stack_log(f)
    f.close()



if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    parse_stack_file(sys.argv[1])







