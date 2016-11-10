<h2>Convert OCW Course Content to edX XML</h2>

# Installation

    python setup.py develop

Usage:

1. ocw2edx -o edx_course_content.tar.gz <ocw_course_download_file>.zip
2. Upload edx_course_content.tar.gz to Studio

# Bringing Course into Studio

1. Create course in Studio with same name and number as in the newly created course.xml and policy.json files
2. In studio, click on ‘Tools’ in the top nav, then ‘Import’ from the pull down menu.
3. Click the ‘Choose File’ button and navigate to the tar.gz file that you just created and click ‘Replace’
