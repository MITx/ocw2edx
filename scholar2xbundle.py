#!/usr/bin/python
#
# Convert Scholar data download dump into an edX course xbundle
#

import os
import sys
import json
import re
import yaml

from lxml import etree
from lxml.html.soupparser import fromstring as fsbs
from path import path	# needs path.py

from xbundle import *

#-----------------------------------------------------------------------------
# scholar course class

class ScholarCourse(object):
    
    DefaultSemester = '2013_Spring'

    def __init__(self, dir='.'):
        self.dir = path(dir)
        self.indexfn = self.dir / 'contents/Syllabus/index.htm'
        self.index_xml = etree.parse(self.dir / 'contents/index.htm.xml').getroot()
        self.meta = self.get_metadata()
        self.policies = self.get_policies(self.meta)


    def fix_static(self, s):
        '''
        Fix a static path.  Return new static path.
        '''
        newpath = re.sub('[\./]+/contents/','/static/',s)
        if newpath.startswith('/static'):
            spath = 'contents' + newpath[7:]
            epath = newpath[1:]
            if not os.path.exists(spath):	# source path doesn't exist!
                print "      ERROR: missing file %s" % epath
                return ""
            if not os.path.exists(epath):
                # print "%s -> %s" % (spath, epath)
                os.system('mkdir -p "%s"' % os.path.dirname(epath))
                os.system('cp %s %s' % (spath,epath))
            return newpath
        return ''


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
            vcontents = fsbs(open(fn).read())
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
        
        m = re.search("http://www.youtube.com/v/([^']+)'",script.text)
        if not m:
            print "oops, cannot find youtube id in %s" % script.text
        else:
            ytid = m.group(1)
            video = etree.SubElement(vert,'video')
            video.set('youtube','1.0:%s' % ytid)
            video.set('from','00:00:20')
            #video.set('display_name','Video: ' + vert.get('display_name','Page'))
            video.set('display_name','Video: ' + title)
            print "      video: %s = %s" % (ytid, title)
            # print "(%s) %s = %s" % (vert.get('display_name'), vc, etree.tostring(video))
            embedbg.getparent().remove(embedbg)
            # print etree.tostring(html)
    
    
    def do_verticals(self, sxml, seq):
        '''
        Create vertical and fill up with contents of a section of a chapter.
        We are given the <a> for the OCW section, and the XML handle for the
        sequential where the contens should go.

        sxml = seq <a> from scholar
        seq = edX sequential
        '''
        href = sxml.get('href')
        sfn = href.replace('../../','')
        print "  sfn=",sfn
        v = fsbs(open(self.dir / sfn).read())	# load in the section HTML file
        nav = v.find('.//div[@id="parent-fieldname-text"]') 
        intro = etree.SubElement(seq, 'html')	# add HTML module in the edX xml tree
        intro.set('display_name','Introduction')
        for p in nav:				# include all content in the HTML as an introduction
            if p.get('class','') in ['sc_nav', 'sc_nav_bottom']:
                continue
            elif etree.tostring(p).startswith('<p>&#160;</p>'):
                continue
            elif p.tag=='blockquote':
                # embedded video or other content ; make this a separate module
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
    
    def do_chapters(self, ocw_xml, edxxml):
        '''
        In an OCW syllabus file, the chapter is described by a <div class="course_nav">
        The elements of the <ul> within that div are the chapters.
        
        We turn the contents of each chapter are sections; we turn those sections
        into sequentials.
        '''
        chapters_xml = ocw_xml.find('.//div[@id="course_nav"]').find('ul')
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
                dn = atag.text.strip()
                print "  section: ", dn
                seq = etree.SubElement(chapter,'sequential')
                seq.set('display_name',dn)
                self.do_verticals(atag,seq)
        
    def get_metadata_field(self, mseq, root=None):
        if root is None:
            root = self.index_xml
        namespaces={'lom':'http://ocw.mit.edu/xmlns/LOM'}
        x = root
        for v in mseq:
            x = x.xpath('.//lom:%s' % v,namespaces=namespaces)[0]
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
        xb.add_about_file('end_date.html', 'April 30, 2013')
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

        pjson = DEF_POLICY_JSON
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
        root = fsbs(open(self.dir/'contents/index.htm').read())
        div = root.find('.//div[@id="course_inner_chp"]')
        img = div.find('.//img[@itemprop="image"]')
        fn = img.get('src')
        fn = fn[3:]	# remove ../
        os.system('mkdir -p static/images')
        os.system('cp %s static/images/course_image.jpg' % fn)
        print "--> course image: %s" % fn

        
    #-----------------------------------------------------------------------------
    
    def export(self):
        meta = self.meta
        sys.stderr.write("metadata = %s\n" % meta)
    
        fn = self.dir / 'contents/Syllabus/index.htm'
        x = fsbs(open(fn).read())
        edxxml = etree.Element('course')
        edxxml.set('dirname',os.path.basename(os.getcwd()))
        edxxml.set('semester', self.DefaultSemester)
        for k, v in meta.items():
            edxxml.set(k,v)
        
        self.do_chapters(x, edxxml)
    
        policies = self.policies

        # grab course image via index.htm
        self.get_course_image()
        
        # make xbundle 
        xb = XBundle()
        xb.set_course(edxxml)
        xb.add_policies(policies)
        self.add_about_files(xb)

        # save it
        outfn = '%s_xbundle.xml' % self.cid
        xb.save(outfn)
        print "Done, wrote to %s" % outfn
    

#-----------------------------------------------------------------------------

if __name__=='__main__':
    sc = ScholarCourse()
    sc.export()
    
