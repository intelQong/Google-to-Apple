#!/usr/bin/env python3

# originally created and posted by user dgc on
# https://discussion.evernote.com/topic/97201-how-to-transfer-all-the-notes-from-google-keep-to-evernote/
# Modified by user charlescanato https://gitlab.com/charlescanato/google-keep-to-evernote-converter
# Modified by gokhan mete erturk to enable bulk operation of html files without any parameters and
# solves the character set problems on Windows
# Modified by Leonard777 to add importing of image data.

# until now, Google Takeout for Keep does NOT export:
# - correct order of lists notes (non-checked first, checked last)
# - list items indentation

import argparse
import os
import sys
import re
import parsedatetime as pdt
import time
import glob
import hashlib
import base64

cal = pdt.Calendar()

r1 = re.compile('<li class="listitem checked"><span class="bullet">&#9745;</span>.*?<span class="text">(.*?)</span>.*?</li>')
r2 = re.compile('<li class="listitem"><span class="bullet">&#9744;</span>.*?<span class="text">(.*?)</span>.*?</li>')
r3 = re.compile('<span class="chip label"><span class="label-name">([^<]*)</span>[^<]*</span>')
# Use non-greedy expressions to support multiple image tags for each note
r4 = re.compile(r'<img alt="" src="data:(.*?);(.*?)\, (.*?)" />')  # Fixed the comma
r5 = re.compile('<div class="content">(.*)</div>')
r6 = re.compile(r'<img alt="" src="(.*?(\.jpg|\.png|\.gif|\.jpeg))" />')  # Fixed the period


def readlineUntil(file, str):
    currLine = ""
    while not str in currLine:
        currLine = file.readline()
    return currLine

def readTagsFromChips(line):
    # line might still have chips
    if line.startswith('<div class="chips">'):
        return line + '\n'

def readImagesFromAttachment(line, fn):
    # Skip image processing, just return an empty result
    return ()

def mungefile(fn):
    fp = open(fn, 'r', encoding="utf8")
    
    title = readlineUntil( fp, "<title>" ).strip()
    title = title.replace('<title>', '').replace('</title>', '')

    readlineUntil( fp, "<body>" )
    t = fp.readline()
    tags = ''
    resources = ''
    if '"archived"' in t:
        tags = '<tag>archived</tag>'
    fp.readline() #</div> alone

    date = fp.readline().strip().replace('</div>', '')
    dt, flat = cal.parse(date)
    iso = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(time.mktime(dt)))

    fp.readline()  # extra title

    content = fp.readline()
    m = r5.search(content)
    if m:
        content = m.group(1)
    content = content.replace( '<ul class="list">', '' )

    for line in fp:
        line = line.strip()
        if line == '</div></body></html>':
            break
        elif line.startswith('<div class="chips">'):
            content += readTagsFromChips(line)
        elif line.startswith('<div class="attachments">'):
            # Skip images, only process text
            result = readImagesFromAttachment(line, fn)
            i = 0
            while i < len(result):
                if i+1 < len(result):
                    content += result[i]
                    resources += result[i+1]
                i += 2
        else:
            content += line + '\n'

    content = content.replace('<br>', '<br/>')
    content = content.replace('\n', '\0')

    while True:
        m = r1.search(content)
        if not m:
            break
        content = content[:m.start()] + '<en-todo checked="true"/>' + m.group(1) + '<br/>' + content[m.end():]

    while True:
        m = r2.search(content)
        if not m:
            break
        content = content[:m.start()] + '<en-todo checked="false"/>' + m.group(1) + '<br/>' + content[m.end():]

    content = content.replace('\0', '\n')

    # remove list close (if it was a list)
    lastUl = content.rfind('</ul>')
    if lastUl != -1:
        content = content[:lastUl] + content[lastUl+5:]

    m = r3.search(content)
    if m:
        content = content[:m.start()] + content[m.end():]
        tags = '<tag>' + m.group(1) + '</tag>'

    content = re.sub(
            r'class="[^"]*"',
            '',
            content
    )

    fp.close()

    print ('''
  <note>
    <title>{title}</title>
    <content><![CDATA[<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note style="word-wrap: break-word; -webkit-nbsp-mode: space; -webkit-line-break: after-white-space;">{content}</en-note>]]></content>
    <created>{iso}</created>
    <updated>{iso}</updated>
    {tags}
    <note-attributes>
      <latitude>0</latitude>
      <longitude>0</longitude>
      <source>google-keep</source>
      <reminder-order>0</reminder-order>
    </note-attributes>
    {resources}
  </note>
'''.format(**locals()), file=fxt)

parser = argparse.ArgumentParser(description="Convert Google Keep notes from .html to .enex for Evernote")
parser.add_argument('-o', '--output', help="The output file to write into. If not specified output goes to stdout.", default="sys.stdout")
parser.add_argument("htmlSource", help="The HTML file or list of files that should be converted", default="*.html", nargs="*")
args = parser.parse_args()

if args.output == "sys.stdout":
    fxt = sys.stdout
else:
    fxt = open(args.output, "w", encoding="utf8")

print ('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">
<en-export export-date="20180502T065115Z" application="Evernote/Windows" version="6.x">''', file=fxt)

if len(args.htmlSource) > 1:
    print(args.htmlSource)
    for filename in args.htmlSource:
        print(filename)
        mungefile(filename)
else:
    # Here, we need to expand the wildcard to actual file paths
    html_files = glob.glob(args.htmlSource[0])  # Expand *.html or any other file pattern
    for filename in html_files:
        mungefile(filename)

print ('''</en-export>''', file=fxt)
fxt.close()
