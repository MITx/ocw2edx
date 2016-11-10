'''
Convert MIT OpenCourseWare content download file to OLX format for import into edX-platform instance
'''

import argparse
from ocw2xbundle import OCWCourse

def CommandLine(args=None, arglist=None):
    '''
    Main command line.  Accepts args, to allow for simple unit testing.
    '''

    # Read arguments from command line
    parser = argparse.ArgumentParser()
    parser.add_argument("ocw_zip_file_name", help="name of zip file with OCW course data", type=str, nargs='+')
    parser.add_argument("-o", "--output-file", type=str, help="filename for output file (single-file if ends with .xml, directory otherwise)")
    parser.add_argument("--suppress-media", help="do not include media, like videos", action="store_true")

    if not args:
        args = parser.parse_args(arglist)
    
    for zfn in args.ocw_zip_file_name:
        ocwc = OCWCourse(fn=zfn, ofn=args.output_file, include_media=(not args.suppress_media))
        ocwc.process()
        
