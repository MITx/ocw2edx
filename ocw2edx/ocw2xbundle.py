#!/usr/bin/python
#
# Convert OpenCourseWare course content data download dump into an edX course XML ("OLX").
#

import os
import sys
import json
import re
import zipfile
import shutil
import tempfile
import requests

from srt2sjson import convert2sjson
from lxml import etree
from lxml.html.soupparser import fromstring as fsbs
from path import path	# needs path.py

from xbundle import XBundle, DEF_POLICY_JSON, DEF_GRADING_POLICY_JSON

#-----------------------------------------------------------------------------

class OCWCourse(object):
    '''
    Convert OpenCourseWare course content data download dump into an edX course XML ("OLX").
    '''
    DefaultSemester = 'course'
    DefaultOrg = "OCW"

    def __init__(self, fn=None, ofn=None, verbose=True, include_media=True):
        '''
        fn = directory of input OCW content files, or input zip filename
        ofn = edX XML output directory name, or output xbundle XML filename (*.xml), or output .tar.gz filename

        After instantiating, call process() to generate the output.
        '''
        self.verbose = verbose
        self.include_media = include_media
        if self.verbose:
            print "=" * 77
            print "Processing input OCW course data file %s" % fn
            sys.stdout.flush()
        self.do_delete_dir = False

        if fn.endswith(".zip"):
            self.dir = None
            tmp_dpath = tempfile.mkdtemp(prefix="tmp_ocw2edx")
            zf = zipfile.ZipFile(fn)
            zf.extractall(tmp_dpath)
            # get course directory within zipfile
            for dfn in os.listdir(tmp_dpath):
                if os.path.isdir(path(tmp_dpath) / dfn):
                    self.dir = path(tmp_dpath) / dfn
            if not self.dir:
                raise Exception("[OCWCourse] Failed to get course directory for unpacked ZIP file %s, located in %s" % (fn, tmp_dpath))
            self.do_delete_dir = True
        else:
            self.dir = path(dir)
        self.output_fn = ofn

    def process(self):
        '''
        Process input file, and generate output xbundle or OLX in directory
        '''
        if not os.path.exists(self.dir / 'contents/Syllabus'):
            if os.path.exists(self.dir / 'contents/syllabus'):
                os.symlink('syllabus', self.dir / 'contents/Syllabus')
                print "Made a symlink from contents/syllabus to contents/Syllabus"

        self.indexfn = self.dir / 'contents/Syllabus/index.htm'
        if self.verbose:
            print "...Parsing index.htm.xml"
            sys.stdout.flush()
        self.index_xml = etree.parse(self.dir / 'contents/index.htm.xml').getroot()
        if self.verbose:
            print "...Parsing metadata"
            sys.stdout.flush()
        self.meta = self.get_metadata()
        if self.verbose:
            print "...Constructing policies"
            sys.stdout.flush()
        self.policies = self.get_policies(self.meta)
        if self.verbose:
            print "...Exporting OLX data"
            sys.stdout.flush()
        self.export()

    @staticmethod
    def parse_broken_html(xmlstr=None, fn=None, parser_type='html', parser=None):
        '''
        Parse broken HTML, either using lxml's HTML parser, or using BeautifulSoup
        '''
        xmlstr = xmlstr or open(fn).read()
        if parser_type=="bs":
            return fsbs(xmlstr)
        elif parser_type=="html":
            parser = parser or etree.HTMLParser()
            return etree.fromstring(xmlstr, parser=parser)

    def get_caption_file(self, url):
        '''
        Retrieve srt caption file from OCW, convert to sjson, and store in static
        input urls are like /courses/physics/8-05-quantum-physics-ii-fall-2013/video-lectures/lecture-1-wave-mechanics/QI13S04w8dM.srt
        output filenames are like "static/subs_<ytid>.srt.sjson"
        '''
        srtfn = os.path.basename(url)
        ytid = srtfn[:-4]
        ret = requests.get(url)
        if not ret.status_code==200:
            raise Exception("[OCWCourse.get_caption_file] Failed to retrieve %s" % url)
        sdir = self.dir / "captions"
        if not sdir.exists():
            os.mkdir(sdir)
        srtfn = sdir / srtfn
        with open(srtfn, 'w') as fp:
            fp.write(ret.content)
        convert2sjson(srtfn, verbose=False)	# generate srt.sjson 
        sjfn = srtfn + ".sjson"        
        efn = "static/subs_%s" % sjfn.basename()
        self.files_to_copy[sjfn] = efn
        if self.verbose:
            print "        Got caption file %s -> %s" % (sjfn, efn)

    def fix_static(self, s):
        '''
        Fix a static path.  Return new static path.
        '''
        m = re.match('[\./]+/(contents|common|[^/ ]+)/.*', s)
        if not m:
            print "      WARNING: unknown static file path %s" % s
            return s
        prefix = m.group(1)
        newpath = re.sub('[\./]+/%s/' % prefix, '/static/', s)
        if newpath.startswith('/static'):
            spath = self.dir / prefix + newpath[7:]
            epath = newpath[1:]
            if not os.path.exists(spath):	# source path doesn't exist!
                print "      ERROR: missing file %s (for %s)" % (spath, epath)
                return ""
            self.files_to_copy[spath] = epath
            return newpath
        else:
            print "    ERROR: failed static path %s -> new path %s" % (s, newpath)
        return s


    def do_href(self, elem):
        '''
        fix href and src in element elem to point to /static
        copy static thing to /static directory
        '''
        #print "elem: %s" % elem
        for a in elem.findall('.//a'):
            href = self.fix_static(a.get('href',''))
            if href:
                a.set('href',href)
        for img in elem.findall('.//img'):
            print "      img: %s" % etree.tostring(img)
            src = self.fix_static(img.get('src',''))
            if src:
                img.set('src',src)
        
    
    def add_video_to_vert_from_popup(self, vxml, vert):
        '''
        Add a <video> based on a popup <a> link.

        vxml = <a> element from OCW file
        vert = <vertical> element from edX xml, to which the <video> is to be added
        '''
        popup = vxml.get('onclick')
        dn = vxml.text.strip()
        m = re.search("youtube.com/v/([^']+)'",popup)
        ytid = m.group(1)
        video = etree.SubElement(vert, 'video')
        video.set('youtube','1.0:%s' % ytid)
        video.set('from','00:00:20')	# default start point

        m = re.search('load_multiple_media_chapter\(.*,([ 0-9]+),([ 0-9]+),\snull\);', popup)
        if m:
            # print "    ", popup
            def sec2code(secstr):
                sec = int(secstr.strip())
                c = '%02d:%02d:%02d' % (sec/3600, (sec/60)%60, sec%60)
                # print "      %s (%s) -> %s" % (secstr, sec, c)
                return c
            video.set('from',sec2code(m.group(1)))
            video.set('to',sec2code(m.group(2)))
        
        video.set('display_name','Video: ' + dn)
        #print "      video: %s = %s" % (ytid, dn)
        print "      video: %s = %s" % (etree.tostring(video), dn)


    def add_pdf_link_to_vert(self, pdffn, text, vert):
        '''
        Add <html> with link to PDF file to vertical
        '''
        newpath = self.fix_static('../' + pdffn)
        dn = text.strip()
        html = etree.XML('<html><a href="%s">%s</a></html>' % (newpath, dn))
        if self.verbose:
            print "      html link: %s = %s" % (dn, newpath)
        vert.append(html)


    def add_contents_to_vert(self, vxml, vert):
        '''
        Create a module (video or html) for the block contents of a section of an OCW chapter.

        vxml = vert <a> from scholar
        vert = edX vertical
        '''
        # if the <a> has a onclick with youtube in it, then make a <video>
        if 'youtube.com' in vxml.get('onclick',''):
            self.add_video_to_vert_from_popup(vxml, vert)
            return
            
        # otherwise follow the href link and process the file
        href = vxml.get('href')
        
        vfn = re.sub('[\./]+/contents/','contents/', href)
        if vfn.endswith('.pdf'):
            self.add_pdf_link_to_vert(vfn, vxml.text, vert)
            return

        # process html file
        try:
            fn = self.dir / vfn
            vcontents = self.parse_broken_heml(fn=fn)
        except Exception as err:
            print "      ERROR reading %s: %s" % (fn, err)
            return
        nav = vcontents.find('.//div[@id="parent-fieldname-text"]') # v.find('.//p[@class="sc_nav"]')
        html = etree.SubElement(vert,'html')
        html.set('display_name',vert.get('display_name','Page'))
        for p in nav:
            # print etree.tostring(p,pretty_print=True)
            if p.get('class','') in ['sc_nav', 'sc_nav_bottom']:
                continue
            elif etree.tostring(p).startswith('<p>&#160;</p>'):
                continue
            else:
                self.do_href(p)
                # print etree.tostring(p)
                html.append(p)
    
        vidclasses = ['embedbg','inline-video']
        for vc in vidclasses:
            for vid in html.findall('.//div[@class="%s"]' % vc):
                self.add_video_to_vert_from_div(vc, vid, vert)
        #print "html: %s" % etree.tostring(html)
        #print "------------------------------------------------------------"
    
    
    def add_video_to_vert_from_div(self, vc, embedbg, vert):
        '''
        Add a video to a edX vertical, based on an OCW <div>

        vc = the class of the video div
        embedbg = <div> with class embedbg or inline-video
        vert = edX vertical to which to add the <video>
        '''
        # get the title - it's a h3 right before the div
        prev = embedbg.getprevious()
        if prev is None:
            title = vert.get('display_name')
        else:
            title = prev.text
        
        # get the youtube ID
        script = embedbg.find('.//script')
        if script is None:
            print "oops, no script?  embedbg=%s" %  etree.tostring(embedbg)
            return
        else:
            self.add_video_from_script_element(title, script, vert)
            embedbg.getparent().remove(embedbg)
    
    def add_video_to_vert_from_main(self, title, main_elem, vert):
        '''
        Add a video to a edX vertical, based on an OCW <main id="course_inner_media"> 
        main_elem = <main> element
        vert = edX vertical to which to add the <video>
        '''
        # get the caption file from the first script
        script1 = main_elem.find('.//script')
        if script1 is None:
            print "oops, no script?  main_elem=%s" %  etree.tostring(main_elem)
            return
        stext = etree.tostring(script1)
        if not "caption_embed" in stext:
            print "oops, was expecting caption link in %s" % stext
        else:
            m = re.search("'(/courses/[^ ]+.srt)'", stext)
            if not m:
                print "missing caption for main_elem=%s" %  etree.tostring(main_elem)
                extra_dict = {}
            else:
                caption_url = "https://ocw.mit.edu" + m.group(1)
                extra_dict = {'caption_url': caption_url}
                self.get_caption_file(caption_url)

        script = main_elem.findall('.//script')[1]
        if script is None:
            print "oops, no script?  main_elem=%s" %  etree.tostring(main_elem)
            return
        else:
            self.add_video_from_script_element(title, script, vert, extra_dict)

    def add_video_from_script_element(self, title, script, vert, extra_dict=None):
        '''
        Extract youtube id from <script> element and add to the edX OLX vert element as a <video>
        '''
        extra_dict = extra_dict or {}
        m = re.search("http[s]*://www.youtube.com/v/([^']+)'",script.text)
        if not m:
            print "oops, cannot find youtube id in %s" % script.text
        else:
            ytid = m.group(1)
            video = etree.SubElement(vert,'video')
            video.set('youtube','1.0:%s' % ytid)
            video.set('from','00:00:20')
            for k, v in extra_dict.items():
                video.set(k, v)
            #video.set('display_name','Video: ' + vert.get('display_name','Page'))
            video.set('display_name','Video: ' + title)
            if self.verbose:
                print "      video: %s = %s" % (ytid, title)
                if self.verbose > 1:
                    print "        (%s) %s" % (vert.get('display_name'), etree.tostring(video))
            # print etree.tostring(html)
    
    
    def get_xml_fn_from_href(self, href):
        '''
        Get absolute local filename path from an <a href> in the OCW content.
        '''
        sfn = href.replace('../../','')
        xmlfn = self.dir / sfn
        return xmlfn

    def process_media_gallery(self, title, display_name, ocw_xml, seq):
        '''
        Process media gallery section of OCW course content (turn into verticals)
        '''
        nav = ocw_xml
        for div in nav:				# include all content in the HTML as an introduction
            if div.get('class','') in ['media_rss_link']:
                continue
            elif div.get('class','') in ['medialisting']:
                # embedded media listing video
                aelem = div.find('.//a')
                href = aelem.get('href')
                xmlfn = self.get_xml_fn_from_href(href)
                if xmlfn in self.processed_files:
                    print "--> Already processed file %s, skipping" % xmlfn
                    return
                self.processed_files.append(xmlfn)
                title = aelem.get('title')
                dn = "Video " + title
                print "    vertical: ", dn
                vert = etree.SubElement(seq,'vertical')
                vert.set('display_name',dn)
                self.process_course_inner_media(title, xmlfn, vert)

    def process_course_inner_media(self, title, fn, vert):
        '''
        Digest single OCW media file and process as video for edX XML
        '''
        cxml = self.parse_broken_html(fn=fn)
        main = cxml.find('.//main[@id="course_inner_media"]')
        if main is None:
            print "--> Error - no course_inner_media found in file %s" % fn
            return
        self.add_video_to_vert_from_main(title, main, vert)

    def process_html(self, title, display_name, ocw_xml, seq, handle_broken_xml=False):
        '''
        Process HTML section of OCW course content (turn into verticals, possibly wth video)
        '''
        intro = etree.SubElement(seq, 'html')	# add HTML module in the edX xml tree
        if self.verbose:
            print '    Adding html: %s' % title
        intro.set('display_name', display_name)
        nav = ocw_xml
        if handle_broken_xml:
            # OCW XML doesn't close a bunch of tags!  This can cause fsbs to mis-parse <main><p>...</p></main> into <main></main><p>...</p> 
            if len(nav)==0:
                # try grabbing all <p> from parent
                nav = [x for x in nav.getparent() if x.tag in ['p', 'div'] ]
        for p in nav:				# include all content in the HTML as an introduction
            if p.get('class','') in ['sc_nav', 'sc_nav_bottom']:
                continue
            elif p.tag in ['main', 'nav']:
                continue
            elif etree.tostring(p).startswith('<p>&#160;</p>'):
                continue
            elif (p.tag=='blockquote') or (p.tag=='p' and len(p)==1 and p[0].tag=='a'):
                # embedded video or other content ; make this a separate module
                # if single link, likely a PDF
                for a in p.findall('.//a'):
                    if not a.text:
                        continue
                    dn = a.text.strip()
                    toskip = ['iTunes U', 'Internet Archive', 'Removed Clips' ]
                    if any((x in dn) for x in toskip):
                        continue
                    print "    vertical: ", dn
                    vert = etree.SubElement(seq,'vertical')
                    vert.set('display_name',dn)
                    self.add_contents_to_vert(a, vert)
            else:
                self.do_href(p)
                intro.append(p)
        if len(intro)==0:
            intro.getparent().remove(intro)	# remove intro if empty

    def robust_get_main(self, fn, ocw_xml, idname, tags=None):
        '''
        The OCW XML is full of XML errors, e.g. with unclosed img tags, and improperly formatted attributes.
        Try to get a <main> or <div> with the specified id=idname, robustly.  That is,
        if the length of the found element is zero, then get its parent instead.

        fn = filename (for error messages)
        ocw_xml = etree element for the OCW xml
        idname = string giving element id to look for
        tags = list of element tags to look for (defaults to ["div", "main"])
        '''
        tags = tags or ["div", "main"]
        for tag in tags:
            elem = ocw_xml.find('.//%s[@id="%s"]' % (tag, idname))
            if elem is not None:
                break
        if elem is None:
            return None
        if len(elem)==0:
            if self.verbose:
                print "        Warning - badly formatted XML in file %s for %s" % (fn, etree.tostring(elem))
                sys.stdout.flush()
            elem = elem.getparent()
            if self.verbose:
                print "            Using parent %s instead - has %d children" % (elem.tag, len(elem))
                sys.stdout.flush()
        return elem

    def do_verticals(self, sxml, seq):
        '''
        Create vertical and fill up with contents of a section of a chapter.
        We are given the <a> for the OCW section, and the XML handle for the
        sequential where the contents should go.

        sxml = seq <a> from scholar
        seq = edX sequential
        '''
        href = sxml.get('href')
        xmlfn = self.get_xml_fn_from_href(href)
        if xmlfn in self.processed_files:
            print "--> Already processed file %s, skipping" % xmlfn
            return
        self.processed_files.append(xmlfn)
        display_name = "Introduction"

        print "  Reading vertical from file %s" % xmlfn
        v = self.parse_broken_html(fn=xmlfn)	# load in the section HTML file

        title = v.find('.//span[@id="parent-fieldname-title"]') 
        display_name = title.text.strip()

        found_elements = []

        nav = v.find('.//div[@id="parent-fieldname-text"]') 
        if nav is None:
            nav = self.robust_get_main(xmlfn, v, "course_inner_section")
        if nav is not None:
            self.process_html(title, display_name, nav, seq, handle_broken_xml=True)
            found_elements.append("html")

        if self.include_media:
            nav = self.robust_get_main(xmlfn, v, "course_inner_media_gallery")
            if nav is not None:
                self.process_media_gallery(title, display_name, nav, seq)
                found_elements.append("media")

        if not found_elements:
            print "    Oops, no sub-elements (parent-fieldname-text or course_inner_section) found for vertical in %s" % xmlfn
            return

    
    def do_chapters(self, ocw_xml, edxxml):
        '''
        In an OCW syllabus file, the chapter is described by a <div class="course_nav">
        The elements of the <ul> within that div are the chapters.
        
        We turn the contents of each chapter are sections; we turn those sections
        into sequentials.
        '''
        nav_div = ocw_xml.find('.//div[@id="course_nav"]')	# older OCW courses
        if nav_div is None:
            nav_div = ocw_xml.find('.//nav[@id="course_nav"]')	# newer OCW courses
        if nav_div is None:
            raise Exception("[OCWCourse.do_chapters] (%s) Failed to find main course navigation list in syllabus index.htm" % self.dir)
        
        chapters_xml = nav_div.find('ul')
        for c in chapters_xml:
            # each c should be a <li>; take the first a that is not href="#' for the chapter name
            atags = [a for a in c.findall('.//a') if not a.get('href')=='#']
            if not atags:
                continue
            dn = atags[0].text.strip()
            if dn=='Course Home':
                continue

            print "chapter: ", dn

            chapter = etree.SubElement(edxxml,'chapter')
            chapter.set('display_name',dn)

            for atag in atags:
                href = atag.get('href')
                xmlfn = self.get_xml_fn_from_href(href)
                if xmlfn in self.processed_files:
                    print "--> Already processed file %s, skipping" % xmlfn
                    continue
                dn = atag.text.strip()
                print "  section: ", dn
                seq = etree.SubElement(chapter,'sequential')
                seq.set('display_name',dn)
                self.do_verticals(atag, seq)
        
    def get_metadata_field(self, mseq, root=None):
        if root is None:
            root = self.index_xml
        namespaces={'lom':'https://ocw.mit.edu/xmlns/LOM'}
        x = root
        for v in mseq:
            try:
                x = x.find('.//lom:%s' % v,namespaces=namespaces)
            except Exception as err:
                raise Exception("[OCWCourse.get_metadata_field] (%s) failed to get metadata field %s, error on %s, err=%s" % (self.dir, mseq, v, str(err)))
        return x.text
    
    def get_metadata(self):
        meta = {}
        root = self.index_xml
        fk = {'course': ['identifier','entry'],
              'name': ['title', 'string'],
              }
        for k, mseq in fk.items():
            meta[k] = self.get_metadata_field(mseq,root)
        return meta
    
    def add_about_files(self, xb):
        '''xb = XBundle instance'''
        description = self.get_metadata_field(['description','string'])
        xb.add_about_file('effort.html', '4 hours per week')
        xb.add_about_file('end_date.html', '')
        xb.add_about_file('overview.html', '<html>%s</html>' % description)
        xb.add_about_file('prerequisites.html', 'None')
        xb.add_about_file('short_description.html', description)
        xb.add_about_file('video.html', '')
    
    def pp_xml(self, xml):
        os.popen('xmllint --format -o tmp.xml -','w').write(etree.tostring(xml))
        return open('tmp.xml').read()

    #-----------------------------------------------------------------------------
    
    def get_policies(self, meta):
        cid = meta['course']
        name = meta['name']
        self.cid = cid
        self.name = name
        policies = etree.Element('policies')
        policies.set('semester',self.DefaultSemester)

        gp = etree.SubElement(policies,'gradingpolicy')
        gp.text = DEF_GRADING_POLICY_JSON

        pjson = DEF_POLICY_JSON.replace("course/2013_Spring", "course/%s") % self.DefaultSemester
        pjson = pjson.replace('4201x',cid.replace('.',''))
        pdict = json.loads(pjson)
        semester = pdict.keys()[0]
        if not semester=='course/%s' % self.DefaultSemester:
            raise Exception('default semester in DEF_POLICY_JSON does not match DefaultSemester')
        pdict[semester]['display_name'] = self.name

        policy = etree.SubElement(policies,'policy')
        policy.text = json.dumps(pdict, indent=4)

        return policies
    
    #-----------------------------------------------------------------------------
    
    def get_course_image(self):
        fn = self.dir/'contents/index.htm'
        root = self.parse_broken_html(fn=fn)
        div = self.robust_get_main(fn, root, "course_inner_chp")
        if div is None:
            raise Exception("[OCWCourse.get_course_image] Cannot find course_inner_chp in %s" % fn)
        img = div.find('.//img[@itemprop="image"]')
        fn = img.get('src')
        fn = fn[3:]	# remove ../
        fn = self.dir / fn
        # os.system('mkdir -p static/images')
        # os.system('cp %s static/images/course_image.jpg' % fn)
        self.files_to_copy[fn] = "static/images/course_image.jpg"
        print "--> course image: %s" % fn

    def copy_static_files(self, destdir):
        '''
        Copy static files specified in self.files_to_copy to the destdir
        Do this all at once, because destdir may be different depending on the output format (eg .tar.gz)
        '''
        for src, dst in self.files_to_copy.items():
            dd = "%s/%s" % (destdir, os.path.dirname(dst))
            if not os.path.exists(dd):
                cmd = "mkdir -p '%s'" % dd
                if 1 or self.verbose > 2:
                    print "    " + cmd
                os.system(cmd)
            cmd = "cp '%s' '%s/%s'" % (src, destdir, dst)
            if 1 or self.verbose > 2:
                print "    " + cmd
            os.system(cmd)

    #-----------------------------------------------------------------------------
    
    def export(self):
        meta = self.meta
        sys.stderr.write("metadata = %s\n" % meta)
    
        fn = self.dir / 'contents/Syllabus/index.htm'
        sxml = self.parse_broken_html(fn=fn)
        edxxml = etree.Element('course')
        edxxml.set('dirname',os.path.basename(os.getcwd()))
        edxxml.set('semester', self.DefaultSemester)
        for k, v in meta.items():
            edxxml.set(k,v)
        
        self.processed_files = [fn]		# track which content files have been ingested, to avoid duplication
        self.files_to_copy = {}			# dict of files (key=OCW source, val=edX static dest) to copy to "/static"
        self.do_chapters(sxml, edxxml)
    
        policies = self.policies

        # grab course image via index.htm
        self.get_course_image()
        
        # make xbundle 
        xb = XBundle()
        xb.DefaultOrg = self.DefaultOrg
        xb.set_course(edxxml)
        xb.add_policies(policies)
        self.add_about_files(xb)

        # save it
        outfn = self.output_fn or ('%s_xbundle.xml' % self.cid)
        if outfn.endswith(".xml"):
            xb.save(outfn)
            self.copy_static_files(".")
        elif outfn.endswith(".tar.gz") or outfn.endswith(".tgz"):
            tempd = tempfile.mkdtemp(prefix="tmp_ocw2xbundle")
            cdir = path(tempd) / "course"
            os.mkdir(cdir)
            self.copy_static_files(cdir)
            xb.export_to_directory(cdir, dir_include_course_id=False)
            curdir = os.path.abspath(os.curdir)
            cmd = "cd %s; tar czf '%s/%s' course" % (tempd, curdir, outfn)
            print cmd
            os.system(cmd)
            shutil.rmtree(tempd)
        else:
            if not os.path.exists(outfn):
                print "Making directory for output: %s" % outfn
                os.mkdir(outfn)
            self.copy_static_files(outfn)
            xb.export_to_directory(outfn, dir_include_course_id=False)
        print "Done, wrote to %s" % outfn
    

#-----------------------------------------------------------------------------

if __name__=='__main__':
    ocwc = OCWCourse(sys.argv[1])
    ocwc.process()
    
