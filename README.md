<h2>Convert OCW Scholar Content to edX XML</h2>

The following process will convert an existing OCW/OCW Scholar course into edX xml which can then be imported into edX Studio or used in the github/staging workflow.

The process includes executing two python scripts:

<strong>scholar2xbundle.py</strong>: This script will convert an OCW Scholar course archive (zip) into an edX course bundle.
  * Usage: python xbundle.py [--force-studio] [cmd] [infn] [outfn]         
where:<br />
    <strong>--force-studio</strong>: forces <sequential> to always be followed by <vertical> in export (this makes it compatible with Studio import)
    <br /><strong>cmd = test</strong>:  run unit tests
    <br /><strong>ccmd = convert</strong>: convert between xbundle and edX directory format (the xbundle filename must end with .xml)

<strong>xbundle.py</strong>: This script creates the system files necessary to run a course on the edX platform. i.e. policy files.

An xbundle file is an XML format file with element <xbundle>, which  includes the following sub-elements:  <br />
```<metadata>  
 <policies semester=...>: <policy> and <gradingpolicy> (each contain the JSON for the corresponding file) <br />
 <about>: <file filename=...> </about> 
 </metadata>  <br />
 <course semester="...">: course XML </course>
 ```

The XBundle class represents an xbundle file; it can read and write  the file, and it can import and export to standard edX (unbundled) format. 

<h2>Requirements</h2>
lxml<br />
pyaml<br />
path.py<br />
beautifulsoup

Can pip install these, if any fail, try easy_install.

<h2>Conversion Process</h2>

<h3>Install the requirements</h3>
1. $ sudo pip install pyaml
2. $ sudo pip install path.py
3. $ sudo pip install beautifulsoup
4. $ sudo pip install lxml
  * If pip installs fail for any of the above, try easy_install

<h2>Get the Files</h2>
5. Download zip archive of OCW course and unzip
6. Clone ocw2edx repo 
  * Example: $ git clone https://github.com/MITx/ocw2edx.git
7. $ cp -a scholar2xbundle.py and xbundle.py to the course folder within the unzipped archive
  * Example: $ cp -a /Users/jmartis/ocw2edx/. /Users/jmartis/6-01sc-spring-2011/6-01sc-spring-2011/
8. cd to the destination of #5 – Note the nested folder structure
  * Example: $ cd /Users/jmartis/6-01sc-spring-2011/6-01sc-spring-2011/

<h2>Execute the Scripts</h2>
9. $ python scholar2xbundle.py
10. $ mkdir temp
11. $ python xbundle.py --force-studio convert 6.01SC_xbundle.xml temp/
  * See usage above
12. Copy the /static directory into the newly created temp/course directory
  * Example: $ cp -a /Users/jmartis/6-01sc-spring-2011/6-01sc-spring-2011/static/. /Users/jmartis/6-01sc-spring-2011/6-01sc-spring-2011/temp/6.01SC/static/
  13. $ cd temp
*  Here you will see your complete course content 

<h2>Bringing Course into Studio</h2>
1. Create course in Studio with same name and number as in the newly created course.xml and policy.json files
2. Studio import accepts files in tar.gz format only. To create a tar.gz of your course, in /temp/<br />
   $ tar -cvf 6_01sc.tar.gz 6.01SC/
3. In studio, click on ‘Tools’ in the top nav, then ‘Import’ from the pull down menu.
4. Click the ‘Choose File’ button and navigate to the tar.gz file that you just created and click ‘Replace’
