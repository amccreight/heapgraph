#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Take a diff of two DMD stack records.

import sys
import parse_33_report
import parse_report


new_log_format = True


def mapify_traces(traces):
    m = {}
    for t in traces:
        k = '{'.join(t[2])
        m[k] = t

    return m


# XXX hacky
def frame_split(frame):
    return frame.split(' /local/')[0]


def print_stack_trace(trace):
    for frame in trace:
        print ' ', frame_split(frame)


def print_diff_entry(size, data):
    print 'Change in size: {0} bytes. {1}'.format(size,
                                                  'New stack trace.' if len(data) == 1 else 'Entry increased in size.')
    print_stack_trace(data[0][2])
    print


def load_traces(file_name):
    if new_log_format:
        return parse_report.load_diff_info(file_name)
    else:
        return parse_33_report.parse_stack_file(file_name)

def diff_logs(f1, f2):
    m1 = mapify_traces(load_traces(f1))
    m2 = mapify_traces(load_traces(f2))

    new_stuff = {}

    for k, data2 in m2.iteritems():
        data1 = m1.get(k, None)
        if data1:
            [num_records1, num_bytes1, _] = data1
            [num_records2, num_bytes2, _] = data2
            if num_bytes1 == num_bytes2:
                # Not really something we can assert, but whatever.
                assert num_records1 == num_records2
                continue
            if num_bytes1 > num_bytes2:
                # Not really something we can assert, but whatever.
                assert num_records1 > num_records2
                continue
            new_bytes = num_bytes2 - num_bytes1
            new_stuff.setdefault(new_bytes, []).append([data1, data2])
        else:
            new_bytes = data2[1]
            new_stuff.setdefault(new_bytes, []).append([data2])

    sizes = sorted(list(new_stuff))
    sizes.reverse()

    num_printed = 0

    for s in sizes:
        entries = new_stuff[s]
        for e in entries:
            print_diff_entry(s, e)
            num_printed += 1

            # For now, just print a few.
            if num_printed > 3:
                exit(-1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.stderr.write('Not enough arguments.\n')
        exit()

    diff_logs(sys.argv[1], sys.argv[2])





