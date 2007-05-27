"""
Detect import statements using the AST parser.

This script outputs a comma-separated list of tuples:

  ((from_root, from_filename), (to_root, to_filename))

The roots are the root directories where the modules lie.  You can use
sfood-graph or some other tool to filter, cluster and generate a meaningful
graph from this list of dependencies.

As a special case, if the 'to' tuple is (None, None), this means to at least
include the 'from' tuple as a node.  This may happen if the file has no
dependencies on anything.

See http://furius.ca/snakefood for details.
"""

import sys, os, logging
from os.path import *
from collections import defaultdict
from operator import itemgetter

from util import iter_pyfiles, setup_logging, def_ignores
from depends import output_depends
from find import find_dependencies, ERROR_IMPORT, ERROR_SYMBOL
from roots import *



def gendeps():
    import optparse
    parser = optparse.OptionParser(__doc__.strip())

    parser.add_option('-i', '--internal', '--internal-only', action='store_true',
                      help="Filter out dependencies that are outside of the "
                      "roots of the input files")

    parser.add_option('-I', '--ignore', dest='ignores', action='append',
                      default=def_ignores,
                      help="Add the given directory name to the list to be ignored.")

    parser.add_option('-v', '--verbose', action='count', default=0,
                      help="Output more debugging information")

    parser.add_option('-f', '--follow', action='store_true',
                      help="Follow the modules depended upon and trace their dependencies. "
                      "WARNING: This can be slow.  Use --internal to limit the scope.")

    parser.add_option('--print-roots', action='store_true',
                      help="Only print the package roots corresponding to the input files."
                      "This is mostly used for testing and troubleshooting.")

    parser.add_option('-d', '--disable-pragmas', action='store_false',
                      dest='do_pragmas', default=True,
                      help="Disable processing of pragma directives as strings after imports.")

    opts, args = parser.parse_args()
    setup_logging(opts.verbose)

    if not args:
        logging.warning("Searching for files from root directory.")
        args = ['.']

    info = logging.info

    if opts.print_roots:
        inroots = find_roots(args, opts.ignores)
        for dn in sorted(inroots):
            print dn
        return

    info("")
    info("Input paths:")
    for arg in args:
        fn = realpath(arg)
        info('  %s' % fn)
        if not exists(fn):
            parser.error("Filename '%s' does not exist." % fn)

    # Get the list of package roots for our input files and prepend them to the
    # module search path to insure localized imports.
    inroots = find_roots(args, opts.ignores)
    if opts.internal and not inroots:
        parser.error("No package roots found from the given files or directories. "
                     "Using --internal with these roots will generate no dependencies.")
    info("")
    info("Roots of the input files:")
    for root in inroots:
        info('  %s' % root)

    info("")
    info("Using the following import path to search for modules:")
    sys.path = inroots + sys.path
    for dn in sys.path:
        info("  %s" % dn)
    inroots = frozenset(inroots)

    # Find all the dependencies.
    info("")
    info("Processing files:")
    info("")
    allfiles = defaultdict(set)
    allerrors = []
    processed_files = set()

    fiter = iter_pyfiles(args, opts.ignores, False)
    while 1:
        newfiles = set()
        for fn in fiter:
            if fn in processed_files:
                continue # Make sure we process each file only once.

            info("  %s" % fn)
            processed_files.add(fn)
            files, errors = find_dependencies(fn, opts.verbose, opts.do_pragmas)
            allerrors.extend(errors)

            # When packages are the source of dependencies, remove the __init__
            # file.  This is important because the targets also do not include the
            # __init__ (i.e. when "from <package> import <subpackage>" is seen).
            if basename(fn) == '__init__.py':
                fn = dirname(fn)

            # Make sure all the files at least appear in the output, even if it has
            # no dependency.
            from_ = relfile(fn, opts.ignores)
            if from_ is None:
                continue
            if opts.internal and from_[0] not in inroots:
                continue
            allfiles[from_].add((None, None))

            # Add the dependencies.
            for dfn in files:
                xfn = dfn
                if basename(xfn) == '__init__.py':
                    xfn = dirname(xfn)
                
                to_ = relfile(xfn, opts.ignores)
                if opts.internal and to_[0] not in inroots:
                    continue
                allfiles[from_].add(to_)
                newfiles.add(dfn)


        if not (opts.follow and newfiles):
            break
        else:
            fiter = iter(sorted(newfiles))


    info("")
    info("SUMMARY")
    info("=======")

    # Output a list of the symbols that could not be imported as modules.
    reports = [("Modules that could not be imported:", ERROR_IMPORT, logging.warning)]
    if opts.verbose >= 2:
        reports.append(
            ("Symbols that could not be imported as modules:", ERROR_SYMBOL, logging.debug))

    for msg, errtype, efun in reports:
        names = frozenset(name for err, name in allerrors if err is errtype)
        if names:
            efun("")
            efun(msg)
            for name in sorted(names):
                efun("  %s" % name)

    # Output the list of roots found.
    info("")
    info("Found roots:")

    found_roots = set()
    for key, files in allfiles.iteritems():
        found_roots.add(key[0])
        found_roots.update(map(itemgetter(0),files))
    if None in found_roots:
        found_roots.remove(None)
    for root in sorted(found_roots):
        info("  %s" % root)

    # Output the dependencies.
    info("")
    output_depends(allfiles)


def main():
    try:
        gendeps()
    except KeyboardInterrupt:
        raise SystemExit("Interrupted.")
    


