#!/usr/bin/env python3
"""findup.py - search upward from CWD for files/dirs like the provided findup.sh

Usage: findup.py [-a|--all] [-r|--reverse] [-A|--absolute] [-t TOPDIR] target1 [target2 ...]
"""
import argparse
import os
import sys


def collect_dirs(start, topdir):
    dirs = []
    cur = os.path.abspath(start)
    topdir = os.path.abspath(topdir)
    while True:
        dirs.append(cur)
        if cur == topdir:
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return dirs


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-a', '--all', action='store_true', dest='all')
    p.add_argument('-r', '--reverse', action='store_true', dest='reverse')
    p.add_argument('-A', '--absolute', action='store_true', dest='absolute')
    p.add_argument('-t', '--topdir', dest='topdir', default=os.path.expanduser('~'))
    p.add_argument('-h', '--help', action='store_true', dest='help')
    # parse only known options, leave the rest as targets
    opts, targets = p.parse_known_args(argv)

    if opts.help:
        print('Usage: {} [-a|--all] [-r|--reverse] [-A|--absolute] [-t|--topdir TOPDIR] file1 <file2> ...'.format(sys.argv[0]))
        return 0

    if len(targets) == 0:
        print('Error: No target file specified.', file=sys.stderr)
        return 2

    topdir = os.path.abspath(os.path.expanduser(opts.topdir))
    # cwd = os.path.abspath(os.getcwd())  # This resolves any symlinks in the cwd
    cwd = os.getenv('PWD', os.path.abspath(os.getcwd()))  # This uses PWD env var to preserve symlinks

    print(f"topdir: {topdir}\ncwd: {cwd}")
    sys.exit(1)

    dirs = collect_dirs(cwd, topdir)

    # if reverse, search from topdir downwards; otherwise from cwd upwards
    if opts.reverse:
        searchdirs = list(reversed(dirs))
    else:
        searchdirs = dirs[:]

    overall_found = False

    for ti, target in enumerate(targets):
        # found = False
        matches = []
        for d in searchdirs:
            fp = os.path.join(d, target)
            if os.path.exists(fp):
                matches.append(os.path.abspath(fp))
                # found = True
                overall_found = True
                if not opts.all:
                    break

        for fp in matches:
            # print using ~ substitution when under topdir (mirror original behaviour)
            try:
                common = os.path.commonpath([topdir, fp])
            except ValueError:
                common = None
            if common == topdir:
                rel = fp[len(topdir):]
                if rel.startswith(os.sep):
                    print('~' + rel)
                else:
                    print('~/' + rel)
            else:
                print(fp)

        if ti != len(targets) - 1:
            print()

    return 0 if overall_found else 1


if __name__ == '__main__':
    sys.exit(main())
