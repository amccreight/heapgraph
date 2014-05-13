#!/usr/bin/python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import sys
import cc.count
import g.count
import os

if len(sys.argv) < 2:
    sys.stderr.write('Expected at least one argument, the edge file name.\n')
    sys.exit(1)

# This is a top-level driver script for the GC and CC log find_roots
# scripts.  It just looks at the first two letters of the file name
# passed in as an argument.  If the file starts with 'cc', it assumes
# you must want the CC script.  If the file starts with 'gc', it
# assumes you must want the GC script.

baseFileName = os.path.basename(sys.argv[1])

if baseFileName.startswith('cc'):
    cc.count.countNodeLabels()
elif baseFileName.startswith('gc'):
    g.count.countNodeLabels()
else:
    sys.stderr.write('Expected log file name to start with cc or gc.\n')
