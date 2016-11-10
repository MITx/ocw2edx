#!/usr/bin/python
#
# Convert OCW's video subtitle srt file format to edX's srt.sjson format.
#
# Example of edX srt.sjson file format:
# 
# {
#   "start": [], 
#   "end": [], 
#   "text": []
# }
#
# {
#   "start": [
#     220, 
#     3460, 
#     6020, 
#     6870, 
#     9160, 
#   ], 
#   "end": [
#     3460, 
#     6020, 
#     6870, 
#     9160, 
#     10830, 
#   ], 
#   "text": [
#     "Well, those are your tools for edX.", 
#     "Bear in mind that we are still in the early stages of", 
#     "development.", 
#     "So we might be tweaking parts of the site as the term", 
#     "progresses.", 
#   ]
# }
#
# Usage:
#
# python srt2sjson.py [file1.srt] [file2.srt] ...
#
# creates file1.srt.sjson, file2.srt.sjson, ...

import os, sys, string, re
import json

def time2ms(tm):
    (hour,min,sec,milisec) = map(int,tm.split(':'))
    return int(1000 * (sec+60*(min+60*hour)))

def convert2sjson(fn=None, srt_string=None, do_write=True, verbose=True):
    if fn and not fn.endswith('.srt'):
        print "not srt file - skipping %s!" % fn
        return

    sub_starts = []
    sub_ends = []
    sub_texts = []    

    mode = 0
    srt_string = srt_string or open(fn).readlines()
    if type(srt_string)==str:
        srt_string = srt_string.split('\n')

    for k in srt_string:
        m = re.match('[0-9]+$',k.strip())
        if mode==0 and m:
            mode = 1
            continue
        elif mode==1:
            m = re.match('(\d\d:\d\d:\d\d:\d\d\d) --> (\d\d:\d\d:\d\d:\d\d\d)',k)
            if not m:
                k = k.replace(',',':')
                m = re.match('(\d\d:\d\d:\d\d:\d\d\d) --> (\d\d:\d\d:\d\d:\d\d\d)',k)
                if not m:
                    print "Error! aborting, unexpected line %s" % k
                    sys.exit(-1)
            (start,end) = map(time2ms, m.groups())
            sub_starts.append(start)
            sub_ends.append(end)
            mode = 2
            text = ''
            continue
        elif mode==2:
            k = k.strip()
            if k:
                text += k + ' '
            else:
                sub_texts.append(text.strip())
                mode = 0

    subs_dict={'start':sub_starts,
               'end':sub_ends,
               'text':sub_texts}

    outstr = json.dumps(subs_dict, indent=4)
    if do_write:
        # write out file
        ofn = fn+'.sjson'
        if verbose:
            print "%s -> %s" % (fn, ofn)
        open(ofn,'w').write(outstr)
    return outstr

#-----------------------------------------------------------------------------

def test1():
    sjson = convert2sjson("test/data/test1.srt", do_write=False)
    print sjson
    data = json.loads(sjson)
    assert len(data['start'])==len(data['end'])
    assert len(data['start'])==len(data['text'])
    assert len(data)==3
    assert "So, we'll get started." in data['text']

def test2():
    ss = open("test/data/test1.srt").read()
    sjson = convert2sjson(srt_string=ss, do_write=False)
    print sjson
    data = json.loads(sjson)
    assert len(data['start'])==len(data['end'])
    assert len(data['start'])==len(data['text'])
    assert len(data)==3
    assert "So, we'll get started." in data['text']

#-----------------------------------------------------------------------------

if __name__=="__main__":
    for fn in sys.argv[1:]:
        convert2sjson(fn)


